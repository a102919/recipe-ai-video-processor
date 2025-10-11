#!/usr/bin/env python3
"""
Integration tests for all supported platforms
Tests multi-tier fallback strategy and cookie handling
"""
import pytest
import os
from pathlib import Path
import sys

# Add src to path for local testing
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.downloader import VideoDownloader


# Test URLs (use actual public videos for realistic testing)
TEST_URLS = {
    'youtube_public': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',  # Public video
    'youtube_shorts': 'https://youtube.com/shorts/DVhKfGub36k',  # Public shorts
    # 'youtube_age_restricted': '',  # Requires manual setup with actual age-restricted video
    # 'instagram': '',  # Requires Instagram cookies
    # 'tiktok': '',  # Public TikTok video
    # 'tiktok_photos': '',  # TikTok photo carousel
}


class TestYouTube:
    """Test YouTube downloads with multi-tier strategy"""

    @pytest.fixture
    def downloader(self, tmp_path):
        """Create downloader with temporary directory"""
        return VideoDownloader(output_dir=str(tmp_path))

    def test_youtube_public_video_no_cookies(self, downloader):
        """Test that public YouTube video downloads WITHOUT cookies (Tier 1)"""
        url = TEST_URLS['youtube_public']

        video_path, thumbnail_url, photo_paths = downloader.download(url)

        # Verify results
        assert video_path is not None
        assert Path(video_path).exists()
        assert Path(video_path).stat().st_size > 0
        assert thumbnail_url is not None
        assert photo_paths is None

        print(f"✅ Public video downloaded without cookies")
        print(f"   Video: {video_path}")
        print(f"   Size: {Path(video_path).stat().st_size / 1024 / 1024:.2f} MB")

    def test_youtube_shorts_no_cookies(self, downloader):
        """Test that YouTube Shorts downloads WITHOUT cookies (Tier 1)"""
        url = TEST_URLS['youtube_shorts']

        video_path, thumbnail_url, photo_paths = downloader.download(url)

        # Verify results
        assert video_path is not None
        assert Path(video_path).exists()
        assert thumbnail_url is not None
        assert photo_paths is None

        print(f"✅ YouTube Shorts downloaded without cookies")
        print(f"   Video: {video_path}")

    @pytest.mark.skipif(
        not os.environ.get('TEST_YOUTUBE_COOKIES'),
        reason="Requires YouTube cookies configured"
    )
    def test_youtube_age_restricted_with_cookies(self, downloader):
        """Test that age-restricted video falls back to cookies (Tier 2)"""
        # This test requires:
        # 1. A real age-restricted video URL
        # 2. YouTube cookies configured in R2
        # 3. TEST_YOUTUBE_COOKIES=1 environment variable

        pytest.skip("Requires manual configuration with age-restricted video URL")


class TestInstagram:
    """Test Instagram downloads"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return VideoDownloader(output_dir=str(tmp_path))

    @pytest.mark.skipif(
        not os.environ.get('TEST_INSTAGRAM'),
        reason="Requires Instagram cookies configured"
    )
    def test_instagram_public_reel(self, downloader):
        """Test Instagram Reel download with cookies"""
        pytest.skip("Requires Instagram test URL and cookies")


class TestTikTok:
    """Test TikTok downloads"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return VideoDownloader(output_dir=str(tmp_path))

    @pytest.mark.skipif(
        not os.environ.get('TEST_TIKTOK'),
        reason="Requires TikTok test URL"
    )
    def test_tiktok_public_video(self, downloader):
        """Test TikTok video download"""
        pytest.skip("Requires TikTok test URL")

    @pytest.mark.skipif(
        not os.environ.get('TEST_TIKTOK_PHOTOS'),
        reason="Requires TikTok photo carousel URL and gallery-dl"
    )
    def test_tiktok_photo_carousel(self, downloader):
        """Test TikTok photo carousel download (uses gallery-dl)"""
        pytest.skip("Requires TikTok photo carousel URL")


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return VideoDownloader(output_dir=str(tmp_path))

    def test_invalid_url_empty(self, downloader):
        """Test that empty URL raises ValueError"""
        with pytest.raises(ValueError, match="Invalid URL"):
            downloader.download("")

    def test_invalid_url_no_protocol(self, downloader):
        """Test that URL without protocol raises ValueError"""
        with pytest.raises(ValueError, match="Invalid URL"):
            downloader.download("youtube.com/watch?v=test")

    def test_nonexistent_video(self, downloader):
        """Test that nonexistent video raises appropriate error"""
        fake_url = "https://www.youtube.com/watch?v=NONEXISTENT123456789"

        with pytest.raises(ValueError):
            downloader.download(fake_url)


class TestMultiTierStrategy:
    """Test the multi-tier fallback strategy"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return VideoDownloader(output_dir=str(tmp_path))

    def test_tier1_success_no_r2_access(self, downloader, monkeypatch):
        """Test that Tier 1 succeeds even if R2 is inaccessible"""
        # Simulate R2 being down by using invalid base URL
        downloader.cookies_manager.r2_base_url = "https://invalid-r2-url.example.com"

        url = TEST_URLS['youtube_public']
        video_path, thumbnail_url, photo_paths = downloader.download(url)

        # Should still succeed via Tier 1 (no cookies)
        assert video_path is not None
        assert Path(video_path).exists()

        print(f"✅ Download succeeded without R2 access (Tier 1 strategy working)")


if __name__ == "__main__":
    # Run tests manually for quick testing
    import tempfile

    print("=" * 80)
    print("Manual Integration Test Run")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        downloader = VideoDownloader(output_dir=tmpdir)

        # Test 1: YouTube public video
        print("\n🧪 Test 1: YouTube public video (no cookies)")
        try:
            video_path, thumbnail_url, photo_paths = downloader.download(
                TEST_URLS['youtube_public']
            )
            print(f"   ✅ Success: {video_path}")
        except Exception as e:
            print(f"   ❌ Failed: {e}")

        # Test 2: YouTube Shorts
        print("\n🧪 Test 2: YouTube Shorts (no cookies)")
        try:
            video_path, thumbnail_url, photo_paths = downloader.download(
                TEST_URLS['youtube_shorts']
            )
            print(f"   ✅ Success: {video_path}")
        except Exception as e:
            print(f"   ❌ Failed: {e}")

        # Test 3: Error handling
        print("\n🧪 Test 3: Invalid URL handling")
        try:
            downloader.download("")
            print(f"   ❌ Should have raised ValueError")
        except ValueError as e:
            print(f"   ✅ Correctly raised ValueError: {e}")

    print("\n" + "=" * 80)
    print("Manual test run complete")
    print("=" * 80)
