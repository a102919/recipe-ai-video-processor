"""
Unit tests for RecipeAnalyzer
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image
from src.analyzer import RecipeAnalyzer, analyze_recipe_from_frames


@pytest.fixture
def mock_frames(tmp_path):
    """Create mock frame images"""
    frame_paths = []
    for i in range(1, 13):
        frame_path = tmp_path / f"frame_{i:04d}.jpg"
        # Create a simple 100x100 RGB image
        img = Image.new('RGB', (100, 100), color=(73, 109, 137))
        img.save(frame_path)
        frame_paths.append(str(frame_path))
    return frame_paths


@pytest.fixture
def valid_recipe_json():
    """Sample valid recipe JSON response"""
    return {
        "name": "蒜香奶油蝦",
        "description": "簡單美味的快炒海鮮料理",
        "ingredients": [
            {"name": "蝦子", "amount": "300", "unit": "g"},
            {"name": "蒜頭", "amount": "5", "unit": "瓣"},
            {"name": "奶油", "amount": "30", "unit": "g"}
        ],
        "steps": [
            {
                "step_number": 1,
                "description": "蝦子去殼去腸泥",
                "duration_minutes": 5
            },
            {
                "step_number": 2,
                "description": "蒜頭切末",
                "duration_minutes": 2
            },
            {
                "step_number": 3,
                "description": "熱鍋加入奶油，爆香蒜末，加入蝦子快炒至變色",
                "duration_minutes": 5,
                "temperature": "中大火"
            }
        ],
        "servings": 2,
        "prep_time": 7,
        "cook_time": 5,
        "tags": ["海鮮", "快炒", "簡易"]
    }


class TestRecipeAnalyzer:
    """Test RecipeAnalyzer class"""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key"""
        analyzer = RecipeAnalyzer(api_key="test-api-key-123")
        assert analyzer.api_key == "test-api-key-123"
        assert analyzer.model_name == "gemini-2.5-flash"

    def test_init_with_env_var(self, monkeypatch):
        """Test initialization with environment variable"""
        monkeypatch.setenv("GEMINI_API_KEY", "env-api-key-456")
        analyzer = RecipeAnalyzer()
        assert analyzer.api_key == "env-api-key-456"

    def test_init_no_api_key(self, monkeypatch):
        """Test initialization fails without API key"""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="GEMINI_API_KEY must be provided"):
            RecipeAnalyzer()

    def test_init_custom_model(self):
        """Test initialization with custom model name"""
        analyzer = RecipeAnalyzer(api_key="test-key", model_name="gemini-2.5-pro")
        assert analyzer.model_name == "gemini-2.5-pro"

    @patch('google.generativeai.GenerativeModel')
    def test_analyze_frames_success(self, mock_model_class, mock_frames, valid_recipe_json):
        """Test successful frame analysis"""
        # Setup mock
        mock_model = MagicMock()
        mock_response = MagicMock()
        import json
        mock_response.text = f'```json\n{json.dumps(valid_recipe_json)}\n```'
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        # Execute
        analyzer = RecipeAnalyzer(api_key="test-key")
        analyzer.model = mock_model  # Replace with mock

        result = analyzer.analyze_frames(mock_frames)

        # Verify
        assert result["name"] == "蒜香奶油蝦"
        assert len(result["ingredients"]) == 3
        assert len(result["steps"]) == 3

        # Verify API was called with correct number of images
        mock_model.generate_content.assert_called_once()
        call_args = mock_model.generate_content.call_args[0][0]
        assert len(call_args) == 13  # Prompt + 12 images

    def test_analyze_frames_empty_list(self):
        """Test analysis fails with empty frame list"""
        analyzer = RecipeAnalyzer(api_key="test-key")

        with pytest.raises(ValueError, match="frame_paths cannot be empty"):
            analyzer.analyze_frames([])

    def test_analyze_frames_invalid_image(self, tmp_path):
        """Test analysis fails with invalid image file"""
        invalid_frame = tmp_path / "invalid.jpg"
        invalid_frame.write_text("not an image")

        analyzer = RecipeAnalyzer(api_key="test-key")

        with pytest.raises(ValueError, match="Cannot load image"):
            analyzer.analyze_frames([str(invalid_frame)])

    def test_parse_json_response_plain_json(self):
        """Test parsing plain JSON response"""
        analyzer = RecipeAnalyzer(api_key="test-key")
        json_str = '{"name": "Test", "ingredients": [], "steps": []}'

        result = analyzer._parse_json_response(json_str)

        assert result["name"] == "Test"

    def test_parse_json_response_with_markdown(self):
        """Test parsing JSON wrapped in markdown code blocks"""
        analyzer = RecipeAnalyzer(api_key="test-key")
        json_str = '```json\n{"name": "Test", "ingredients": [], "steps": []}\n```'

        result = analyzer._parse_json_response(json_str)

        assert result["name"] == "Test"

    def test_parse_json_response_invalid_json(self):
        """Test parsing invalid JSON raises error"""
        analyzer = RecipeAnalyzer(api_key="test-key")
        invalid_json = "not valid json at all"

        with pytest.raises(ValueError, match="Invalid JSON response"):
            analyzer._parse_json_response(invalid_json)

    def test_validate_recipe_data_valid(self, valid_recipe_json):
        """Test validation passes for valid recipe data"""
        analyzer = RecipeAnalyzer(api_key="test-key")

        # Should not raise exception
        analyzer._validate_recipe_data(valid_recipe_json)

    def test_validate_recipe_data_missing_name(self):
        """Test validation fails when name is missing"""
        analyzer = RecipeAnalyzer(api_key="test-key")
        invalid_data = {"ingredients": [], "steps": []}

        with pytest.raises(ValueError, match="Missing required field: name"):
            analyzer._validate_recipe_data(invalid_data)

    def test_validate_recipe_data_missing_ingredients(self):
        """Test validation fails when ingredients is missing"""
        analyzer = RecipeAnalyzer(api_key="test-key")
        invalid_data = {"name": "Test", "steps": []}

        with pytest.raises(ValueError, match="Missing required field: ingredients"):
            analyzer._validate_recipe_data(invalid_data)

class TestConvenienceFunction:
    """Test convenience function"""

    @patch.object(RecipeAnalyzer, 'analyze_frames')
    def test_analyze_recipe_from_frames(self, mock_method, valid_recipe_json):
        """Test analyze_recipe_from_frames convenience function"""
        mock_method.return_value = valid_recipe_json

        result = analyze_recipe_from_frames(
            ["frame1.jpg", "frame2.jpg"],
            api_key="test-key"
        )

        assert result == valid_recipe_json
        mock_method.assert_called_once()
