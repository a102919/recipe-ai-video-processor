"""
Video Frame Extractor
Extracts key frames from cooking videos using FFmpeg for Gemini Vision analysis
"""
import subprocess
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)


class FrameExtractor:
    """Extracts and selects key frames from video files"""

    def __init__(self, max_frames: int = 180, quality: int = 2):
        """
        Initialize frame extractor

        Args:
            max_frames: Maximum frames to extract (default 180 for 3-min video @ 1fps)
            quality: JPEG quality (1-31, lower is better, default 2)
        """
        self.max_frames = max_frames
        self.quality = quality

    def extract_frames(self, video_path: str, output_dir: str) -> List[str]:
        """
        Extract frames from video at 1fps

        Args:
            video_path: Path to input video file
            output_dir: Directory to save extracted frames

        Returns:
            List of paths to extracted frame images

        Raises:
            subprocess.CalledProcessError: If FFmpeg fails
            FileNotFoundError: If video file not found
        """
        video_file = Path(video_path)
        if not video_file.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        output_pattern = str(output_path / "frame_%04d.jpg")

        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vf', 'fps=1',  # 1 frame per second
            '-q:v', str(self.quality),  # High quality
            '-frames:v', str(self.max_frames),  # Max frames limit
            output_pattern
        ]

        try:
            logger.info(f"Extracting frames from {video_path} at 1fps")
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            logger.debug(f"FFmpeg output: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed: {e.stderr}")
            raise

        # Get all extracted frames
        frames = sorted(output_path.glob('frame_*.jpg'))
        frame_paths = [str(f) for f in frames]

        logger.info(f"Extracted {len(frame_paths)} frames")
        return frame_paths

    def select_key_frames(
        self,
        frame_paths: List[str],
        count: int = 12
    ) -> List[str]:
        """
        Select evenly distributed key frames for analysis

        Args:
            frame_paths: List of all extracted frame paths
            count: Target number of frames to select (default 12)

        Returns:
            List of selected key frame paths
        """
        if len(frame_paths) <= count:
            logger.info(f"Using all {len(frame_paths)} frames (less than target {count})")
            return frame_paths

        # Select evenly distributed frames
        step = len(frame_paths) / count
        selected = [frame_paths[int(i * step)] for i in range(count)]

        logger.info(f"Selected {len(selected)} key frames from {len(frame_paths)} total")
        return selected

    def extract_and_select(
        self,
        video_path: str,
        output_dir: str,
        key_frame_count: int = 12
    ) -> List[str]:
        """
        Extract frames and select key frames in one step

        Args:
            video_path: Path to input video
            output_dir: Directory for frame output
            key_frame_count: Number of key frames to select

        Returns:
            List of selected key frame paths
        """
        all_frames = self.extract_frames(video_path, output_dir)
        key_frames = self.select_key_frames(all_frames, key_frame_count)
        return key_frames


# Convenience function for single-use extraction
def extract_key_frames(
    video_path: str,
    output_dir: str,
    count: int = 12,
    max_frames: int = 180
) -> List[str]:
    """
    Extract and select key frames from video

    Args:
        video_path: Path to video file
        output_dir: Output directory for frames
        count: Number of key frames to select
        max_frames: Maximum total frames to extract

    Returns:
        List of key frame paths
    """
    extractor = FrameExtractor(max_frames=max_frames)
    return extractor.extract_and_select(video_path, output_dir, count)
