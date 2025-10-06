"""
Unit tests for VideoDownloader
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.downloader import VideoDownloader, download_video


@pytest.fixture
def temp_dir():
    """Create temporary directory for test outputs"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


class TestVideoDownloader:
    """Test VideoDownloader class"""

    def test_init_default_dir(self):
        """Test initialization with default directory"""
        downloader = VideoDownloader()
        assert downloader.output_dir is not None
        assert Path(downloader.output_dir).exists()

    def test_init_custom_dir(self, temp_dir):
        """Test initialization with custom directory"""
        downloader = VideoDownloader(output_dir=temp_dir)
        assert downloader.output_dir == temp_dir
        assert Path(temp_dir).exists()

    def test_download_invalid_url_empty(self):
        """Test download fails with empty URL"""
        downloader = VideoDownloader()

        with pytest.raises(ValueError, match="Invalid URL"):
            downloader.download("")

    def test_download_invalid_url_no_protocol(self):
        """Test download fails with URL without protocol"""
        downloader = VideoDownloader()

        with pytest.raises(ValueError, match="Invalid URL"):
            downloader.download("youtube.com/watch?v=test")

    @patch('yt_dlp.YoutubeDL')
    def test_download_success(self, mock_ydl_class, temp_dir):
        """Test successful video download"""
        # Setup mock
        mock_ydl = MagicMock()
        mock_info = {
            'id': 'test123',
            'ext': 'mp4',
            'title': 'Test Cooking Video',
            'thumbnail': 'https://example.com/thumb.jpg'
        }
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        # Create expected output file
        expected_path = Path(temp_dir) / "video_test123.mp4"
        expected_path.touch()

        # Execute
        downloader = VideoDownloader(output_dir=temp_dir)
        video_path, thumbnail_url = downloader.download("https://youtube.com/watch?v=test123")

        # Verify
        assert video_path == str(expected_path)
        assert thumbnail_url == 'https://example.com/thumb.jpg'
        mock_ydl.extract_info.assert_called_once_with(
            "https://youtube.com/watch?v=test123",
            download=True
        )

    @patch('yt_dlp.YoutubeDL')
    def test_download_custom_prefix(self, mock_ydl_class, temp_dir):
        """Test download with custom filename prefix"""
        # Setup mock
        mock_ydl = MagicMock()
        mock_info = {'id': 'abc456', 'ext': 'mp4', 'thumbnail': None}
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        # Create expected output file
        expected_path = Path(temp_dir) / "cooking_abc456.mp4"
        expected_path.touch()

        # Execute
        downloader = VideoDownloader(output_dir=temp_dir)
        video_path, thumbnail_url = downloader.download(
            "https://youtube.com/watch?v=abc456",
            filename_prefix="cooking"
        )

        # Verify
        assert video_path == str(expected_path)
        assert "cooking_" in video_path
        assert thumbnail_url is None

    @patch('yt_dlp.YoutubeDL')
    def test_download_no_info_extracted(self, mock_ydl_class, temp_dir):
        """Test download fails when no info extracted"""
        # Setup mock to return None
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = None
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        # Execute
        downloader = VideoDownloader(output_dir=temp_dir)

        with pytest.raises(ValueError, match="Failed to extract video info"):
            downloader.download("https://youtube.com/watch?v=invalid")

    @patch('yt_dlp.YoutubeDL')
    def test_download_file_not_created(self, mock_ydl_class, temp_dir):
        """Test download fails when file is not created"""
        # Setup mock - returns info but file doesn't exist
        mock_ydl = MagicMock()
        mock_info = {'id': 'test999', 'ext': 'mp4'}
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        # Don't create the file - simulate download failure

        # Execute
        downloader = VideoDownloader(output_dir=temp_dir)

        with pytest.raises(Exception, match="Download succeeded but file not found"):
            downloader.download("https://youtube.com/watch?v=test999")

    @patch('yt_dlp.YoutubeDL')
    def test_download_ydl_error(self, mock_ydl_class, temp_dir):
        """Test download handles yt-dlp errors"""
        import yt_dlp

        # Setup mock to raise DownloadError
        mock_ydl = MagicMock()
        mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError("Video unavailable")
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        # Execute
        downloader = VideoDownloader(output_dir=temp_dir)

        with pytest.raises(ValueError, match="Failed to download video"):
            downloader.download("https://youtube.com/watch?v=unavailable")


class TestConvenienceFunction:
    """Test convenience function"""

    @patch.object(VideoDownloader, 'download')
    def test_download_video(self, mock_method, temp_dir):
        """Test download_video convenience function"""
        mock_method.return_value = ("/path/to/video.mp4", "https://example.com/thumb.jpg")

        video_path, thumbnail_url = download_video(
            "https://youtube.com/watch?v=test",
            output_dir=temp_dir
        )

        assert video_path == "/path/to/video.mp4"
        assert thumbnail_url == "https://example.com/thumb.jpg"
        mock_method.assert_called_once_with("https://youtube.com/watch?v=test")
