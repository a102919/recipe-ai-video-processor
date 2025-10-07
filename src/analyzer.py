"""
Recipe Analyzer using Gemini Vision API
Analyzes cooking video frames to extract structured recipe information
"""
import os
import json
import re
import logging
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
from PIL import Image
import google.generativeai as genai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

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
  "tags": ["料理類型", "烹飪方式", "難度等級"]
}

要求：
1. 食譜名稱必須是繁體中文
2. 食材必須包含名稱和份量，如果畫面中沒有明確顯示，請標記為 "適量"
3. 步驟必須按順序排列，包含關鍵的時間和溫度資訊
4. 標籤請從以下分類選擇：中式、日式、韓式、泰式、西式、快炒、燉煮、炸物、烘焙、甜點、簡易、進階

只回傳 JSON，不要其他說明文字。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: int = 60,
        max_retries: int = 3
    ):
        """
        Initialize recipe analyzer

        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
            model_name: Gemini model to use (defaults to GEMINI_MODEL env var or gemini-2.5-flash)
            timeout_seconds: Timeout for API calls in seconds (default: 60)
            max_retries: Maximum number of retry attempts (default: 3)
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be provided or set in environment")

        self.model_name = model_name or os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            self.model_name,
            generation_config={
                'temperature': 0.7
            }
        )
        # Note: timeout is handled by the underlying HTTP client (default 60s)
        # Combined with tenacity retry mechanism for resilience

        logger.info(
            f"RecipeAnalyzer initialized: model={self.model_name}, "
            f"timeout={timeout_seconds}s, max_retries={max_retries}"
        )

    def _call_gemini_api_with_retry(self, images: List[Any]) -> Any:
        """
        Call Gemini API with retry mechanism

        Args:
            images: List of PIL Image objects

        Returns:
            Gemini API response

        Raises:
            Exception: If all retry attempts fail
        """
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((
                Exception,  # Retry on any exception
            )),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def _api_call():
            start_time = time.time()
            try:
                logger.debug(f"Calling Gemini API with {len(images)} images")
                response = self.model.generate_content([self.SYSTEM_PROMPT] + images)
                elapsed = time.time() - start_time
                logger.info(f"Gemini API call succeeded in {elapsed:.2f}s")
                return response
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(
                    f"Gemini API call failed after {elapsed:.2f}s: "
                    f"{type(e).__name__}: {str(e)}"
                )
                raise

        return _api_call()

    def analyze_frames(self, frame_paths: List[str]) -> Dict[str, Any]:
        """
        Analyze video frames to extract recipe information

        Args:
            frame_paths: List of paths to frame images

        Returns:
            Dictionary containing recipe data and metadata

        Raises:
            ValueError: If frame_paths is empty or images cannot be loaded
            Exception: If API call fails after all retries or JSON parsing fails
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

        # Call Gemini API with retry mechanism
        try:
            response = self._call_gemini_api_with_retry(images)

            # Extract usage metadata for cost tracking
            usage_metadata = {
                'prompt_tokens': response.usage_metadata.prompt_token_count,
                'output_tokens': response.usage_metadata.candidates_token_count,
                'total_tokens': response.usage_metadata.total_token_count
            }
            logger.info(f"Token usage: {usage_metadata['total_tokens']} tokens")

            # Extract JSON from response
            recipe_data = self._parse_json_response(response.text)

            # Validate required fields
            self._validate_recipe_data(recipe_data)

            logger.info(f"Successfully extracted recipe: {recipe_data.get('name', 'Unknown')}")

            # Return both recipe data and usage metadata
            return {
                'recipe': recipe_data,
                'usage_metadata': usage_metadata
            }

        except Exception as e:
            logger.error(
                f"Recipe extraction failed after {self.max_retries} attempts: "
                f"{type(e).__name__}: {str(e)}",
                exc_info=True
            )
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
        # Remove markdown code blocks (```json or ```) using regex
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', response_text.strip(), flags=re.MULTILINE).strip()

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
            logger.warning("Recipe has no ingredients")

        if len(data['steps']) == 0:
            logger.warning("Recipe has no steps")


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
        Dictionary containing:
        - recipe: Parsed recipe data (ingredients, steps, etc.)
        - usage_metadata: Token usage statistics (prompt_tokens, output_tokens, total_tokens)
    """
    analyzer = RecipeAnalyzer(api_key=api_key)
    return analyzer.analyze_frames(frame_paths)
