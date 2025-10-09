"""
Video Downloader using yt-dlp
Downloads cooking videos from various platforms for recipe extraction
"""
import os
import logging
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional
import yt_dlp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from .thumbnail_generator import proxy_thumbnail_to_r2

logger = logging.getLogger(__name__)


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

    def download(self, url: str, filename_prefix: str = "video") -> tuple[str, Optional[str]]:
        """
        Download video from URL with automatic retry on transient failures

        Args:
            url: Video URL (YouTube, Instagram, etc.)
            filename_prefix: Prefix for output filename

        Returns:
            Tuple of (video_path, thumbnail_url)

        Raises:
            ValueError: If URL is invalid or unsupported
            Exception: If download fails after all retries
        """
        if not url or not url.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid URL: {url}")

        output_template = os.path.join(
            self.output_dir,
            f"{filename_prefix}_%(id)s.%(ext)s"
        )

        # Prepare cookies from R2 URL (if configured)
        cookie_file = None
        # Fixed R2 public URL (this bucket has public access enabled)
        cookies_url = "https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails/www.instagram.com_cookies.txt"

        try:
            # Download cookies from R2
            logger.info(f"Downloading Instagram cookies from R2...")

            # Create request with User-Agent to avoid Cloudflare blocking
            req = urllib.request.Request(
                cookies_url,
                headers={'User-Agent': 'RecipeAI-VideoProcessor/1.0'}
            )
            with urllib.request.urlopen(req) as response:
                cookies_content = response.read().decode('utf-8')

            # Create temporary cookies file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write(cookies_content)
                cookie_file = f.name

            # Debug: Validate cookies file content
            cookie_lines = cookies_content.strip().split('\n')
            has_netscape_header = cookie_lines[0].startswith('# Netscape HTTP Cookie File')
            cookie_names = []
            for line in cookie_lines:
                if not line.startswith('#') and line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 6:
                        cookie_names.append(parts[5])  # Cookie name is 6th field

            logger.info(f"Using Instagram cookies from R2")
            logger.info(f"Cookies validation: Netscape header={has_netscape_header}, "
                       f"Cookie count={len(cookie_names)}, "
                       f"Cookie names={cookie_names[:5]}")  # Show first 5 cookie names

            # Check for critical cookies
            critical_cookies = {'sessionid', 'csrftoken', 'ds_user_id'}
            found_critical = critical_cookies.intersection(set(cookie_names))
            missing_critical = critical_cookies - found_critical

            if missing_critical:
                logger.warning(f"Missing critical cookies: {missing_critical}")
            else:
                logger.info("All critical cookies present ✓")

        except Exception as e:
            logger.warning(f"Failed to download/create cookies file from R2: {e}")

        # yt-dlp options: no playlist, default quality
        # Note: quiet=True causes "Broken pipe" errors with Facebook videos
        ydl_opts = {
            # No format specification - use yt-dlp default
            'outtmpl': output_template,
            'noplaylist': True,
            'quiet': False,  # Keep False to prevent broken pipe errors
            'no_warnings': True,  # Hide warnings for cleaner output
            'sleep_interval': 3,  # Wait 3 seconds between downloads to avoid rate limits
            'max_sleep_interval': 10,  # Maximum sleep interval if needed
        }

        # Add cookies file if available
        if cookie_file:
            ydl_opts['cookiefile'] = cookie_file

        # Internal function with retry logic for rate limit handling
        @retry(
            stop=stop_after_attempt(4),  # 1 original + 3 retries
            wait=wait_exponential(multiplier=2, min=2, max=10),  # 2s, 4s, 8s
            retry=retry_if_exception_type(yt_dlp.utils.DownloadError),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def _download_with_retry():
            """Internal function that performs actual download with retry"""
            logger.info(f"Downloading video from {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise ValueError(f"Failed to extract video info from {url}")

                # Get actual downloaded filename
                video_id = info.get('id', 'unknown')
                ext = info.get('ext', 'mp4')
                video_path = os.path.join(
                    self.output_dir,
                    f"{filename_prefix}_{video_id}.{ext}"
                )

                if not os.path.exists(video_path):
                    raise Exception(f"Download succeeded but file not found: {video_path}")

                # Get thumbnail from yt-dlp
                thumbnail_url = info.get('thumbnail')

                if thumbnail_url:
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
                else:
                    logger.warning("No thumbnail URL found in video metadata")

                logger.info(f"Downloaded video to {video_path}")
                return (video_path, thumbnail_url)

        try:
            return _download_with_retry()
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            # Provide helpful error messages based on error type
            if 'rate-limit' in error_msg.lower() or 'login required' in error_msg.lower():
                raise ValueError(
                    f"Failed to download video after 4 attempts due to rate limiting. "
                    f"Instagram/Facebook may have temporarily blocked requests. "
                    f"The cookies from R2 may have expired. Please update the cookies file at:\n"
                    f"{cookies_url}\n\n"
                    f"Original error: {e}"
                )
            else:
                raise ValueError(f"Failed to download video: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during download: {e}")
            raise
        finally:
            # Clean up temporary cookies file
            if cookie_file and os.path.exists(cookie_file):
                try:
                    os.unlink(cookie_file)
                    logger.debug(f"Cleaned up temporary cookies file: {cookie_file}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup cookies file: {e}")


# Convenience function for single-use download
def download_video(url: str, output_dir: Optional[str] = None) -> tuple[str, Optional[str]]:
    """
    Download video from URL

    Args:
        url: Video URL
        output_dir: Output directory (optional)

    Returns:
        Tuple of (video_path, thumbnail_url)
    """
    downloader = VideoDownloader(output_dir=output_dir)
    return downloader.download(url)
