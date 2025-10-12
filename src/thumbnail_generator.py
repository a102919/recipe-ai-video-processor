"""
Thumbnail Proxy for Cloudflare R2
Downloads thumbnails from CORS-blocked sources and re-uploads to R2
"""
import os
import logging
import uuid
import requests
from pathlib import Path
from typing import Optional
import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class ThumbnailProxy:
    """Proxies CORS-blocked thumbnails through R2"""

    def __init__(self):
        """Initialize thumbnail proxy with R2 credentials"""
        self.temp_dir = os.getenv('TEMP_DIR', '/tmp/aizhu-helper')
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)

        # R2 Configuration
        self.r2_account_id = os.getenv('R2_ACCOUNT_ID')
        self.r2_access_key = os.getenv('R2_ACCESS_KEY_ID')
        self.r2_secret_key = os.getenv('R2_SECRET_ACCESS_KEY')
        self.r2_bucket = os.getenv('R2_BUCKET_NAME', 'aizhu-helper-thumbnails')
        self.r2_public_url = os.getenv('R2_PUBLIC_URL')  # e.g., https://thumbnails.recipeai.com

        # Enhanced logging for R2 configuration status
        logger.info("=== ThumbnailProxy Initialization ===")
        logger.info(f"R2_ACCOUNT_ID: {'✓ set' if self.r2_account_id else '✗ NOT SET'}")
        logger.info(f"R2_ACCESS_KEY_ID: {'✓ set' if self.r2_access_key else '✗ NOT SET'}")
        logger.info(f"R2_SECRET_ACCESS_KEY: {'✓ set' if self.r2_secret_key else '✗ NOT SET'}")
        logger.info(f"R2_BUCKET_NAME: {self.r2_bucket}")
        logger.info(f"R2_PUBLIC_URL: {self.r2_public_url or 'NOT SET (will use .r2.dev)'}")

        if not all([self.r2_account_id, self.r2_access_key, self.r2_secret_key]):
            logger.warning("⚠️  R2 credentials not configured. Thumbnail upload will fail.")
            logger.warning("⚠️  Please check R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY environment variables")

        # S3-compatible client for R2
        if self.r2_account_id:
            try:
                self.s3_client = boto3.client(
                    's3',
                    endpoint_url=f'https://{self.r2_account_id}.r2.cloudflarestorage.com',
                    aws_access_key_id=self.r2_access_key,
                    aws_secret_access_key=self.r2_secret_key,
                    config=Config(signature_version='s3v4'),
                )
                logger.info("✓ R2 S3 client initialized successfully")
            except Exception as e:
                logger.error(f"✗ Failed to initialize R2 S3 client: {e}")
                logger.exception("Full traceback:")
                self.s3_client = None
        else:
            logger.warning("✗ R2 client not initialized (missing account ID)")
            self.s3_client = None

    def download_thumbnail(self, thumbnail_url: str, output_path: Optional[str] = None) -> str:
        """
        Download thumbnail from URL

        Args:
            thumbnail_url: URL of thumbnail image
            output_path: Optional path for saved thumbnail (default: temp dir)

        Returns:
            Path to downloaded thumbnail image

        Raises:
            Exception: If download fails
        """
        if not thumbnail_url:
            raise ValueError("Thumbnail URL is required")

        # Generate output path if not provided
        if not output_path:
            thumbnail_id = uuid.uuid4().hex[:12]
            output_path = os.path.join(self.temp_dir, f"thumb_{thumbnail_id}.jpg")

        try:
            logger.info(f"Downloading thumbnail from: {thumbnail_url[:100]}...")

            # Download with timeout and headers
            response = requests.get(
                thumbnail_url,
                timeout=10,
                headers={'User-Agent': 'AizhuHelper/1.0'}
            )

            # Log detailed response info
            logger.info(f"HTTP Response: {response.status_code} {response.reason}")
            logger.info(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}")
            logger.info(f"Content-Length: {len(response.content)} bytes")

            response.raise_for_status()

            # Save to file
            with open(output_path, 'wb') as f:
                f.write(response.content)

            if not os.path.exists(output_path):
                raise Exception(f"Thumbnail not saved: {output_path}")

            logger.info(f"✓ Thumbnail downloaded successfully: {output_path}")
            return output_path

        except requests.HTTPError as e:
            logger.error(f"✗ HTTP error during thumbnail download: {e}")
            logger.error(f"   Status code: {e.response.status_code if e.response else 'N/A'}")
            logger.error(f"   Response: {e.response.text[:200] if e.response else 'N/A'}")
            logger.exception("Full traceback:")
            raise Exception(f"Failed to download thumbnail (HTTP {e.response.status_code if e.response else 'error'}): {e}")
        except requests.Timeout as e:
            logger.error(f"✗ Timeout downloading thumbnail after 10 seconds: {e}")
            logger.exception("Full traceback:")
            raise Exception(f"Timeout downloading thumbnail: {e}")
        except requests.RequestException as e:
            logger.error(f"✗ Network error downloading thumbnail: {e}")
            logger.exception("Full traceback:")
            raise Exception(f"Failed to download thumbnail: {e}")
        except Exception as e:
            logger.error(f"✗ Unexpected error during thumbnail download: {e}")
            logger.exception("Full traceback:")
            raise

    def upload_to_r2(self, thumbnail_path: str, object_key: Optional[str] = None) -> str:
        """
        Upload thumbnail to Cloudflare R2

        Args:
            thumbnail_path: Path to thumbnail file
            object_key: Optional S3 object key (default: generated UUID)

        Returns:
            Public URL of uploaded thumbnail

        Raises:
            Exception: If upload fails or R2 not configured
        """
        if not self.s3_client:
            raise Exception("R2 not configured. Check R2_* environment variables.")

        if not os.path.exists(thumbnail_path):
            raise ValueError(f"Thumbnail file not found: {thumbnail_path}")

        # Generate object key if not provided
        if not object_key:
            file_ext = Path(thumbnail_path).suffix
            object_key = f"thumbnails/{uuid.uuid4().hex}{file_ext}"

        try:
            logger.info(f"Uploading thumbnail to R2...")
            logger.info(f"  Bucket: {self.r2_bucket}")
            logger.info(f"  Key: {object_key}")
            logger.info(f"  File: {thumbnail_path} ({os.path.getsize(thumbnail_path)} bytes)")

            with open(thumbnail_path, 'rb') as f:
                self.s3_client.put_object(
                    Bucket=self.r2_bucket,
                    Key=object_key,
                    Body=f,
                    ContentType='image/jpeg',
                    CacheControl='public, max-age=31536000',  # 1 year
                )

            # Generate public URL
            if self.r2_public_url:
                public_url = f"{self.r2_public_url}/{object_key}"
            else:
                # Fallback: use R2.dev subdomain (if public)
                public_url = f"https://{self.r2_bucket}.r2.dev/{object_key}"

            logger.info(f"✓ Thumbnail uploaded successfully to R2!")
            logger.info(f"✓ Public URL: {public_url}")
            return public_url

        except Exception as e:
            logger.error(f"✗ R2 upload failed: {e}")
            logger.error(f"   Bucket: {self.r2_bucket}")
            logger.error(f"   Key: {object_key}")
            logger.error(f"   Endpoint: https://{self.r2_account_id}.r2.cloudflarestorage.com")
            logger.exception("Full traceback:")
            raise

    def download_and_upload(self, thumbnail_url: str) -> str:
        """
        Download thumbnail and upload to R2 (all-in-one)

        Args:
            thumbnail_url: URL of thumbnail image

        Returns:
            Public URL of uploaded thumbnail on R2

        Raises:
            Exception: If download or upload fails
        """
        thumbnail_path = None
        try:
            # Step 1: Download thumbnail
            thumbnail_path = self.download_thumbnail(thumbnail_url)

            # Step 2: Upload to R2
            public_url = self.upload_to_r2(thumbnail_path)

            return public_url

        finally:
            # Cleanup: delete local thumbnail file
            if thumbnail_path and os.path.exists(thumbnail_path):
                try:
                    os.remove(thumbnail_path)
                    logger.debug(f"Cleaned up thumbnail: {thumbnail_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup thumbnail: {e}")


# Convenience function
def proxy_thumbnail_to_r2(thumbnail_url: str) -> str:
    """
    Proxy thumbnail URL to R2 (for CORS-blocked sources)

    Args:
        thumbnail_url: Original thumbnail URL

    Returns:
        Public URL of R2-hosted thumbnail
    """
    proxy = ThumbnailProxy()
    return proxy.download_and_upload(thumbnail_url)
