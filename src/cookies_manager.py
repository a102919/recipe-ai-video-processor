"""
Cookies Manager for yt-dlp
Handles downloading and caching cookies from R2 storage
"""
import os
import tempfile
import urllib.request
import logging
from typing import Optional, Generator
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class CookiesManager:
    """Manages yt-dlp cookies downloading and caching from R2"""

    def __init__(self, r2_base_url: str):
        """
        Initialize cookies manager

        Args:
            r2_base_url: R2 bucket base URL for cookies storage
        """
        self.r2_base_url = r2_base_url.rstrip('/')
        self.cookies_mapping = {
            'instagram': 'www.instagram.com_cookies.txt',
            'youtube': 'www.youtube.com_cookies.txt',
        }

    @contextmanager
    def get_cookies_file(self, platform: str) -> Generator[Optional[str], None, None]:
        """
        Download cookies file and return temporary file path (context manager)

        Usage:
            with cookies_manager.get_cookies_file('instagram') as cookie_file:
                # Use cookie_file
                pass
            # File is automatically deleted after context exits

        Args:
            platform: Platform name ('instagram', 'youtube', etc.)

        Yields:
            Temporary file path or None if no cookies configured
        """
        if platform not in self.cookies_mapping:
            logger.info(f"No cookies configured for platform: {platform}")
            yield None
            return

        temp_file_path = None
        try:
            filename = self.cookies_mapping[platform]
            cookies_url = f"{self.r2_base_url}/{filename}"

            logger.info(f"Downloading {platform} cookies from R2...")

            # Create request with User-Agent to avoid Cloudflare blocking
            req = urllib.request.Request(
                cookies_url,
                headers={'User-Agent': 'AizhuHelper-VideoProcessor/1.0'}
            )

            with urllib.request.urlopen(req) as response:
                cookies_content = response.read().decode('utf-8')

            # Create temporary cookies file
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                delete=False,
                suffix='.txt'
            )
            temp_file.write(cookies_content)
            temp_file.close()
            temp_file_path = temp_file.name

            logger.info(f"Using {platform} cookies: {temp_file_path}")

        except Exception as e:
            logger.warning(f"Failed to download cookies: {e}")
            temp_file_path = None

        # Always yield (either path or None), then handle any exceptions from the caller
        try:
            yield temp_file_path
        except Exception:
            # Re-raise any exception from the with-block to properly propagate it
            raise
        finally:
            # Guarantee cleanup
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    logger.debug(f"Cleaned up cookies file: {temp_file_path}")
                except Exception as e:
                    logger.error(f"Failed to cleanup cookies: {e}")
