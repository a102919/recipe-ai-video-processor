"""
Video Downloader using yt-dlp
Downloads cooking videos from various platforms for recipe extraction
"""
import os
import logging
from pathlib import Path
from typing import Optional
import yt_dlp

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
        Download video from URL

        Args:
            url: Video URL (YouTube, etc.)
            filename_prefix: Prefix for output filename

        Returns:
            Tuple of (video_path, thumbnail_url)

        Raises:
            ValueError: If URL is invalid or unsupported
            Exception: If download fails
        """
        if not url or not url.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid URL: {url}")

        output_template = os.path.join(
            self.output_dir,
            f"{filename_prefix}_%(id)s.%(ext)s"
        )

        # yt-dlp options: medium quality, mp4 format, no playlist
        # Note: quiet=True causes "Broken pipe" errors with Facebook videos
        ydl_opts = {
            'format': 'best[height<=720][ext=mp4]/best[ext=mp4]/best',
            'outtmpl': output_template,
            'noplaylist': True,
            'quiet': False,  # Keep False to prevent broken pipe errors
            'no_warnings': True,  # Hide warnings for cleaner output
        }

        try:
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

                # Extract thumbnail URL from video metadata
                thumbnail_url = info.get('thumbnail')

                logger.info(f"Downloaded video to {video_path}")
                logger.info(f"Thumbnail URL: {thumbnail_url or 'N/A'}")
                return (video_path, thumbnail_url)

        except yt_dlp.utils.DownloadError as e:
            logger.error(f"Download failed: {e}")
            raise ValueError(f"Failed to download video: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during download: {e}")
            raise


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
