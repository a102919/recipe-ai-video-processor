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
from video_utils import get_video_metadata

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
    4. Return structured recipe data with cost metadata
    5. Cleanup temporary files (optional)

    Args:
        url: Video URL (YouTube, etc.)
        cleanup: Remove temporary files after processing (default: True)
        api_key: Gemini API key (optional, uses env var if not provided)

    Returns:
        Recipe data dictionary with ingredients, steps, and metadata (tokens, video info)

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

        # Get video metadata using FFmpeg
        metadata = get_video_metadata(video_path)
        video_file_size = metadata['size']
        video_duration = metadata['duration']
        logger.info(f"Video file size: {video_file_size} bytes")
        logger.info(f"Video duration: {video_duration}s")

        # Stage 3: Extract key frames
        logger.info("Stage 2/3: Extracting frames...")
        frames_dir = os.path.join(temp_dir, 'frames')
        all_frames = extract_key_frames(video_path, frames_dir, count=12)
        logger.info(f"Extracted {len(all_frames)} frames")

        if not all_frames:
            raise ValueError("No frames extracted from video")

        # Stage 4: Analyze with Gemini Vision
        logger.info("Stage 3/3: Analyzing with Gemini Vision...")
        analysis_result = analyze_recipe_from_frames(all_frames, api_key=api_key)
        recipe_data = analysis_result['recipe']
        usage_metadata = analysis_result['usage_metadata']

        logger.info(f"Recipe extracted: {recipe_data.get('name', 'Unknown')}")
        logger.info(f"Token usage: {usage_metadata['total_tokens']} tokens")

        # Add thumbnail URL and metadata to recipe data
        recipe_data['thumbnail_url'] = thumbnail_url

        return {
            **recipe_data,
            'metadata': {
                'gemini_tokens': usage_metadata,
                'video_info': {
                    'duration_seconds': video_duration,
                    'file_size_bytes': video_file_size,
                    'frames_extracted': len(all_frames),
                    'frames_analyzed': len(all_frames)
                }
            }
        }

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
