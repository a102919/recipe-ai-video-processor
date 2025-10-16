"""
Streaming Frame Extractor
Extracts frames directly from video streams without downloading full video
Significantly faster than traditional download-then-extract approach
"""
import subprocess
import tempfile
import logging
import os
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class StreamingError(Exception):
    """Raised when streaming extraction fails"""
    pass


def get_direct_stream_url(video_url: str, use_cookies: bool = False, cookie_file: Optional[str] = None) -> str:
    """
    Get direct stream URL using yt-dlp without downloading

    Args:
        video_url: YouTube/Instagram/TikTok video URL
        use_cookies: Whether to use cookies for authentication
        cookie_file: Path to cookies file (required if use_cookies=True)

    Returns:
        Direct stream URL that can be used with FFmpeg

    Raises:
        StreamingError: If yt-dlp fails to get stream URL
    """
    cmd = ['yt-dlp', '-g', video_url]

    if use_cookies and cookie_file:
        cmd.extend(['--cookies', cookie_file])

    try:
        logger.info(f"Getting stream URL for: {video_url[:60]}...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15  # Quick operation, 15 seconds should be enough
        )

        if result.returncode != 0:
            raise StreamingError(f"yt-dlp failed: {result.stderr}")

        stream_url = result.stdout.strip()
        if not stream_url:
            raise StreamingError("yt-dlp returned empty stream URL")

        logger.info(f"✓ Got stream URL: {stream_url[:80]}...")
        return stream_url

    except subprocess.TimeoutExpired:
        raise StreamingError("yt-dlp timed out getting stream URL")
    except Exception as e:
        raise StreamingError(f"Failed to get stream URL: {e}")


