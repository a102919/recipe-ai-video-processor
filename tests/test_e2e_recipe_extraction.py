"""
End-to-End Tests for Recipe Extraction Pipeline

These tests run the complete workflow:
URL -> Download -> Frame Extraction -> Gemini Analysis -> Recipe

NOTE: These tests require:
- Valid GEMINI_API_KEY environment variable
- Internet connection for video download
- FFmpeg installed

Run with: pytest -v -m e2e
Skip with: pytest -v -m "not e2e"
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from src.pipeline import analyze_recipe_from_url


# Mark all tests in this module as e2e
pytestmark = pytest.mark.e2e


@pytest.fixture
def gemini_api_key():
    """Check if Gemini API key is available"""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set - skipping e2e test")
    return api_key


class TestE2ERecipeExtraction:
    """End-to-end tests for complete recipe extraction workflow"""

    @pytest.mark.skip(reason="Requires real video URL - update with actual test video")
    def test_full_pipeline_real_video(self, gemini_api_key):
        """
        Test complete pipeline with real video

        IMPORTANT: Replace the URL below with a real cooking video URL
        Use a SHORT video (10-30 seconds) to minimize API costs and test time
        """
        test_url = "https://youtube.com/shorts/EXAMPLE_SHORT_VIDEO_ID"

        # Execute full pipeline
        recipe = analyze_recipe_from_url(test_url, cleanup=True)

        # Verify recipe structure
        assert 'name' in recipe
        assert 'ingredients' in recipe
        assert 'steps' in recipe
        assert isinstance(recipe['ingredients'], list)
        assert isinstance(recipe['steps'], list)

        # Verify some content exists
        assert len(recipe['name']) > 0
        # Note: ingredients/steps might be empty for incomplete recipes

    @patch('src.pipeline.analyze_recipe_from_frames')
    @patch('src.pipeline.extract_key_frames')
    @patch('src.pipeline.download_video')
    def test_full_pipeline_mocked(
        self,
        mock_download,
        mock_extract,
        mock_analyze
    ):
        """
        Test pipeline with all stages mocked

        This test verifies the pipeline orchestration without
        requiring actual downloads or API calls
        """
        # Setup mocks
        mock_download.return_value = "/tmp/video.mp4"
        mock_extract.return_value = [
            "/tmp/frames/frame_0001.jpg",
            "/tmp/frames/frame_0002.jpg",
            "/tmp/frames/frame_0003.jpg"
        ]
        mock_analyze.return_value = {
            "name": "測試食譜",
            "description": "端到端測試用食譜",
            "ingredients": [
                {"name": "測試材料", "amount": "100", "unit": "g"}
            ],
            "steps": [
                {
                    "step_number": 1,
                    "description": "測試步驟",
                    "duration_minutes": 5
                }
            ],
            "servings": 2
        }

        # Execute pipeline
        recipe = analyze_recipe_from_url(
            "https://youtube.com/watch?v=test123",
            cleanup=True
        )

        # Verify all stages were called
        mock_download.assert_called_once()
        mock_extract.assert_called_once()
        mock_analyze.assert_called_once()

        # Verify result
        assert recipe["name"] == "測試食譜"
        assert len(recipe["ingredients"]) == 1
        assert len(recipe["steps"]) == 1

    @patch('src.pipeline.download_video')
    def test_pipeline_download_failure(self, mock_download):
        """Test pipeline handles download failures gracefully"""
        # Mock download failure
        mock_download.side_effect = ValueError("Invalid URL")

        # Execute and verify error handling
        with pytest.raises(ValueError, match="Invalid URL"):
            analyze_recipe_from_url("https://invalid.url/video")

    @patch('src.pipeline.download_video')
    @patch('src.pipeline.extract_key_frames')
    def test_pipeline_no_frames_extracted(self, mock_extract, mock_download):
        """Test pipeline handles case when no frames are extracted"""
        # Setup mocks
        mock_download.return_value = "/tmp/video.mp4"
        mock_extract.return_value = []  # No frames extracted

        # Execute and verify error handling
        with pytest.raises(ValueError, match="No frames extracted"):
            analyze_recipe_from_url("https://youtube.com/watch?v=test")

    @patch('src.pipeline.download_video')
    @patch('src.pipeline.extract_key_frames')
    @patch('src.pipeline.analyze_recipe_from_frames')
    @patch('shutil.rmtree')
    def test_pipeline_cleanup_enabled(
        self,
        mock_rmtree,
        mock_analyze,
        mock_extract,
        mock_download
    ):
        """Test pipeline cleans up temporary files when cleanup=True"""
        # Setup mocks
        mock_download.return_value = "/tmp/test/video.mp4"
        mock_extract.return_value = ["/tmp/test/frame1.jpg"]
        mock_analyze.return_value = {
            "name": "Test",
            "ingredients": [],
            "steps": []
        }

        # Execute with cleanup enabled
        analyze_recipe_from_url(
            "https://youtube.com/watch?v=test",
            cleanup=True
        )

        # Verify cleanup was called
        assert mock_rmtree.called

    @patch('src.pipeline.download_video')
    @patch('src.pipeline.extract_key_frames')
    @patch('src.pipeline.analyze_recipe_from_frames')
    @patch('shutil.rmtree')
    def test_pipeline_cleanup_disabled(
        self,
        mock_rmtree,
        mock_analyze,
        mock_extract,
        mock_download
    ):
        """Test pipeline keeps files when cleanup=False"""
        # Setup mocks
        mock_download.return_value = "/tmp/test/video.mp4"
        mock_extract.return_value = ["/tmp/test/frame1.jpg"]
        mock_analyze.return_value = {
            "name": "Test",
            "ingredients": [],
            "steps": []
        }

        # Execute with cleanup disabled
        analyze_recipe_from_url(
            "https://youtube.com/watch?v=test",
            cleanup=False
        )

        # Verify cleanup was NOT called
        mock_rmtree.assert_not_called()

    @patch('src.pipeline.download_video')
    @patch('src.pipeline.extract_key_frames')
    @patch('src.pipeline.analyze_recipe_from_frames')
    def test_pipeline_with_custom_api_key(
        self,
        mock_analyze,
        mock_extract,
        mock_download
    ):
        """Test pipeline passes custom API key to analyzer"""
        # Setup mocks
        mock_download.return_value = "/tmp/video.mp4"
        mock_extract.return_value = ["/tmp/frame1.jpg"]
        mock_analyze.return_value = {
            "name": "Test",
            "ingredients": [],
            "steps": []
        }

        custom_key = "custom-api-key-123"

        # Execute with custom API key
        analyze_recipe_from_url(
            "https://youtube.com/watch?v=test",
            api_key=custom_key
        )

        # Verify custom key was passed to analyzer
        mock_analyze.assert_called_once()
        call_kwargs = mock_analyze.call_args[1]
        assert call_kwargs.get('api_key') == custom_key
