"""
Recipe Analyzer using LangChain with multiple LLM providers
Analyzes cooking video frames to extract structured recipe information
Supports: Gemini, Grok (xAI), OpenAI with automatic fallback
"""
import os
import json
import re
import logging
import time
import requests
import tempfile
import base64
from typing import List, Dict, Any, Optional
from pathlib import Path
from PIL import Image
from io import BytesIO
from langchain_core.messages import HumanMessage
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

try:
    from .llm_config import get_llm_manager
except ImportError:
    from llm_config import get_llm_manager

logger = logging.getLogger(__name__)


class RecipeAnalyzer:
    """Analyzes video frames using Gemini Vision to extract recipe data"""

    SYSTEM_PROMPT = """分析這些圖片，提取完整資訊並以「食譜格式」輸出 JSON。請用繁體中文與台灣用詞。

重要說明：
- 第一張圖是影片的封面圖片，可能包含標題、成品照片或重要資訊
- 後續圖片是影片的關鍵幀，展示過程細節

**核心原則：萬物皆可成為「食譜」**
- 如果是烹飪影片 → 提取真實食譜

**輸出格式**：
{
  "name": "菜名或主題名稱",
  "description": "簡短描述",
  "ingredients": [
    {"name": "材料名稱", "amount": "數量", "unit": "單位"}
  ],
  "steps": [
    {
      "step_number": 1,
      "description": "中火熱鍋，倒入 1 大匙油，放入蒜末爆香至微黃色",
      "duration_minutes": 2,
      "temperature": "中火",
      "tips": ["蒜末不要炒焦，微黃即可", "油溫約 150°C 時下蒜末"]
    }
  ],
  "servings": 2,
  "prep_time": 10,
  "cook_time": 20,
  "tags": ["標籤"]
}

**格式要求**：
1. name：食譜名稱必須是繁體中文，而且是台灣用詞
2. description：一句話，不超過20字
3. steps 的 description：直接描述動作，不加「步驟一」等前綴
4. tips：實用建議，避免空話
5. tags：烹飪類（中式、日式、韓式、泰式、西式、快炒、燉煮、炸物、烘焙、甜點、簡易、進階）或非烹飪類（生活、寵物、自然、藝術、運動、療癒、創意、趣味）
6. **永遠返回 JSON，絕不返回文字說明**
7. 食材必須包含名稱和份量，如果畫面中沒有明確顯示，請標記為 "適量"
8. 步驟必須按順序排列，包含關鍵的時間和溫度資訊，並在 `tips` 欄位中補充說明關鍵訣竅
9. **家庭料理級別詳細要求**：
   - 步驟 description 必須包含：火候（大火/中火/小火/文火）+ 具體時間（「2-3 分鐘」而非「幾分鐘」）+ 觀察指標（「肉變金黃」、「水分收乾」等）
   - tips 必須包含：成功關鍵（為什麼這樣做）+ 常見錯誤提醒
   - 例：「翻炒均勻」❌ vs 「中火翻炒 2-3 分鐘，至肉變金黃色」✅

只回傳 JSON，不要其他說明文字。"""

    SINGLE_IMAGE_ADDITIONAL_PROMPT = """

**特別注意：當前只提供一張成品照片**

由於沒有烹飪過程的畫面，請根據成品照片推斷完整的烹飪流程：

1. **食材辨識**：分析成品中包含哪些食材的原始形態
   - 例如：看到蒲燒鰻魚 → 原料是新鮮鰻魚
   - 例如：看到白飯 → 原料是生米

2. **食材處理步驟**：推斷每種食材需要的前處理
   - 清洗、去骨、切割、醃製等
   - 必須描述具體動作和技巧

3. **烹飪方法推斷**：根據成品狀態推斷烹飪手法
   - 煎、炒、煮、蒸、烤、炸等
   - 包含火候、時間、溫度

4. **烹飪順序**：按合理的烹飪邏輯排列步驟
   - 先處理需時較長的食材
   - 再處理配菜和醬汁
   - 最後才是組裝和擺盤

**嚴格要求**：
- 步驟必須從「處理原始食材」開始，絕不能從「擺盤」或「組裝」開始
- 每個步驟應描述具體的烹飪動作，不能只寫「將XX切片」這種過於簡化的描述
- 必須包含關鍵的烹飪技巧和注意事項在 `tips` 欄位中
"""

    QUICK_NAME_ONLY_PROMPT = """分析這張圖片，只提取「菜名」，不要提供完整食譜。

**重要說明：**
- 這是影片的縮圖或成品照片
- 只需要辨識菜名，不需要食材或步驟

**輸出格式**：
{
  "name": "菜名（繁體中文，台灣用詞）"
}

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
            api_key: DEPRECATED - API keys are now managed via environment variables
            model_name: DEPRECATED - Model selection handled automatically
            timeout_seconds: Timeout for API calls in seconds (default: 60)
            max_retries: Maximum number of retry attempts (default: 3)
        """
        # Legacy parameters ignored (kept for backward compatibility)
        if api_key:
            logger.warning(
                "api_key parameter is deprecated. "
                "Use GEMINI_API_KEYS, GROK_API_KEYS, or OPENAI_API_KEYS environment variables."
            )
        if model_name:
            logger.warning("model_name parameter is deprecated. Model selection is automatic.")

        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        # Get LLM manager (handles multiple providers)
        try:
            self.llm_manager = get_llm_manager()
            logger.info(
                f"RecipeAnalyzer initialized with LangChain: "
                f"timeout={timeout_seconds}s, max_retries={max_retries}"
            )
            logger.info(f"Provider chain: {self.llm_manager.get_provider_metadata()}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM manager: {e}")
            raise ValueError(
                "Failed to initialize LLM providers. "
                "Please configure at least one of: GEMINI_API_KEYS, GROK_API_KEYS, OPENAI_API_KEYS"
            )

    def _image_to_base64(self, image: Image.Image) -> str:
        """
        Convert PIL Image to base64 string for LangChain

        Args:
            image: PIL Image object

        Returns:
            Base64-encoded image string with data URI prefix
        """
        buffered = BytesIO()
        # Convert to RGB if needed (handle RGBA, grayscale, etc.)
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        image.save(buffered, format="JPEG", quality=85)
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/jpeg;base64,{img_str}"

    def _call_llm_api_with_retry(
        self,
        images: List[Image.Image],
        is_single_image: bool = False,
        existing_recipe_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call LLM API with retry mechanism (supports multiple providers)

        Args:
            images: List of PIL Image objects
            is_single_image: True if analyzing single product photo (requires inference)
            existing_recipe_context: Optional previous analysis results for reanalysis context

        Returns:
            Dict with response text and metadata

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
                # Convert images to base64
                image_contents = [
                    {"type": "image_url", "image_url": {"url": self._image_to_base64(img)}}
                    for img in images
                ]

                # Select prompt based on image count
                if is_single_image:
                    prompt_text = self.SYSTEM_PROMPT + self.SINGLE_IMAGE_ADDITIONAL_PROMPT
                    logger.info("Using single-image prompt (with inference guidance)")
                else:
                    prompt_text = self.SYSTEM_PROMPT
                    logger.info("Using multi-image prompt (process-based)")

                # Add previous analysis context if reanalysis
                if existing_recipe_context:
                    logger.info("Adding previous analysis context for improved accuracy")
                    context_prompt = f"""

**重新解析模式：參考先前的分析結果**

以下是先前對這個影片的分析結果，請參考這些資訊，並根據影片內容提供更準確、更詳細的改進版本：

先前的分析結果：
```json
{json.dumps(existing_recipe_context, ensure_ascii=False, indent=2)}
```

**重新解析要求：**
1. 仔細比對影片內容與先前分析，修正任何不準確的地方
2. 補充先前遺漏的食材或步驟細節
3. 改進步驟描述的清晰度和可操作性
4. 如果先前分析已經很準確，可以保持相同內容但提供更詳細的說明
5. 保持 JSON 格式輸出，不要返回文字說明

請輸出改進後的完整食譜 JSON。
"""
                    prompt_text += context_prompt

                # Build message
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": prompt_text},
                        *image_contents
                    ]
                )

                # Get LLM model (with automatic fallback)
                model = self.llm_manager.get_primary_model()

                # Call LLM
                logger.debug(f"Calling LLM API with {len(images)} images")
                response = model.invoke([message])

                elapsed = time.time() - start_time
                provider_info = self.llm_manager.get_provider_metadata()
                logger.info(
                    f"LLM API call succeeded in {elapsed:.2f}s "
                    f"(provider: {provider_info['primary_provider']})"
                )

                # Extract token usage from response metadata
                token_usage = {}

                # Try new-style usage_metadata first (LangChain 0.3+)
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    usage = response.usage_metadata
                    # usage_metadata is a dict, not an object
                    if isinstance(usage, dict):
                        token_usage = {
                            'prompt_tokens': usage.get('input_tokens', 0),
                            'output_tokens': usage.get('output_tokens', 0),
                            'total_tokens': usage.get('total_tokens', 0)
                        }
                    else:
                        # Fallback to getattr for object-style usage
                        token_usage = {
                            'prompt_tokens': getattr(usage, 'input_tokens', 0),
                            'output_tokens': getattr(usage, 'output_tokens', 0),
                            'total_tokens': getattr(usage, 'total_tokens', 0)
                        }
                # Fallback to response_metadata (older style)
                elif hasattr(response, 'response_metadata') and response.response_metadata:
                    metadata = response.response_metadata
                    # Gemini format
                    if 'usage_metadata' in metadata:
                        usage = metadata['usage_metadata']
                        token_usage = {
                            'prompt_tokens': usage.get('prompt_token_count', 0),
                            'output_tokens': usage.get('candidates_token_count', 0),
                            'total_tokens': usage.get('total_token_count', 0)
                        }
                    # OpenAI format
                    elif 'token_usage' in metadata:
                        usage = metadata['token_usage']
                        token_usage = {
                            'prompt_tokens': usage.get('prompt_tokens', 0),
                            'output_tokens': usage.get('completion_tokens', 0),
                            'total_tokens': usage.get('total_tokens', 0)
                        }

                logger.info(f"Token usage: {token_usage.get('total_tokens', 0)} total tokens")

                # Return response text and metadata
                return {
                    'text': response.content,
                    'provider': provider_info['primary_provider'],
                    'provider_metadata': provider_info,
                    'token_usage': token_usage
                }
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(
                    f"LLM API call failed after {elapsed:.2f}s: "
                    f"{type(e).__name__}: {str(e)}"
                )
                raise

        return _api_call()

    def _load_thumbnail(self, thumbnail_url: str) -> Optional[Image.Image]:
        """
        Load thumbnail image from URL or local path

        Args:
            thumbnail_url: URL or local file path to thumbnail

        Returns:
            PIL Image object or None if loading fails
        """
        try:
            # Check if it's a local file path
            if os.path.exists(thumbnail_url):
                logger.info(f"Loading thumbnail from local path: {thumbnail_url}")
                img = Image.open(thumbnail_url)
                logger.info(f"Successfully loaded thumbnail from local file")
                return img

            # Otherwise treat as HTTP(S) URL
            if thumbnail_url.startswith(('http://', 'https://')):
                logger.info(f"Downloading thumbnail from URL: {thumbnail_url[:80]}...")
                response = requests.get(thumbnail_url, timeout=30)
                response.raise_for_status()

                # Save to temporary file and load
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                    tmp_file.write(response.content)
                    tmp_path = tmp_file.name

                img = Image.open(tmp_path)
                # Clean up temp file
                os.unlink(tmp_path)
                logger.info(f"Successfully downloaded and loaded thumbnail")
                return img
            else:
                logger.warning(f"Invalid thumbnail path/URL: {thumbnail_url}")
                return None
        except Exception as e:
            logger.error(f"Failed to load thumbnail from {thumbnail_url}: {e}")
            return None

    def analyze_frames(
        self,
        frame_paths: List[str],
        thumbnail_url: Optional[str] = None,
        is_incremental: bool = False,
        existing_recipe_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze video frames to extract recipe information

        Args:
            frame_paths: List of paths to frame images
            thumbnail_url: Optional URL or path to video thumbnail/cover image
                          If provided, this will be inserted as the first image for analysis
            is_incremental: If True, use supplementary analysis prompt
            existing_recipe_context: Existing recipe data for incremental context

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

        try:
            # Load thumbnail first if provided
            if thumbnail_url:
                logger.info(f"Loading thumbnail image from: {thumbnail_url[:80]}...")
                thumbnail_img = self._load_thumbnail(thumbnail_url)
                if thumbnail_img:
                    images.append(thumbnail_img)
                    logger.info(f"Added thumbnail as first image for analysis")
                else:
                    logger.warning(f"Failed to load thumbnail, proceeding with frames only")

            # Load video frames
            for frame_path in frame_paths:
                try:
                    img = Image.open(frame_path)
                    images.append(img)
                    logger.debug(f"Loaded frame: {frame_path}")
                except Exception as e:
                    logger.error(f"Failed to load frame {frame_path}: {e}")
                    raise ValueError(f"Cannot load image: {frame_path}")

            logger.info(f"Analyzing {len(images)} images with LLM (including thumbnail: {thumbnail_url is not None and len(images) > len(frame_paths)})")

            # Determine if this is a single product photo (requires inference)
            is_single_image = len(images) == 1
            if is_single_image:
                logger.info("Detected single image - will use inference-based prompt")

            # Call LLM API with retry mechanism (supports multiple providers)
            # Pass existing_recipe_context for reanalysis context
            response = self._call_llm_api_with_retry(
                images,
                is_single_image=is_single_image,
                existing_recipe_context=existing_recipe_context
            )

            # Extract usage metadata for cost tracking
            token_usage = response.get('token_usage', {})
            usage_metadata = {
                'provider': response['provider'],
                'provider_metadata': response['provider_metadata'],
                # Flattened token fields (no nested format)
                **token_usage
            }
            logger.info(f"Used provider: {response['provider']}")
            if token_usage.get('total_tokens'):
                logger.info(f"Token usage: {token_usage['total_tokens']} total ({token_usage.get('prompt_tokens', 0)} prompt + {token_usage.get('output_tokens', 0)} output)")

            # Extract JSON from response
            recipe_data = self._parse_json_response(response['text'])

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

        finally:
            # CRITICAL: Close all PIL Image objects to free file handles and memory
            for img in images:
                try:
                    img.close()
                except Exception as e:
                    logger.warning(f"Failed to close image: {e}")

            # Clear images list to help garbage collector
            images.clear()
            logger.debug(f"Closed {len(frame_paths)} image file handles")

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response text with creative fallback

        Args:
            response_text: Raw response text from LLM

        Returns:
            Parsed JSON object (or creative default if LLM refuses)

        Note:
            If LLM returns non-JSON despite instructions, creates a meta-recipe
            about "how to analyze mysterious images" for user entertainment
        """
        # Try to extract JSON from response
        # Sometimes LLMs wrap JSON in markdown code blocks
        # Remove markdown code blocks (```json or ```) using regex
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', response_text.strip(), flags=re.MULTILINE).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"LLM returned non-JSON response, using creative fallback: {text[:200]}...")

            # Extract key phrases from LLM's text response for creative fallback
            # This turns "LLM refused to generate recipe" into an entertaining meta-recipe
            return {
                "name": "神秘圖片分析指南",
                "description": "當 AI 也不知道該說什麼的時候",
                "ingredients": [
                    {"name": "好奇心", "amount": "1", "unit": "份"},
                    {"name": "想像力", "amount": "適量", "unit": ""},
                    {"name": "開放的心態", "amount": "滿滿的", "unit": ""}
                ],
                "steps": [
                    {
                        "step_number": 1,
                        "description": "仔細觀察圖片中的每個細節",
                        "duration_minutes": 2,
                        "temperature": "室溫",
                        "tips": ["放輕鬆，沒有標準答案"]
                    },
                    {
                        "step_number": 2,
                        "description": "試著用不同角度理解圖片內容",
                        "duration_minutes": 3,
                        "temperature": "舒適環境",
                        "tips": ["每個人的理解都是獨特的"]
                    },
                    {
                        "step_number": 3,
                        "description": "接受這可能不是一個傳統的食譜",
                        "duration_minutes": 1,
                        "temperature": "常溫",
                        "tips": ["生活中的驚喜總是意外出現"]
                    }
                ],
                "servings": 1,
                "prep_time": 1,
                "cook_time": 5,
                "tags": ["創意", "趣味", "療癒"]
            }

    def analyze_thumbnail_quick(
        self,
        thumbnail_url: str
    ) -> Dict[str, Any]:
        """
        Quick thumbnail-only analysis to extract recipe name only
        Used for Phase 1 of two-phase analysis (fast reply)

        Args:
            thumbnail_url: URL or local path to thumbnail image

        Returns:
            Dictionary containing:
            - name: Recipe name only
            - usage_metadata: Token usage information

        Raises:
            ValueError: If thumbnail cannot be loaded
            Exception: If API call fails
        """
        try:
            logger.info(f"Quick analysis: Loading thumbnail from {thumbnail_url[:80]}...")

            # Load thumbnail image
            thumbnail_img = self._load_thumbnail(thumbnail_url)
            if not thumbnail_img:
                raise ValueError(f"Cannot load thumbnail from {thumbnail_url}")

            logger.info("Quick analysis: Thumbnail loaded, calling Gemini for name extraction...")

            # Call LLM with quick name-only prompt
            response = self._call_llm_api_quick(thumbnail_img)

            # Extract token usage
            token_usage = response.get('token_usage', {})
            usage_metadata = {
                'provider': response['provider'],
                'provider_metadata': response['provider_metadata'],
                **token_usage
            }

            logger.info(f"Quick analysis token usage: {token_usage.get('total_tokens', 0)} tokens")

            # Parse JSON response
            recipe_data = self._parse_json_quick_response(response['text'])

            # Validate name field exists
            if 'name' not in recipe_data:
                raise ValueError("Quick analysis failed: 'name' field not found in response")

            logger.info(f"Quick analysis complete: {recipe_data['name']}")

            return {
                'name': recipe_data['name'],
                'usage_metadata': usage_metadata
            }

        except Exception as e:
            logger.error(f"Quick thumbnail analysis failed: {type(e).__name__}: {str(e)}", exc_info=True)
            raise
        finally:
            # Close image to free file handle
            if 'thumbnail_img' in locals():
                try:
                    thumbnail_img.close()
                except Exception as e:
                    logger.warning(f"Failed to close thumbnail image: {e}")

    def _call_llm_api_quick(
        self,
        image: Image.Image
    ) -> Dict[str, Any]:
        """
        Call LLM API with quick name-only prompt (no retry, fast path)

        Args:
            image: PIL Image object (thumbnail)

        Returns:
            Dict with response text and metadata
        """
        start_time = time.time()
        try:
            # Convert image to base64
            image_content = {"type": "image_url", "image_url": {"url": self._image_to_base64(image)}}

            # Build message with quick name-only prompt
            message = HumanMessage(
                content=[
                    {"type": "text", "text": self.QUICK_NAME_ONLY_PROMPT},
                    image_content
                ]
            )

            # Get LLM model
            model = self.llm_manager.get_primary_model()

            # Call LLM (no retry for quick analysis)
            logger.debug("Calling LLM API with quick name-only prompt")
            response = model.invoke([message])

            elapsed = time.time() - start_time
            provider_info = self.llm_manager.get_provider_metadata()
            logger.info(
                f"Quick LLM API call succeeded in {elapsed:.2f}s "
                f"(provider: {provider_info['primary_provider']})"
            )

            # Extract token usage
            token_usage = {}

            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                if isinstance(usage, dict):
                    token_usage = {
                        'prompt_tokens': usage.get('input_tokens', 0),
                        'output_tokens': usage.get('output_tokens', 0),
                        'total_tokens': usage.get('total_tokens', 0)
                    }
            elif hasattr(response, 'response_metadata') and response.response_metadata:
                metadata = response.response_metadata
                if 'usage_metadata' in metadata:
                    usage = metadata['usage_metadata']
                    token_usage = {
                        'prompt_tokens': usage.get('prompt_token_count', 0),
                        'output_tokens': usage.get('candidates_token_count', 0),
                        'total_tokens': usage.get('total_token_count', 0)
                    }

            logger.info(f"Token usage: {token_usage.get('total_tokens', 0)} tokens")

            return {
                'text': response.content,
                'provider': provider_info['primary_provider'],
                'provider_metadata': provider_info,
                'token_usage': token_usage
            }

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"Quick LLM API call failed after {elapsed:.2f}s: "
                f"{type(e).__name__}: {str(e)}"
            )
            raise

    def _parse_json_quick_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON from quick name-only response

        Args:
            response_text: Raw response text from LLM

        Returns:
            Parsed JSON object with 'name' field

        Raises:
            ValueError: If 'name' field not found
        """
        # Remove markdown code blocks
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', response_text.strip(), flags=re.MULTILINE).strip()

        try:
            data = json.loads(text)
            if 'name' not in data:
                raise ValueError("Response missing 'name' field")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse quick response JSON: {text[:200]}...")
            raise ValueError(f"Invalid JSON response: {str(e)}")

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
    api_key: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    is_incremental: bool = False,
    existing_recipe_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Analyze recipe from video frames

    Args:
        frame_paths: List of frame image paths
        api_key: DEPRECATED - API keys are now managed via environment variables
        thumbnail_url: Optional URL or path to video thumbnail/cover image
        is_incremental: If True, treat this as a supplementary analysis (default: False)
        existing_recipe_context: Existing recipe data for incremental analysis context

    Returns:
        Dictionary containing:
        - recipe: Parsed recipe data (ingredients, steps, etc.)
        - usage_metadata: Dict with:
            - provider: LLM provider used (gemini/grok/openai)
            - provider_metadata: Provider chain information
            - prompt_tokens: Input tokens count
            - output_tokens: Output tokens count
            - total_tokens: Total tokens count
    """
    analyzer = RecipeAnalyzer(api_key=api_key)
    return analyzer.analyze_frames(
        frame_paths,
        thumbnail_url=thumbnail_url,
        is_incremental=is_incremental,
        existing_recipe_context=existing_recipe_context
    )
