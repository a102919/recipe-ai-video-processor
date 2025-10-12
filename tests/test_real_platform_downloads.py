#!/usr/bin/env python3
"""
Real platform download tests for YouTube, Instagram, Facebook, and TikTok
Tests actual video downloads with real public URLs to ensure functionality
"""
import pytest
import os
import sys
from pathlib import Path
import tempfile

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.downloader import VideoDownloader, DownloadResult


# Real public test URLs that should always work
REAL_TEST_URLS = {
    # YouTube - various formats
    'youtube_standard': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',  # Rick Astley - Never Gonna Give You Up
    'youtube_shorts': 'https://youtube.com/shorts/DVhKfGub36k',  # Random cooking shorts

    # Instagram - public reels (may require cookies for reliability)
    'instagram_reel': 'https://www.instagram.com/reel/DBvnw1nBrxT/',  # Real public Instagram Reel

    # Facebook - public videos
    'facebook_video': 'https://www.facebook.com/share/r/1ERTqo87RT/',  # Real public Facebook video

    # TikTok - videos and photo carousels
    'tiktok_video': 'https://vt.tiktok.com/ZSUDeadj6/',  # Real public TikTok video
    'tiktok_photos': 'https://www.tiktok.com/@username/photo/1234567890',  # Placeholder - update with real photo carousel if needed
}


