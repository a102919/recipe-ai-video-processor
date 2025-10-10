"""
Cookies Manager for yt-dlp
Handles downloading and caching cookies from R2 storage
"""
import os
import tempfile
import urllib.request
import logging
from typing import Optional

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

    def get_cookies_file(self, platform: str) -> Optional[str]:
        """
        Download cookies file for platform and return temporary file path

        Args:
            platform: Platform name ('instagram', 'youtube', etc.)

        Returns:
            Temporary file path or None if no cookies configured
        """
        if platform not in self.cookies_mapping:
            logger.info(f"No cookies configured for platform: {platform}")
            return None

        filename = self.cookies_mapping[platform]
        cookies_url = f"{self.r2_base_url}/{filename}"

        try:
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

            logger.info(f"Using {platform} cookies from R2: {temp_file.name}")
            return temp_file.name

        except Exception as e:
            logger.warning(f"Failed to download cookies from R2: {e}")
            return None
