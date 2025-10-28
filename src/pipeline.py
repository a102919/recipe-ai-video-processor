"""
Recipe Extraction Pipeline
End-to-end workflow: URL -> Download -> Extract Frames -> Analyze -> Recipe
Version 2.0: Streaming frame extraction (no download required for most cases)
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
from .streaming_extractor import (
    extract_frames_from_stream,
    get_video_metadata_only,
    StreamingError
)
from .config import EXTRACTION_MODE

logger = logging.getLogger(__name__)


def calculate_optimal_frame_count(duration_seconds: int, mode: str = 'balanced') -> int:
    """
    Calculate optimal frame count based on video duration

    Args:
        duration_seconds: Video duration in seconds
        mode: Extraction mode
              - 'fast': Prioritize speed, minimal frames (for reply token deadline)
              - 'balanced': Balance speed and accuracy (default)
              - 'accurate': Maximum frames for best accuracy

    Returns:
        Optimal frame count

    Strategy by mode:
        Fast mode (optimized for <55s reply token deadline):
        - <5 min: 8 frames  (every ~35s)
        - 5-10 min: 10 frames (every ~45s)
        - 10-15 min: 12 frames (every ~60s)
        - >15 min: 16 frames (capped)

        Balanced mode (original):
        - <5 min: 12 frames (every ~25s)
        - 5-10 min: 18 frames (every ~30s)
        - 10-15 min: 24 frames (every ~35s)
        - >15 min: 36 frames (capped)

        Accurate mode:
        - <5 min: 15 frames
        - 5-10 min: 24 frames
        - 10-15 min: 36 frames
        - >15 min: 48 frames (capped)
    """
    if mode == 'fast':
        # Fast mode: Optimized for speed
        if duration_seconds < 300:  # <5 minutes
            return 8
        elif duration_seconds < 600:  # <10 minutes
            return 10
        elif duration_seconds < 900:  # <15 minutes
            return 12
        else:  # >=15 minutes
            return 16
    elif mode == 'accurate':
        # Accurate mode: Maximum frames
        if duration_seconds < 300:
            return 15
        elif duration_seconds < 600:
            return 24
        elif duration_seconds < 900:
            return 36
        else:
            return min(48, max(36, duration_seconds // 20))
    else:
        # Balanced mode (default)
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
    frame_count: Optional[int] = None,
    extraction_mode: str = EXTRACTION_MODE,
    use_streaming: bool = False,  # Disabled by default: YouTube doesn't support FFmpeg streaming
    frame_selection_strategy: str = 'scene',  # 'uniform', 'scene', or 'hybrid' - Default: scene (captures key moments)
    previous_recipe_context: Optional[Dict[str, Any]] = None  # Previous analysis for reanalysis context
) -> Dict[str, Any]:
    """
    Extract recipe from video URL (end-to-end pipeline)

    Version 2.1: Supports multiple frame selection strategies

    Pipeline stages (streaming mode):
    1. Get video metadata without downloading
    2. Extract frames directly from stream
    3. Analyze frames with Gemini Vision
    4. Return structured recipe data with cost metadata
    5. Cleanup temporary files (optional)

    Pipeline stages (fallback mode):
    1. Download video from URL
    2. Extract key frames from video (using selected strategy)
    3. Analyze frames with Gemini Vision
    4. Return structured recipe data with cost metadata
    5. Cleanup temporary files (optional)

    Args:
        url: Video URL (YouTube, Instagram, TikTok, etc.)
        cleanup: Remove temporary files after processing (default: True)
        api_key: Gemini API key (optional, uses env var if not provided)
        frame_count: Number of frames to extract and analyze
                    If None (default), automatically calculated based on video duration and mode
        extraction_mode: Frame extraction mode (default: 'fast')
                        - 'fast': 8-16 frames (optimized for reply token deadline)
                        - 'balanced': 12-36 frames (original behavior)
                        - 'accurate': 15-48 frames (maximum quality)
        use_streaming: Try streaming extraction first (default: True)
                      If False or streaming fails, fallback to traditional download
        frame_selection_strategy: Frame selection strategy (default: 'uniform')
                                 - 'uniform': Evenly distributed frames (original method)
                                 - 'scene': FFmpeg scene detection (detects visual changes)
                                 - 'hybrid': 70% scene detection + 30% uniform

    Returns:
        Recipe data dictionary with ingredients, steps, and metadata (tokens, video info)

    Raises:
        ValueError: If URL is invalid or video cannot be processed
        Exception: If any pipeline stage fails

    Performance (streaming vs traditional):
        - Streaming: 5-25s total
        - Traditional: 30-110s total
        - Speedup: 3-10x faster
    """
    temp_dir = None
    video_path = None
    all_frames = []

    try:
        # Stage 1: Create temp directory
        temp_dir = tempfile.mkdtemp(prefix='recipeai_pipeline_')
        logger.info(f"Pipeline started for URL: {url}")
        logger.info(f"Temp directory: {temp_dir}")
        logger.info(f"Extraction mode: {extraction_mode}, Streaming: {use_streaming}")

        # ========================================
        # STREAMING MODE (NEW - Fast Path)
        # ========================================
        if use_streaming:
            try:
                logger.info("=" * 60)
                logger.info("ATTEMPTING STREAMING EXTRACTION (Fast Path)")
                logger.info("=" * 60)

                # Get metadata without downloading
                logger.info("Stage 1/3: Getting video metadata...")
                metadata = get_video_metadata_only(url)
                video_duration = metadata.get('duration', 0)
                thumbnail_url = metadata.get('thumbnail')
                logger.info(f"Video duration: {video_duration}s")

                # Calculate frame count
                if frame_count is None:
                    frame_count = calculate_optimal_frame_count(int(video_duration), mode=extraction_mode)
                    logger.info(f"Auto-calculated frame count: {frame_count} frames ({extraction_mode} mode)")

                # Extract frames from stream
                logger.info(f"Stage 2/3: Extracting {frame_count} frames from stream...")
                all_frames = extract_frames_from_stream(
                    url,
                    target_count=frame_count,
                    output_dir=temp_dir
                )
                logger.info(f"✅ Streaming extraction successful: {len(all_frames)} frames")

                # Calculate file size from frames
                video_file_size = sum(os.path.getsize(f) for f in all_frames)

                # Success! Skip traditional download
                video_path = None
                photo_paths = None

            except StreamingError as e:
                logger.warning("=" * 60)
                logger.warning(f"STREAMING EXTRACTION FAILED: {e}")
                logger.warning("Falling back to traditional download method...")
                logger.warning("=" * 60)
                use_streaming = False  # Force fallback

        # ========================================
        # TRADITIONAL MODE (Fallback or Explicit)
        # ========================================
        if not use_streaming or not all_frames:
            logger.info("=" * 60)
            logger.info("USING TRADITIONAL DOWNLOAD METHOD")
            logger.info("=" * 60)

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
                    frame_count = calculate_optimal_frame_count(int(video_duration), mode=extraction_mode)
                    logger.info(f"Auto-calculated frame count: {frame_count} frames ({extraction_mode} mode, {video_duration}s duration)")
                else:
                    logger.info(f"Using specified frame count: {frame_count} frames")

                # Stage 3: Extract key frames
                logger.info(f"Stage 2/3: Extracting frames (strategy: {frame_selection_strategy})...")
                frames_dir = os.path.join(temp_dir, 'frames')
                # Set max_frames based on video duration to cover entire video
                # Use 1fps sampling, so max_frames should match duration
                max_frames_needed = max(int(video_duration) + 10, 200)  # +10 buffer, min 200
                all_frames = extract_key_frames(
                    video_path,
                    frames_dir,
                    count=frame_count,
                    max_frames=max_frames_needed,
                    strategy=frame_selection_strategy
                )
                logger.info(f"Extracted {len(all_frames)} frames")

                if not all_frames:
                    raise ValueError("No frames extracted from video")

        # Stage 4: Analyze with Gemini Vision (including thumbnail and previous context)
        logger.info("Stage 3/3: Analyzing with Gemini Vision...")
        if previous_recipe_context:
            logger.info("Using previous analysis as reference for improved accuracy")

        analysis_result = analyze_recipe_from_frames(
            all_frames,
            api_key=api_key,
            thumbnail_url=thumbnail_url,
            is_incremental=bool(previous_recipe_context),
            existing_recipe_context=previous_recipe_context
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

        # Determine content type
        if use_streaming and all_frames:
            content_type = 'video_streaming'  # Streaming extraction was used
        elif photo_paths:
            content_type = 'photo_carousel'
        else:
            content_type = 'video'

        return {
            **recipe_data,
            'metadata': {
                'llm_usage': usage_metadata,  # Renamed from 'gemini_tokens' to be provider-agnostic
                'content_type': content_type,
                'extraction_method': 'streaming' if (use_streaming and all_frames) else 'download',
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


def run_incremental_analysis(
    url: str,
    excluded_frame_indices: list[int],
    existing_recipe: Optional[Dict[str, Any]] = None,
    cleanup: bool = True,
    api_key: Optional[str] = None,
    frame_count: Optional[int] = None
) -> Dict[str, Any]:
    """
    Incremental analysis: Extract and analyze additional frames from a video
    that weren't analyzed in the original analysis.

    This is useful for getting more detailed recipes by analyzing supplementary frames
    and then merging results intelligently.

    Args:
        url: Video URL
        excluded_frame_indices: List of frame indices already analyzed (e.g., [1, 16, 31, ...])
        existing_recipe: The existing recipe data (used in LLM prompt for context)
        cleanup: Remove temporary files after processing
        api_key: Gemini API key
        frame_count: Number of new frames to extract
                    If None, auto-calculated based on video duration

    Returns:
        Recipe data from supplementary frames, with frame indices of analyzed frames

    Example:
        # First analysis: 12 frames analyzed at indices [1, 16, 31, 46, 61, 76, 91, 106, 121, 136, 151, 166]
        # Incremental analysis: analyze 24 more frames from remaining frames
        result = run_incremental_analysis(
            url="https://...",
            excluded_frame_indices=[1, 16, 31, 46, 61, 76, 91, 106, 121, 136, 151, 166],
            existing_recipe={"name": "Braise", "ingredients": [...]}
        )
    """
    temp_dir = None
    video_path = None
    all_extracted_frames = []

    try:
        temp_dir = tempfile.mkdtemp(prefix='recipeai_incremental_')
        logger.info(f"Incremental analysis started for URL: {url}")
        logger.info(f"Excluded frame indices: {excluded_frame_indices}")
        logger.info(f"Using Hybrid extraction mode (highest precision)")

        # Stage 1: Download video
        logger.info("Stage 1/3: Downloading content...")
        video_path, thumbnail_url, photo_paths = download_video(url, output_dir=temp_dir)

        # Handle photo carousel (no incremental analysis for photos)
        if photo_paths:
            logger.warning("Photo carousel detected - incremental analysis not supported")
            raise ValueError("Incremental analysis requires video input, not photo carousel")

        # Get video metadata
        metadata = get_video_metadata(video_path)
        video_duration = metadata['duration']
        video_file_size = metadata['size']
        logger.info(f"Video duration: {video_duration}s, size: {video_file_size} bytes")

        # Auto-calculate frame count for incremental analysis
        # Use 'accurate' mode to get maximum detail
        if frame_count is None:
            # For incremental, use higher frame count than original
            # If original was 12 frames, increment by 24 frames
            frame_count = calculate_optimal_frame_count(int(video_duration), mode='accurate')
            logger.info(f"Auto-calculated incremental frame count: {frame_count} frames (accurate mode)")

        # Stage 2: Extract ALL frames first (for comparison)
        logger.info(f"Stage 2/3: Extracting frames (hybrid strategy for max detail)...")
        frames_dir = os.path.join(temp_dir, 'frames')
        max_frames_needed = max(int(video_duration) + 10, 200)

        # Extract with maximum detail using hybrid strategy
        all_extracted_frames = extract_key_frames(
            video_path,
            frames_dir,
            count=frame_count,
            max_frames=max_frames_needed,
            strategy='hybrid'  # Use hybrid for maximum detail
        )
        logger.info(f"Extracted {len(all_extracted_frames)} frames total")

        if not all_extracted_frames:
            raise ValueError("No frames extracted from video")

        # Stage 3: Analyze with context about existing recipe
        logger.info("Stage 3/3: Analyzing supplementary frames with Gemini Vision...")

        # Prepare context about existing recipe for the prompt
        recipe_context = existing_recipe if existing_recipe else {}

        # Create enhanced analysis result with incremental context
        analysis_result = analyze_recipe_from_frames(
            all_extracted_frames,
            api_key=api_key,
            thumbnail_url=thumbnail_url,
            is_incremental=True,
            existing_recipe_context=recipe_context
        )

        recipe_data = analysis_result['recipe']
        usage_metadata = analysis_result['usage_metadata']

        logger.info(f"Incremental recipe extracted: {recipe_data.get('name', 'Unknown')}")
        logger.info(f"Token usage: {usage_metadata.get('total_tokens', 'N/A')} tokens")

        # Return result with frame indices for tracking
        return {
            **recipe_data,
            'metadata': {
                'llm_usage': usage_metadata,
                'is_incremental': True,
                'extraction_method': 'download',
                'video_info': {
                    'duration_seconds': video_duration,
                    'file_size_bytes': video_file_size,
                    'frames_extracted': len(all_extracted_frames),
                    'frames_analyzed': len(all_extracted_frames),
                    'frame_indices': list(range(1, len(all_extracted_frames) + 1))  # Frame indices for this analysis
                }
            }
        }

    except Exception as e:
        logger.error(f"Incremental analysis failed: {e}", exc_info=True)
        raise

    finally:
        # Cleanup temporary files
        if cleanup and temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {temp_dir}: {e}")

        # Force garbage collection
        gc.collect()
