"""
Recipe Analyzer using Gemini Vision API
Analyzes cooking video frames to extract structured recipe information
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from PIL import Image
import google.generativeai as genai

logger = logging.getLogger(__name__)


class RecipeAnalyzer:
    """Analyzes video frames using Gemini Vision to extract recipe data"""

    SYSTEM_PROMPT = """分析這些烹飪影片畫面，提取完整食譜資訊。請用繁體中文輸出 JSON：

{
  "name": "菜名",
  "description": "簡短描述",
  "ingredients": [
    {"name": "食材名稱", "amount": "數量", "unit": "單位"}
  ],
  "steps": [
    {
      "step_number": 1,
      "description": "步驟說明",
      "duration_minutes": 5,
      "temperature": "溫度（如適用）"
    }
  ],
  "servings": 2,
  "prep_time": 10,
  "cook_time": 20,
  "tags": ["料理類型", "烹飪方式", "難度等級"],
  "completeness": "complete"
}

要求：
1. 食譜名稱必須是繁體中文
2. 食材必須包含名稱和份量，如果畫面中沒有明確顯示，請標記為 "適量"
3. 步驟必須按順序排列，包含關鍵的時間和溫度資訊
4. 如果資訊不完整（例如缺少步驟或食材），將 completeness 設為 "incomplete"
5. 標籤請從以下分類選擇：中式、日式、韓式、泰式、西式、快炒、燉煮、炸物、烘焙、甜點、簡易、進階

只回傳 JSON，不要其他說明文字。"""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """
        Initialize recipe analyzer

        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
            model_name: Gemini model to use (defaults to GEMINI_MODEL env var or gemini-2.5-flash)
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be provided or set in environment")

        self.model_name = model_name or os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)

        logger.info(f"RecipeAnalyzer initialized with model: {self.model_name}")

    def analyze_frames(self, frame_paths: List[str]) -> Dict[str, Any]:
        """
        Analyze video frames to extract recipe information

        Args:
            frame_paths: List of paths to frame images

        Returns:
            Parsed recipe JSON data

        Raises:
            ValueError: If frame_paths is empty or images cannot be loaded
            Exception: If API call fails or JSON parsing fails
        """
        if not frame_paths:
            raise ValueError("frame_paths cannot be empty")

        # Load images
        images = []
        for frame_path in frame_paths:
            try:
                img = Image.open(frame_path)
                images.append(img)
                logger.debug(f"Loaded frame: {frame_path}")
            except Exception as e:
                logger.error(f"Failed to load frame {frame_path}: {e}")
                raise ValueError(f"Cannot load image: {frame_path}")

        logger.info(f"Analyzing {len(images)} frames with Gemini Vision")

        # Call Gemini API with images
        try:
            response = self.model.generate_content([self.SYSTEM_PROMPT] + images)
            logger.debug(f"Gemini API response received")

            # Extract JSON from response
            recipe_data = self._parse_json_response(response.text)

            # Validate required fields
            self._validate_recipe_data(recipe_data)

            logger.info(f"Successfully extracted recipe: {recipe_data.get('name', 'Unknown')}")
            return recipe_data

        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON from Gemini response text

        Args:
            response_text: Raw response text from Gemini

        Returns:
            Parsed JSON object

        Raises:
            json.JSONDecodeError: If response is not valid JSON
        """
        # Try to extract JSON from response
        # Sometimes Gemini wraps JSON in markdown code blocks
        text = response_text.strip()

        # Remove markdown code blocks if present
        if text.startswith('```json'):
            text = text[7:]  # Remove ```json
        if text.startswith('```'):
            text = text[3:]  # Remove ```
        if text.endswith('```'):
            text = text[:-3]  # Remove trailing ```

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {text[:200]}...")
            raise ValueError(f"Invalid JSON response from Gemini: {e}")

    def _validate_recipe_data(self, data: Dict[str, Any]) -> None:
        """
        Validate that recipe data has required fields

        Args:
            data: Recipe data dictionary

        Raises:
            ValueError: If required fields are missing
        """
        required_fields = ['name', 'ingredients', 'steps']

        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        if not isinstance(data['ingredients'], list):
            raise ValueError("ingredients must be a list")

        if not isinstance(data['steps'], list):
            raise ValueError("steps must be a list")

        if len(data['ingredients']) == 0:
            logger.warning("Recipe has no ingredients, marking as incomplete")
            data['completeness'] = 'incomplete'

        if len(data['steps']) == 0:
            logger.warning("Recipe has no steps, marking as incomplete")
            data['completeness'] = 'incomplete'


# Convenience function for single-use analysis
def analyze_recipe_from_frames(
    frame_paths: List[str],
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze recipe from video frames

    Args:
        frame_paths: List of frame image paths
        api_key: Gemini API key (optional, uses env var if not provided)

    Returns:
        Parsed recipe data
    """
    analyzer = RecipeAnalyzer(api_key=api_key)
    return analyzer.analyze_frames(frame_paths)
