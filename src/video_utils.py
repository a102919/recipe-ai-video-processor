"""
Video utility functions for metadata extraction
"""
import subprocess
import json
from typing import Dict, Any


def get_video_metadata(video_path: str) -> Dict[str, Any]:
    """
    Extract video metadata using FFprobe

    Args:
        video_path: Path to video file

    Returns:
        Dictionary containing:
            - duration: Video duration in seconds (int)
            - size: File size in bytes (int)
            - format: Format information from FFprobe
    """
    probe_result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_path],
        capture_output=True,
        text=True,
        check=True
    )
    format_info = json.loads(probe_result.stdout)['format']

    return {
        'duration': int(float(format_info['duration'])),
        'size': int(format_info['size']),
        'format': format_info
    }
