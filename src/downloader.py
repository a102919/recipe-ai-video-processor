"""
Video Downloader using yt-dlp
Downloads cooking videos from various platforms for recipe extraction
"""
import os
import logging
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import yt_dlp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from .thumbnail_generator import proxy_thumbnail_to_r2
from .cookies_manager import CookiesManager
from .config import R2_COOKIES_BASE_URL

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """
    Result of video/photo download operation

    Supports tuple unpacking for backward compatibility:
        video_path, thumbnail_url, photo_paths = result
    """
    video_path: Optional[str] = None
    thumbnail_url: Optional[str] = None
    photo_paths: Optional[list[str]] = None

    def __iter__(self):
        """Enable tuple unpacking: video_path, thumbnail, photos = result"""
        return iter((self.video_path, self.thumbnail_url, self.photo_paths))

    @property
    def is_video(self) -> bool:
        """Check if result contains a video"""
        return self.video_path is not None

    @property
    def is_photo_carousel(self) -> bool:
        """Check if result contains photos"""
        return self.photo_paths is not None and len(self.photo_paths) > 0


class VideoDownloader:
    """Downloads videos from supported platforms using yt-dlp"""

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize video downloader

        Args:
            output_dir: Directory for downloaded videos (default: temp dir)
        """
        self.output_dir = output_dir or os.path.join(os.getcwd(), 'downloads')
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.cookies_manager = CookiesManager(R2_COOKIES_BASE_URL)

    def _detect_platform(self, url: str) -> str:
        """
        Detect video platform from URL

        Args:
            url: Video URL

        Returns:
            Platform name ('youtube', 'instagram', 'facebook', 'other')
        """
        url_lower = url.lower()
        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'youtube'
        elif 'instagram.com' in url_lower:
            return 'instagram'
        elif 'facebook.com' in url_lower or 'fb.watch' in url_lower:
            return 'facebook'
        else:
            return 'other'

    def download(self, url: str, filename_prefix: str = "video") -> DownloadResult:
        """
        Download video or photos from URL with automatic retry on transient failures

        Multi-tier fallback strategy:
        1. Try without cookies first (fastest, works for 90% public videos)
        2. If bot detection or login required, retry with cookies from R2
        3. If cookies also fail, raise detailed error

        Args:
            url: Video/Photo URL (YouTube, TikTok, Instagram, etc.)
            filename_prefix: Prefix for output filename

        Returns:
            DownloadResult containing:
            - For video: DownloadResult(video_path=..., thumbnail_url=...)
            - For TikTok photo carousel: DownloadResult(thumbnail_url=..., photo_paths=[...])

        Raises:
            ValueError: If URL is invalid or unsupported
            Exception: If download fails after all retries
        """
        if not url or not url.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid URL: {url}")

        platform = self._detect_platform(url)

        # Tier 1: Try without cookies (optimal for public content)
        logger.info(f"Attempting download without cookies (Tier 1)...")
        try:
            return self._download_with_ydl(url, filename_prefix, cookie_file=None)
        except (ValueError, Exception) as e:
            error_msg = str(e).lower()

            # Check if error indicates authentication is needed
            needs_auth = any(keyword in error_msg for keyword in [
                'sign in', 'login required', 'bot', 'age-restricted',
                'private', 'members-only', 'not available'
            ])

            if not needs_auth:
                # Not an auth issue, re-raise immediately
                logger.error(f"Tier 1 failed with non-auth error: {e}")
                raise

            logger.warning(f"Tier 1 failed (auth required): {e}")
            logger.info(f"Attempting download with cookies (Tier 2)...")

        # Tier 2: Try with cookies from R2
        with self.cookies_manager.get_cookies_file(platform) as cookie_file:
            if not cookie_file:
                raise ValueError(
                    f"Authentication required but no cookies available for {platform}. "
                    f"Please configure cookies following YOUTUBE_COOKIES_SETUP.md"
                )

            try:
                return self._download_with_ydl(url, filename_prefix, cookie_file)
            except Exception as e:
                logger.error(f"Tier 2 (with cookies) also failed: {e}")
                raise ValueError(
                    f"Failed to download even with cookies. "
                    f"Cookies may have expired or video is unavailable. "
                    f"Original error: {e}"
                )

    def _download_with_ydl(
        self,
        url: str,
        filename_prefix: str,
        cookie_file: Optional[str]
    ) -> DownloadResult:
        """
        Perform actual video download using yt-dlp with retry logic

        Args:
            url: Video URL
            filename_prefix: Prefix for output filename
            cookie_file: Path to cookies file (optional)

        Returns:
            DownloadResult with video_path and thumbnail_url
        """
        output_template = os.path.join(
            self.output_dir,
            f"{filename_prefix}_%(id)s.%(ext)s"
        )

        # yt-dlp options with aggressive rate limiting for bot detection avoidance
        ydl_opts = {
            'outtmpl': output_template,
            'noplaylist': True,
            'quiet': False,
            'no_warnings': True,
            # YouTube recommends 5-10s delays to avoid "content not available" errors
            'sleep_interval': 5,           # Minimum wait between requests
            'max_sleep_interval': 10,      # Maximum wait between requests
            'sleep_interval_requests': 1,  # Wait 1s between fragment downloads
        }

        # For YouTube: ALWAYS use clients that bypass bot detection
        # These clients work with/without cookies and avoid most bot checks
        platform = self._detect_platform(url)
        if platform == 'youtube':
            logger.info("Using YouTube clients that bypass bot detection (ios, web_safari, tv_embedded)")
            ydl_opts['extractor_args'] = {
                'youtube': {
                    'player_client': ['ios', 'web_safari', 'tv_embedded', 'mweb']
                }
            }

        if cookie_file:
            ydl_opts['cookiefile'] = cookie_file
            logger.info(f"Using cookies file: {cookie_file}")

        # Internal function with retry logic
        @retry(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=2, min=2, max=10),
            retry=retry_if_exception_type(yt_dlp.utils.DownloadError),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def _perform_download():
            logger.info(f"Downloading video from {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise ValueError(f"Failed to extract video info from {url}")

                # Get downloaded file path
                video_id = info.get('id', 'unknown')
                ext = info.get('ext', 'mp4')
                video_path = os.path.join(
                    self.output_dir,
                    f"{filename_prefix}_{video_id}.{ext}"
                )

                if not os.path.exists(video_path):
                    raise Exception(f"Download succeeded but file not found: {video_path}")

                # Process thumbnail
                thumbnail_url = self._process_thumbnail(info)

                logger.info(f"Downloaded video to {video_path}")
                return DownloadResult(video_path=video_path, thumbnail_url=thumbnail_url)

        try:
            return _perform_download()
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if 'rate-limit' in error_msg.lower() or 'login required' in error_msg.lower():
                raise ValueError(
                    f"Failed to download video after 4 attempts due to rate limiting. "
                    f"The platform may have blocked requests or cookies expired. "
                    f"Original error: {e}"
                )
            elif 'unsupported url' in error_msg.lower() and 'photo' in error_msg.lower():
                # This is a TikTok photo carousel - try gallery-dl
                logger.info("Detected TikTok photo carousel, switching to gallery-dl")
                return self._download_photos_with_gallery_dl(url, filename_prefix)
            else:
                raise ValueError(f"Failed to download video: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during download: {e}")
            raise

    def _select_best_thumbnail(self, info: dict) -> Optional[str]:
        """
        Select the best thumbnail from video info metadata

        Args:
            info: Video info dict from yt-dlp

        Returns:
            Best thumbnail URL or None
        """
        # Check for thumbnails array (TikTok, some platforms)
        thumbnails = info.get('thumbnails')
        if thumbnails and isinstance(thumbnails, list) and len(thumbnails) > 0:
            logger.info(f"Found {len(thumbnails)} thumbnails in metadata")

            # Sort by preference (higher is better)
            sorted_thumbnails = sorted(
                thumbnails,
                key=lambda t: t.get('preference', 0),
                reverse=True
            )

            # Get the best thumbnail URL
            best_thumbnail = sorted_thumbnails[0]
            thumbnail_url = best_thumbnail.get('url')
            thumbnail_id = best_thumbnail.get('id', 'unknown')

            logger.info(f"Selected thumbnail: id={thumbnail_id}, preference={best_thumbnail.get('preference', 0)}")
            return thumbnail_url

        # Fallback to single thumbnail field
        thumbnail_url = info.get('thumbnail')
        if thumbnail_url:
            logger.info("Using single 'thumbnail' field from metadata")
        else:
            logger.warning("No thumbnail found in video metadata")

        return thumbnail_url

    def _process_thumbnail(self, info: dict) -> Optional[str]:
        """
        Process thumbnail URL, proxying through R2 if needed for CORS

        Args:
            info: Video info dict from yt-dlp

        Returns:
            Processed thumbnail URL or None
        """
        # Select best thumbnail from available options
        thumbnail_url = self._select_best_thumbnail(info)

        if not thumbnail_url:
            return None

        # Check if thumbnail needs CORS proxy (Instagram only)
        needs_proxy = any(domain in thumbnail_url.lower() for domain in [
            'instagram', 'cdninstagram'
        ])

        if needs_proxy:
            logger.info(f"Thumbnail has CORS restrictions, proxying to R2...")
            try:
                thumbnail_url = proxy_thumbnail_to_r2(thumbnail_url)
                logger.info(f"Proxied thumbnail URL: {thumbnail_url}")
            except Exception as e:
                logger.warning(f"R2 proxy failed: {e}, using original URL")
        else:
            logger.info(f"Thumbnail URL (no proxy needed): {thumbnail_url}")

        return thumbnail_url

    def _upload_photo_thumbnail(self, photo_path: str) -> str:
        """
        Upload local photo file to R2 and return public URL

        Args:
            photo_path: Path to local photo file

        Returns:
            Public URL of uploaded photo on R2

        Raises:
            Exception: If upload fails
        """
        from .thumbnail_generator import ThumbnailProxy

        logger.info(f"Uploading photo thumbnail to R2: {photo_path}")
        try:
            proxy = ThumbnailProxy()
            thumbnail_url = proxy.upload_to_r2(photo_path)
            logger.info(f"Photo thumbnail uploaded: {thumbnail_url}")
            return thumbnail_url
        except Exception as e:
            logger.error(f"Failed to upload photo thumbnail to R2: {e}")
            # Fallback: return local path (will fail but at least we try)
            logger.warning("Falling back to local path (frontend may not be able to access)")
            return photo_path

    def _download_photos_with_gallery_dl(
        self,
        url: str,
        filename_prefix: str
    ) -> DownloadResult:
        """
        Download TikTok photo carousel using gallery-dl

        Args:
            url: TikTok photo carousel URL
            filename_prefix: Prefix for output directory

        Returns:
            DownloadResult with thumbnail_url and photo_paths

        Raises:
            ValueError: If download fails
        """
        logger.info(f"Downloading TikTok photo carousel with gallery-dl: {url}")

        # Run gallery-dl to download photos
        cmd = [
            'gallery-dl',
            '--directory', self.output_dir,
            '--quiet',
            url
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            # Note: gallery-dl return code 4 means partial success (e.g., audio failed but images succeeded)
            if result.returncode not in (0, 4):
                logger.error(f"gallery-dl failed with code {result.returncode}: {result.stderr}")
                raise ValueError(f"Failed to download photos: {result.stderr}")

            logger.info(f"gallery-dl completed with return code {result.returncode}")

            # Find downloaded images
            photo_paths = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp']:
                photo_paths.extend(Path(self.output_dir).rglob(ext))

            if not photo_paths:
                raise ValueError("No photos downloaded from TikTok carousel")

            # Sort by filename to maintain order
            photo_paths = sorted(photo_paths)
            photo_path_strs = [str(p) for p in photo_paths]

            logger.info(f"Downloaded {len(photo_path_strs)} photos from carousel")

            # Upload first photo to R2 as thumbnail (return public URL instead of local path)
            if photo_path_strs:
                thumbnail_url = self._upload_photo_thumbnail(photo_path_strs[0])
            else:
                thumbnail_url = None

            return DownloadResult(thumbnail_url=thumbnail_url, photo_paths=photo_path_strs)

        except subprocess.TimeoutExpired:
            logger.error("gallery-dl timed out after 60 seconds")
            raise ValueError("Photo download timed out")
        except Exception as e:
            logger.error(f"Unexpected error in gallery-dl: {e}")
            raise ValueError(f"Failed to download photos: {e}")


# Convenience function for single-use download
def download_video(url: str, output_dir: Optional[str] = None) -> DownloadResult:
    """
    Download video or photos from URL

    Args:
        url: Video/Photo URL
        output_dir: Output directory (optional)

    Returns:
        DownloadResult containing:
        - For video: DownloadResult(video_path=..., thumbnail_url=...)
        - For TikTok photo carousel: DownloadResult(thumbnail_url=..., photo_paths=[...])

    Note:
        Supports tuple unpacking for backward compatibility:
            video_path, thumbnail_url, photo_paths = download_video(url)
    """
    downloader = VideoDownloader(output_dir=output_dir)
    return downloader.download(url)