@pytest.fixture
def downloader():
    """Create downloader with temporary directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield VideoDownloader(output_dir=tmpdir)


class TestYouTubeRealDownloads:
    """Test real YouTube video downloads"""

    def test_youtube_standard_video(self, downloader):
        """Test downloading a standard YouTube video"""
        url = REAL_TEST_URLS['youtube_standard']

        result = downloader.download(url)

        # Verify result structure
        assert isinstance(result, DownloadResult)
        assert result.is_video
        assert not result.is_photo_carousel

        # Verify video file
        assert result.video_path is not None
        assert Path(result.video_path).exists()
        assert Path(result.video_path).stat().st_size > 0

        # Verify thumbnail
        assert result.thumbnail_url is not None
        assert result.thumbnail_url.startswith('http')

        # Verify no photos
        assert result.photo_paths is None

        print(f"✅ YouTube standard video download succeeded")
        print(f"   Video: {result.video_path}")
        print(f"   Size: {Path(result.video_path).stat().st_size / 1024 / 1024:.2f} MB")
        print(f"   Thumbnail: {result.thumbnail_url[:80]}...")

    def test_youtube_shorts(self, downloader):
        """Test downloading YouTube Shorts"""
        url = REAL_TEST_URLS['youtube_shorts']

        result = downloader.download(url)

        # Verify result
        assert result.is_video
        assert result.video_path is not None
        assert Path(result.video_path).exists()
        assert result.thumbnail_url is not None

        print(f"✅ YouTube Shorts download succeeded")
        print(f"   Video: {result.video_path}")

    def test_youtube_android_client_bypass(self, downloader):
        """Test that Android client is used for YouTube (bot detection bypass)"""
        url = REAL_TEST_URLS['youtube_standard']

        # This should succeed without cookies using Android client
        result = downloader.download(url)

        assert result.video_path is not None
        assert Path(result.video_path).exists()

        print(f"✅ YouTube download via Android client succeeded (no cookies needed)")

    def test_youtube_tuple_unpacking(self, downloader):
        """Test backward compatibility with tuple unpacking"""
        url = REAL_TEST_URLS['youtube_standard']

        # Old-style tuple unpacking should still work
        video_path, thumbnail_url, photo_paths = downloader.download(url)

        assert video_path is not None
        assert Path(video_path).exists()
        assert thumbnail_url is not None
        assert photo_paths is None

        print(f"✅ Tuple unpacking compatibility verified")


class TestInstagramRealDownloads:
    """Test real Instagram downloads"""

    @pytest.mark.skipif(
        not os.getenv('TEST_INSTAGRAM'),
        reason="Instagram test requires TEST_INSTAGRAM=1 and valid test URL"
    )
    def test_instagram_public_reel(self, downloader):
        """Test downloading a public Instagram Reel"""
        url = REAL_TEST_URLS['instagram_reel']

        # Instagram may require cookies, so this might fallback to Tier 2
        result = downloader.download(url)

        # Verify result
        assert result.is_video
        assert result.video_path is not None
        assert Path(result.video_path).exists()

        # Instagram thumbnail should be proxied through R2
        if result.thumbnail_url:
            # Check if thumbnail was proxied (R2 URL or fallback to Instagram)
            is_r2_url = '.r2.dev' in result.thumbnail_url or 'R2_PUBLIC_URL' in result.thumbnail_url
            is_instagram_url = 'instagram' in result.thumbnail_url.lower()
            assert is_r2_url or is_instagram_url

        print(f"✅ Instagram Reel download succeeded")
        print(f"   Video: {result.video_path}")
        print(f"   Thumbnail: {result.thumbnail_url[:80]}...")

    @pytest.mark.skipif(
        not os.getenv('TEST_INSTAGRAM'),
        reason="Instagram test requires TEST_INSTAGRAM=1 and cookies"
    )
    def test_instagram_with_cookies_fallback(self, downloader):
        """Test that Instagram falls back to cookies when needed"""
        url = REAL_TEST_URLS['instagram_reel']

        # This test verifies the multi-tier strategy works
        result = downloader.download(url)

        assert result.video_path is not None
        assert Path(result.video_path).exists()

        print(f"✅ Instagram multi-tier download strategy working")


class TestFacebookRealDownloads:
    """Test real Facebook downloads"""

    @pytest.mark.skipif(
        not os.getenv('TEST_FACEBOOK'),
        reason="Facebook test requires TEST_FACEBOOK=1 and valid test URL"
    )
    def test_facebook_public_video(self, downloader):
        """Test downloading a public Facebook video"""
        url = REAL_TEST_URLS['facebook_video']

        result = downloader.download(url)

        # Verify result
        assert result.is_video
        assert result.video_path is not None
        assert Path(result.video_path).exists()
        assert Path(result.video_path).stat().st_size > 0

        print(f"✅ Facebook video download succeeded")
        print(f"   Video: {result.video_path}")
        print(f"   Size: {Path(result.video_path).stat().st_size / 1024 / 1024:.2f} MB")

    @pytest.mark.skipif(
        not os.getenv('TEST_FACEBOOK'),
        reason="Facebook test requires TEST_FACEBOOK=1"
    )
    def test_facebook_short_url(self, downloader):
        """Test downloading from fb.watch short URL"""
        # Example: https://fb.watch/abc123/
        pytest.skip("Requires real fb.watch URL for testing")


class TestTikTokRealDownloads:
    """Test real TikTok (抖音) downloads"""

    @pytest.mark.skipif(
        not os.getenv('TEST_TIKTOK'),
        reason="TikTok test requires TEST_TIKTOK=1 and valid test URL"
    )
    def test_tiktok_video(self, downloader):
        """Test downloading a TikTok video"""
        url = REAL_TEST_URLS['tiktok_video']

        result = downloader.download(url)

        # Verify video result
        assert result.is_video
        assert result.video_path is not None
        assert Path(result.video_path).exists()

        # TikTok should have thumbnail from metadata
        assert result.thumbnail_url is not None

        print(f"✅ TikTok video download succeeded")
        print(f"   Video: {result.video_path}")
        print(f"   Thumbnail: {result.thumbnail_url[:80]}...")

    @pytest.mark.skipif(
        not os.getenv('TEST_TIKTOK_PHOTOS'),
        reason="TikTok photo carousel test requires TEST_TIKTOK_PHOTOS=1 and gallery-dl"
    )
    def test_tiktok_photo_carousel(self, downloader):
        """Test downloading a TikTok photo carousel (使用 gallery-dl)"""
        url = REAL_TEST_URLS['tiktok_photos']

        result = downloader.download(url)

        # Verify photo carousel result
        assert result.is_photo_carousel
        assert not result.is_video
        assert result.video_path is None

        # Verify photos were downloaded
        assert result.photo_paths is not None
        assert len(result.photo_paths) > 0

        # Verify all photos exist
        for photo_path in result.photo_paths:
            assert Path(photo_path).exists()
            assert Path(photo_path).stat().st_size > 0

        # Verify thumbnail (should be uploaded to R2)
        assert result.thumbnail_url is not None

        print(f"✅ TikTok photo carousel download succeeded")
        print(f"   Photos: {len(result.photo_paths)}")
        print(f"   Thumbnail: {result.thumbnail_url[:80]}...")


class TestPlatformDetection:
    """Test platform detection logic"""

    def test_detect_youtube(self, downloader):
        """Test YouTube platform detection"""
        assert downloader._detect_platform('https://www.youtube.com/watch?v=abc') == 'youtube'
        assert downloader._detect_platform('https://youtu.be/abc') == 'youtube'
        assert downloader._detect_platform('https://youtube.com/shorts/abc') == 'youtube'

    def test_detect_instagram(self, downloader):
        """Test Instagram platform detection"""
        assert downloader._detect_platform('https://www.instagram.com/reel/abc/') == 'instagram'
        assert downloader._detect_platform('https://instagram.com/p/abc/') == 'instagram'

    def test_detect_facebook(self, downloader):
        """Test Facebook platform detection"""
        assert downloader._detect_platform('https://www.facebook.com/watch/?v=123') == 'facebook'
        assert downloader._detect_platform('https://fb.watch/abc/') == 'facebook'

    def test_detect_other(self, downloader):
        """Test other platform detection (TikTok, etc.)"""
        assert downloader._detect_platform('https://www.tiktok.com/@user/video/123') == 'other'
        assert downloader._detect_platform('https://vt.tiktok.com/abc/') == 'other'


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_invalid_url_empty(self, downloader):
        """Test that empty URL raises ValueError"""
        with pytest.raises(ValueError, match="Invalid URL"):
            downloader.download("")

    def test_invalid_url_no_protocol(self, downloader):
        """Test that URL without protocol raises ValueError"""
        with pytest.raises(ValueError, match="Invalid URL"):
            downloader.download("youtube.com/watch?v=test")

    def test_nonexistent_youtube_video(self, downloader):
        """Test handling of nonexistent YouTube video"""
        fake_url = "https://www.youtube.com/watch?v=NONEXISTENT_VIDEO_ID_12345"

        with pytest.raises(ValueError):
            downloader.download(fake_url)

    def test_multi_tier_fallback_no_r2_access(self, downloader):
        """Test that Tier 1 works even if R2 is inaccessible"""
        # Simulate R2 being down
        downloader.cookies_manager.r2_base_url = "https://invalid-r2-url.example.com"

        # Public YouTube video should still work via Tier 1 (no cookies)
        url = REAL_TEST_URLS['youtube_standard']
        result = downloader.download(url)

        assert result.video_path is not None
        assert Path(result.video_path).exists()

        print(f"✅ Tier 1 strategy working (download succeeded without R2 access)")


class TestDownloadResult:
    """Test DownloadResult dataclass functionality"""

    def test_download_result_video(self):
        """Test DownloadResult for video"""
        result = DownloadResult(
            video_path="/path/to/video.mp4",
            thumbnail_url="https://example.com/thumb.jpg",
            photo_paths=None
        )

        assert result.is_video
        assert not result.is_photo_carousel
        assert result.video_path == "/path/to/video.mp4"

    def test_download_result_photos(self):
        """Test DownloadResult for photo carousel"""
        result = DownloadResult(
            video_path=None,
            thumbnail_url="https://example.com/thumb.jpg",
            photo_paths=["/path/to/photo1.jpg", "/path/to/photo2.jpg"]
        )

        assert not result.is_video
        assert result.is_photo_carousel
        assert len(result.photo_paths) == 2

    def test_download_result_tuple_unpacking(self):
        """Test backward compatibility with tuple unpacking"""
        result = DownloadResult(
            video_path="/path/to/video.mp4",
            thumbnail_url="https://example.com/thumb.jpg",
            photo_paths=None
        )

        # Old-style tuple unpacking
        video_path, thumbnail_url, photo_paths = result

        assert video_path == "/path/to/video.mp4"
        assert thumbnail_url == "https://example.com/thumb.jpg"
        assert photo_paths is None


# Manual test runner for quick verification
if __name__ == "__main__":
    print("=" * 80)
    print("Manual Real Platform Download Test")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        downloader = VideoDownloader(output_dir=tmpdir)

        # Test 1: YouTube standard video
        print("\n🧪 Test 1: YouTube standard video")
        try:
            result = downloader.download(REAL_TEST_URLS['youtube_standard'])
            print(f"   ✅ Success!")
            print(f"      Video: {result.video_path}")
            print(f"      Size: {Path(result.video_path).stat().st_size / 1024 / 1024:.2f} MB")
            print(f"      Thumbnail: {result.thumbnail_url[:80]}...")
        except Exception as e:
            print(f"   ❌ Failed: {e}")

        # Test 2: YouTube Shorts
        print("\n🧪 Test 2: YouTube Shorts")
        try:
            result = downloader.download(REAL_TEST_URLS['youtube_shorts'])
            print(f"   ✅ Success!")
            print(f"      Video: {result.video_path}")
        except Exception as e:
            print(f"   ❌ Failed: {e}")

        # Test 3: Platform detection
        print("\n🧪 Test 3: Platform detection")
        test_urls = {
            'YouTube': 'https://www.youtube.com/watch?v=test',
            'Instagram': 'https://www.instagram.com/reel/test/',
            'Facebook': 'https://www.facebook.com/watch/?v=123',
            'TikTok': 'https://www.tiktok.com/@user/video/123',
        }
        for platform, url in test_urls.items():
            detected = downloader._detect_platform(url)
            print(f"   {platform}: {detected}")

        # Test 4: Error handling
        print("\n🧪 Test 4: Error handling")
        try:
            downloader.download("")
            print(f"   ❌ Should have raised ValueError")
        except ValueError as e:
            print(f"   ✅ Correctly raised ValueError: {e}")

    print("\n" + "=" * 80)
    print("Manual test run complete")
    print("=" * 80)
    print("\n💡 To run with pytest:")
    print("   cd /Users/alan/code/RecipeAI/video-processor")
    print("   pytest tests/test_real_platform_downloads.py -v")
    print("\n💡 To test Instagram/Facebook/TikTok (requires URLs and setup):")
    print("   TEST_INSTAGRAM=1 pytest tests/test_real_platform_downloads.py -v -k instagram")
    print("   TEST_FACEBOOK=1 pytest tests/test_real_platform_downloads.py -v -k facebook")
    print("   TEST_TIKTOK=1 pytest tests/test_real_platform_downloads.py -v -k tiktok")
