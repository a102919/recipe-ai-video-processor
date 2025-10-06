"""
Unit tests for FrameExtractor
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.extractor import FrameExtractor, extract_key_frames


@pytest.fixture
def temp_dir():
    """Create temporary directory for test outputs"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_video_file(temp_dir):
    """Create mock video file"""
    video_path = Path(temp_dir) / "test_video.mp4"
    video_path.touch()
    return str(video_path)


@pytest.fixture
def mock_frames(temp_dir):
    """Create mock extracted frames"""
    frames_dir = Path(temp_dir) / "frames"
    frames_dir.mkdir()

    frame_paths = []
    for i in range(1, 21):  # 20 frames
        frame_path = frames_dir / f"frame_{i:04d}.jpg"
        frame_path.touch()
        frame_paths.append(str(frame_path))

    return frame_paths


class TestFrameExtractor:
    """Test FrameExtractor class"""

    def test_init_default_params(self):
        """Test initialization with default parameters"""
        extractor = FrameExtractor()
        assert extractor.max_frames == 180
        assert extractor.quality == 2

    def test_init_custom_params(self):
        """Test initialization with custom parameters"""
        extractor = FrameExtractor(max_frames=100, quality=5)
        assert extractor.max_frames == 100
        assert extractor.quality == 5

    @patch('subprocess.run')
    def test_extract_frames_success(self, mock_run, mock_video_file, temp_dir):
        """Test successful frame extraction"""
        # Setup mock
        mock_run.return_value = MagicMock(stderr="FFmpeg output", returncode=0)

        # Create mock output frames
        output_dir = Path(temp_dir) / "output"
        output_dir.mkdir()
        for i in range(1, 13):
            (output_dir / f"frame_{i:04d}.jpg").touch()

        extractor = FrameExtractor()
        frames = extractor.extract_frames(mock_video_file, str(output_dir))

        # Verify FFmpeg was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert 'ffmpeg' in call_args
        assert '-i' in call_args
        assert 'fps=1' in call_args

        # Verify frames were found
        assert len(frames) == 12

    def test_extract_frames_video_not_found(self, temp_dir):
        """Test extraction with non-existent video file"""
        extractor = FrameExtractor()

        with pytest.raises(FileNotFoundError, match="Video file not found"):
            extractor.extract_frames("/nonexistent/video.mp4", temp_dir)

    @patch('subprocess.run')
    def test_extract_frames_ffmpeg_fails(self, mock_run, mock_video_file, temp_dir):
        """Test handling of FFmpeg failure"""
        # Mock FFmpeg failure
        mock_run.side_effect = Exception("FFmpeg error")

        extractor = FrameExtractor()

        with pytest.raises(Exception, match="FFmpeg error"):
            extractor.extract_frames(mock_video_file, temp_dir)

    def test_select_key_frames_less_than_target(self):
        """Test key frame selection when total frames < target count"""
        extractor = FrameExtractor()
        frames = [f"frame_{i}.jpg" for i in range(10)]

        selected = extractor.select_key_frames(frames, count=12)

        # Should return all frames when less than target
        assert selected == frames
        assert len(selected) == 10

    def test_select_key_frames_more_than_target(self):
        """Test key frame selection with evenly distributed sampling"""
        extractor = FrameExtractor()
        frames = [f"frame_{i:04d}.jpg" for i in range(1, 181)]  # 180 frames

        selected = extractor.select_key_frames(frames, count=12)

        # Should return exactly 12 frames
        assert len(selected) == 12

        # Verify even distribution (every 15th frame: 180/12 = 15)
        expected_indices = [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165]
        for i, expected_idx in enumerate(expected_indices):
            assert selected[i] == frames[expected_idx]

    def test_select_key_frames_empty_list(self):
        """Test key frame selection with empty list"""
        extractor = FrameExtractor()
        selected = extractor.select_key_frames([], count=12)

        assert selected == []

    @patch.object(FrameExtractor, 'extract_frames')
    @patch.object(FrameExtractor, 'select_key_frames')
    def test_extract_and_select(self, mock_select, mock_extract, mock_video_file, temp_dir):
        """Test combined extract and select workflow"""
        # Setup mocks
        all_frames = [f"frame_{i:04d}.jpg" for i in range(1, 181)]
        key_frames = all_frames[::15]  # Every 15th frame

        mock_extract.return_value = all_frames
        mock_select.return_value = key_frames

        # Execute
        extractor = FrameExtractor()
        result = extractor.extract_and_select(mock_video_file, temp_dir, key_frame_count=12)

        # Verify workflow
        mock_extract.assert_called_once_with(mock_video_file, temp_dir)
        mock_select.assert_called_once_with(all_frames, 12)
        assert result == key_frames


class TestConvenienceFunction:
    """Test convenience function"""

    @patch.object(FrameExtractor, 'extract_and_select')
    def test_extract_key_frames(self, mock_method):
        """Test extract_key_frames convenience function"""
        expected_frames = [f"frame_{i}.jpg" for i in range(12)]
        mock_method.return_value = expected_frames

        result = extract_key_frames("/path/to/video.mp4", "/tmp/output", count=12)

        assert result == expected_frames
        mock_method.assert_called_once_with("/path/to/video.mp4", "/tmp/output", 12)