def get_video_metadata_only(video_url: str, use_cookies: bool = False, cookie_file: Optional[str] = None) -> dict:
    """
    Get video metadata without downloading using yt-dlp --dump-json

    Args:
        video_url: Video URL
        use_cookies: Whether to use cookies
        cookie_file: Path to cookies file

    Returns:
        Dict with metadata including duration, title, thumbnail, etc.

    Raises:
        StreamingError: If metadata extraction fails
    """
    cmd = ['yt-dlp', '--dump-json', '--no-download', video_url]

    if use_cookies and cookie_file:
        cmd.extend(['--cookies', cookie_file])

    try:
        logger.info(f"Getting metadata for: {video_url[:60]}...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode != 0:
            raise StreamingError(f"yt-dlp metadata extraction failed: {result.stderr}")

        import json
        metadata = json.loads(result.stdout)

        logger.info(f"✓ Got metadata: duration={metadata.get('duration', 0)}s, title={metadata.get('title', 'Unknown')[:40]}")
        return metadata

    except subprocess.TimeoutExpired:
        raise StreamingError("yt-dlp timed out getting metadata")
    except Exception as e:
        raise StreamingError(f"Failed to get metadata: {e}")


def extract_frame_from_stream(
    stream_url: str,
    timestamp: float,
    output_path: str,
    quality: int = 2
) -> str:
    """
    Extract a single frame from video stream at specific timestamp

    Args:
        stream_url: Direct video stream URL (from yt-dlp -g)
        timestamp: Time in seconds to extract frame
        output_path: Path to save extracted frame
        quality: JPEG quality (1-31, lower is better, default 2)

    Returns:
        Path to extracted frame

    Raises:
        StreamingError: If frame extraction fails
    """
    cmd = [
        'ffmpeg',
        '-ss', str(timestamp),    # Seek to timestamp (input seeking - faster)
        '-i', stream_url,          # Input stream URL
        '-vframes', '1',           # Extract 1 frame
        '-q:v', str(quality),      # Quality
        '-y',                      # Overwrite output
        output_path
    ]

    try:
        logger.debug(f"Extracting frame at {timestamp}s to {output_path}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30  # Should be fast, but allow time for seeking
        )

        if result.returncode != 0:
            raise StreamingError(f"FFmpeg frame extraction failed at {timestamp}s: {result.stderr[:200]}")

        if not os.path.exists(output_path):
            raise StreamingError(f"Frame extraction succeeded but file not found: {output_path}")

        logger.debug(f"✓ Extracted frame at {timestamp}s")
        return output_path

    except subprocess.TimeoutExpired:
        raise StreamingError(f"FFmpeg timed out extracting frame at {timestamp}s")
    except Exception as e:
        raise StreamingError(f"Failed to extract frame at {timestamp}s: {e}")


def calculate_sample_timestamps(duration_seconds: float, target_count: int) -> List[float]:
    """
    Calculate evenly distributed sample timestamps across video duration

    Args:
        duration_seconds: Total video duration in seconds
        target_count: Number of frames to extract

    Returns:
        List of timestamps (in seconds) evenly distributed across video

    Example:
        duration=300s (5 min), target_count=8
        Returns: [33.3, 66.7, 100.0, 133.3, 166.7, 200.0, 233.3, 266.7]
    """
    if target_count <= 0:
        return []

    if target_count == 1:
        # Single frame: extract from middle
        return [duration_seconds / 2]

    # Evenly distribute frames, avoiding first and last seconds
    # Add buffer to avoid black frames at start/end
    buffer = max(1, duration_seconds * 0.02)  # 2% buffer or 1 second minimum
    effective_duration = duration_seconds - (2 * buffer)

    step = effective_duration / (target_count - 1)
    timestamps = [buffer + (step * i) for i in range(target_count)]

    logger.info(f"Calculated {target_count} timestamps for {duration_seconds}s video: {[f'{t:.1f}s' for t in timestamps[:3]]}...")
    return timestamps


def extract_frames_from_stream(
    video_url: str,
    target_count: int = 8,
    output_dir: Optional[str] = None,
    use_cookies: bool = False,
    cookie_file: Optional[str] = None
) -> List[str]:
    """
    Extract frames from video stream without downloading full video

    This is the main entry point for streaming frame extraction.

    Args:
        video_url: Video URL (YouTube, Instagram, etc.)
        target_count: Number of frames to extract (default 8)
        output_dir: Directory to save frames (default: temp dir)
        use_cookies: Whether to use cookies for authentication
        cookie_file: Path to cookies file

    Returns:
        List of paths to extracted frame images

    Raises:
        StreamingError: If extraction fails

    Performance:
        - Traditional method: 30-110s (download + extract)
        - Streaming method: 5-20s (direct extraction)
        - Speedup: 3-10x faster
    """
    temp_dir_created = False

    try:
        # Create output directory
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix='recipeai_stream_')
            temp_dir_created = True
        else:
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        logger.info(f"[Streaming Extraction] Starting for {video_url[:60]}...")
        logger.info(f"[Streaming Extraction] Target: {target_count} frames")

        # Step 1: Get metadata (fast, ~2s)
        metadata = get_video_metadata_only(video_url, use_cookies, cookie_file)
        duration = metadata.get('duration')

        if not duration or duration <= 0:
            raise StreamingError(f"Invalid video duration: {duration}")

        logger.info(f"[Streaming Extraction] Video duration: {duration}s")

        # Step 2: Calculate sample timestamps
        timestamps = calculate_sample_timestamps(duration, target_count)

        # Step 3: Get stream URL (fast, ~2s)
        stream_url = get_direct_stream_url(video_url, use_cookies, cookie_file)

        # Step 4: Extract frames at calculated timestamps
        frame_paths = []
        for i, timestamp in enumerate(timestamps):
            frame_path = os.path.join(output_dir, f"stream_frame_{i+1:04d}.jpg")
            try:
                extract_frame_from_stream(stream_url, timestamp, frame_path)
                frame_paths.append(frame_path)
            except StreamingError as e:
                logger.warning(f"Failed to extract frame at {timestamp}s: {e}")
                # Continue with other frames even if one fails
                continue

        if not frame_paths:
            raise StreamingError("No frames could be extracted from stream")

        logger.info(f"[Streaming Extraction] ✅ Successfully extracted {len(frame_paths)}/{target_count} frames")
        return frame_paths

    except Exception as e:
        logger.error(f"[Streaming Extraction] ❌ Failed: {e}")
        raise StreamingError(f"Streaming extraction failed: {e}")


# Backward compatibility alias
extract_key_frames_from_stream = extract_frames_from_stream
