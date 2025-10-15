"""
Recipe Extraction Pipeline
End-to-end workflow: URL -> Download -> Extract Frames -> Analyze -> Recipe
"""
import os
import gc
import tempfile
import shutil
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from .downloader import download_video
from .extractor import extract_key_frames
from .analyzer import analyze_recipe_from_frames
from .video_utils import get_video_metadata

logger = logging.getLogger(__name__)


def calculate_optimal_frame_count(duration_seconds: int) -> int:
    """
    Calculate optimal frame count based on video duration

    Strategy: Balance accuracy and cost by adjusting frame density
    - Short videos (<5 min): 12 frames (every ~25s)
    - Medium videos (5-10 min): 18 frames (every ~30s)
    - Medium-long videos (10-15 min): 24 frames (every ~35s)
    - Long videos (>15 min): 36 frames (every ~40-50s, max to control cost)

    Args:
        duration_seconds: Video duration in seconds

    Returns:
        Optimal frame count
    """
    if duration_seconds < 300:  # <5 minutes
        return 12
    elif duration_seconds < 600:  # <10 minutes
        return 18
    elif duration_seconds < 900:  # <15 minutes
        return 24
    else:  # >=15 minutes
        # For very long videos, cap at 36 frames to control cost
        # This gives approximately 1 frame per 30-60 seconds
        return min(36, max(24, duration_seconds // 30))


def analyze_recipe_from_url(
    url: str,
    cleanup: bool = True,
    api_key: Optional[str] = None,
    frame_count: Optional[int] = None
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
        frame_count: Number of frames to extract and analyze
                    If None (default), automatically calculated based on video duration:
                    - <5 min: 12 frames
                    - 5-10 min: 18 frames
                    - 10-15 min: 24 frames
                    - >15 min: 36 frames (max)

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

        # Stage 2: Download video or photos
        logger.info("Stage 1/3: Downloading content...")
        video_path, thumbnail_url, photo_paths = download_video(url, output_dir=temp_dir)

        # Check if this is a photo carousel or video
        if photo_paths:
            # Photo carousel - use photos directly
            logger.info(f"Downloaded {len(photo_paths)} photos from carousel")
            logger.info(f"Thumbnail: {thumbnail_url or 'N/A'}")
            all_frames = photo_paths
            video_file_size = sum(os.path.getsize(p) for p in photo_paths)
            video_duration = 0  # No duration for static images
            logger.info(f"Total photo size: {video_file_size} bytes")
        else:
            # Video - extract frames
            logger.info(f"Video downloaded: {video_path}")
            logger.info(f"Thumbnail URL: {thumbnail_url or 'N/A'}")

            # Get video metadata using FFmpeg
            metadata = get_video_metadata(video_path)
            video_file_size = metadata['size']
            video_duration = metadata['duration']
            logger.info(f"Video file size: {video_file_size} bytes")
            logger.info(f"Video duration: {video_duration}s")

            # Auto-calculate optimal frame count if not specified
            if frame_count is None:
                frame_count = calculate_optimal_frame_count(int(video_duration))
                logger.info(f"Auto-calculated frame count: {frame_count} frames (based on {video_duration}s duration)")
            else:
                logger.info(f"Using specified frame count: {frame_count} frames")

            # Stage 3: Extract key frames
            logger.info("Stage 2/3: Extracting frames...")
            frames_dir = os.path.join(temp_dir, 'frames')
            # Set max_frames based on video duration to cover entire video
            # Use 1fps sampling, so max_frames should match duration
            max_frames_needed = max(int(video_duration) + 10, 200)  # +10 buffer, min 200
            all_frames = extract_key_frames(
                video_path,
                frames_dir,
                count=frame_count,
                max_frames=max_frames_needed
            )
            logger.info(f"Extracted {len(all_frames)} frames")

            if not all_frames:
                raise ValueError("No frames extracted from video")

        # Stage 4: Analyze with Gemini Vision (including thumbnail)
        logger.info("Stage 3/3: Analyzing with Gemini Vision...")
        analysis_result = analyze_recipe_from_frames(
            all_frames,
            api_key=api_key,
            thumbnail_url=thumbnail_url
        )
        recipe_data = analysis_result['recipe']
        usage_metadata = analysis_result['usage_metadata']

        logger.info(f"Recipe extracted: {recipe_data.get('name', 'Unknown')}")

        # Log provider info (new LangChain format)
        if 'provider' in usage_metadata:
            logger.info(f"LLM Provider: {usage_metadata['provider']}")
            provider_info = usage_metadata.get('provider_metadata', {})
            logger.info(f"Provider chain: {provider_info.get('provider_chain', [])}")
        # Legacy format compatibility
        elif 'total_tokens' in usage_metadata:
            logger.info(f"Token usage: {usage_metadata['total_tokens']} tokens")

        # Add thumbnail URL and metadata to recipe data
        recipe_data['thumbnail_url'] = thumbnail_url

        return {
            **recipe_data,
            'metadata': {
                'llm_usage': usage_metadata,  # Renamed from 'gemini_tokens' to be provider-agnostic
                'content_type': 'photo_carousel' if photo_paths else 'video',
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

        # Force garbage collection after video processing to free memory
        gc.collect()
