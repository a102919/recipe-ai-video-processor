"""
Recipe Extraction Pipeline
End-to-end workflow: URL -> Download -> Extract Frames -> Analyze -> Recipe
"""
import os
import tempfile
import shutil
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from downloader import download_video
from extractor import extract_key_frames
from analyzer import analyze_recipe_from_frames

logger = logging.getLogger(__name__)


def analyze_recipe_from_url(
    url: str,
    cleanup: bool = True,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract recipe from video URL (end-to-end pipeline)

    Pipeline stages:
    1. Download video from URL
    2. Extract key frames from video
    3. Analyze frames with Gemini Vision
    4. Return structured recipe data
    5. Cleanup temporary files (optional)

    Args:
        url: Video URL (YouTube, etc.)
        cleanup: Remove temporary files after processing (default: True)
        api_key: Gemini API key (optional, uses env var if not provided)

    Returns:
        Recipe data dictionary with ingredients, steps, etc.

    Raises:
        ValueError: If URL is invalid or video cannot be processed
        Exception: If any pipeline stage fails
    """
    temp_dir = None
    video_path = None

    try:
        # Stage 1: Create temp directory
        temp_dir = tempfile.mkdtemp(prefix='recipeai_pipeline_')
        logger.info(f"Pipeline started for URL: {url}")
        logger.info(f"Temp directory: {temp_dir}")

        # Stage 2: Download video
        logger.info("Stage 1/3: Downloading video...")
        video_path, thumbnail_url = download_video(url, output_dir=temp_dir)
        logger.info(f"Video downloaded: {video_path}")
        logger.info(f"Thumbnail URL: {thumbnail_url or 'N/A'}")

        # Stage 3: Extract key frames
        logger.info("Stage 2/3: Extracting frames...")
        frames_dir = os.path.join(temp_dir, 'frames')
        key_frames = extract_key_frames(video_path, frames_dir, count=12)
        logger.info(f"Extracted {len(key_frames)} key frames")

        if not key_frames:
            raise ValueError("No frames extracted from video")

        # Stage 4: Analyze with Gemini Vision
        logger.info("Stage 3/3: Analyzing with Gemini Vision...")
        recipe_data = analyze_recipe_from_frames(key_frames, api_key=api_key)
        logger.info(f"Recipe extracted: {recipe_data.get('name', 'Unknown')}")

        # Add thumbnail URL to recipe data
        recipe_data['thumbnail_url'] = thumbnail_url

        return recipe_data

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise

    finally:
        # Cleanup temporary files
        if cleanup and temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {temp_dir}: {e}")
