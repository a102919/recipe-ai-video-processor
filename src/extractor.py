"""
Video Frame Extractor
Extracts key frames from cooking videos using FFmpeg for Gemini Vision analysis

Supports multiple extraction strategies:
- uniform: Evenly distributed frames (original method)
- scene: FFmpeg scene detection (detects visual changes)
- hybrid: Combination of scene detection + uniform sampling
"""
import subprocess
from pathlib import Path
from typing import List, Literal
import logging
import os

logger = logging.getLogger(__name__)

ExtractionStrategy = Literal['uniform', 'scene', 'hybrid']


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
        # Memory optimization: single thread, ultrafast preset
        cmd.extend(['-threads', '1', '-preset', 'ultrafast'])

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

    def extract_frames_by_scene_detection(
        self,
        video_path: str,
        output_dir: str,
        target_count: int = 12,
        threshold: float = 0.4
    ) -> List[str]:
        """
        Extract frames using FFmpeg scene detection (detects visual changes)

        Args:
            video_path: Path to input video file
            output_dir: Directory to save extracted frames
            target_count: Target number of frames (default 12)
            threshold: Scene change threshold 0-1 (default 0.4 = 40% change)

        Returns:
            List of paths to scene-detected frame images

        Raises:
            subprocess.CalledProcessError: If FFmpeg fails
            FileNotFoundError: If video file not found
        """
        video_file = Path(video_path)
        if not video_file.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        output_pattern = str(output_path / "scene_%04d.jpg")

        # FFmpeg scene detection filter
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vf', f'select=gt(scene\\,{threshold})',  # Scene change > threshold
            '-vsync', 'vfr',  # Variable frame rate output
            '-q:v', str(self.quality),
            '-frames:v', str(self.max_frames),  # Safety limit
            output_pattern
        ]
        cmd.extend(['-threads', '1', '-preset', 'ultrafast'])

        try:
            logger.info(f"Extracting frames using scene detection (threshold={threshold})")
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            logger.debug(f"FFmpeg output: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg scene detection failed: {e.stderr}")
            raise

        # Get all scene-detected frames
        frames = sorted(output_path.glob('scene_*.jpg'))
        frame_paths = [str(f) for f in frames]

        logger.info(f"Scene detection found {len(frame_paths)} key frames")

        # If too many frames, sample evenly
        if len(frame_paths) > target_count:
            step = len(frame_paths) / target_count
            selected = [frame_paths[int(i * step)] for i in range(target_count)]
            logger.info(f"Downsampled to {len(selected)} frames")
            return selected

        # If too few frames, supplement with uniform sampling
        if len(frame_paths) < target_count:
            logger.warning(f"Only found {len(frame_paths)} scene changes (target: {target_count})")
            logger.info("Supplementing with uniform sampling...")
            return self._supplement_with_uniform(
                video_path, output_dir, frame_paths, target_count
            )

        return frame_paths

    def _supplement_with_uniform(
        self,
        video_path: str,
        output_dir: str,
        existing_frames: List[str],
        target_count: int
    ) -> List[str]:
        """
        Supplement scene-detected frames with uniform sampling

        Args:
            video_path: Path to video file
            output_dir: Output directory
            existing_frames: Already extracted scene frames
            target_count: Target total frame count

        Returns:
            Combined list of scene + uniform frames, sorted by timestamp
        """
        needed = target_count - len(existing_frames)
        if needed <= 0:
            return existing_frames

        # Extract uniform frames
        logger.info(f"Extracting {needed} additional uniform frames")
        uniform_pattern = str(Path(output_dir) / "uniform_%04d.jpg")

        # Get video duration
        duration_cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(duration_cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip())

        # Calculate timestamps for uniform sampling
        step = duration / (needed + 1)
        timestamps = [step * (i + 1) for i in range(needed)]

        # Extract frames at these timestamps
        uniform_frames = []
        for i, ts in enumerate(timestamps):
            output_file = str(Path(output_dir) / f"uniform_{i:04d}.jpg")
            cmd = [
                'ffmpeg',
                '-ss', str(ts),
                '-i', video_path,
                '-vframes', '1',
                '-q:v', str(self.quality),
                '-y',
                output_file
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            uniform_frames.append(output_file)

        # Combine and sort by filename (which reflects temporal order)
        all_frames = existing_frames + uniform_frames
        return sorted(all_frames)

    def extract_frames_hybrid(
        self,
        video_path: str,
        output_dir: str,
        target_count: int = 12,
        scene_ratio: float = 0.7
    ) -> List[str]:
        """
        Hybrid strategy: scene detection + uniform sampling

        Args:
            video_path: Path to input video
            output_dir: Output directory
            target_count: Target total frames (default 12)
            scene_ratio: Ratio of frames from scene detection (default 0.7 = 70%)

        Returns:
            List of frame paths combining both strategies
        """
        scene_count = int(target_count * scene_ratio)
        uniform_count = target_count - scene_count

        logger.info(f"Hybrid extraction: {scene_count} scene frames + {uniform_count} uniform frames")

        # Extract scene frames
        scene_frames = self.extract_frames_by_scene_detection(
            video_path,
            output_dir,
            target_count=scene_count,
            threshold=0.4
        )

        # Extract uniform frames at different timestamps
        uniform_frames = self._extract_uniform_frames_at_intervals(
            video_path,
            output_dir,
            count=uniform_count
        )

        # Combine and sort
        all_frames = scene_frames + uniform_frames
        return sorted(all_frames)

    def _extract_uniform_frames_at_intervals(
        self,
        video_path: str,
        output_dir: str,
        count: int
    ) -> List[str]:
        """Extract frames at uniform time intervals"""
        # Get video duration
        duration_cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(duration_cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip())

        # Calculate timestamps
        step = duration / (count + 1)
        timestamps = [step * (i + 1) for i in range(count)]

        # Extract frames
        frames = []
        for i, ts in enumerate(timestamps):
            output_file = str(Path(output_dir) / f"hybrid_uniform_{i:04d}.jpg")
            cmd = [
                'ffmpeg',
                '-ss', str(ts),
                '-i', video_path,
                '-vframes', '1',
                '-q:v', str(self.quality),
                '-y',
                output_file
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            frames.append(output_file)

        return frames

    def extract_and_select(
        self,
        video_path: str,
        output_dir: str,
        key_frame_count: int = 12,
        strategy: ExtractionStrategy = 'uniform'
    ) -> List[str]:
        """
        Extract frames and select key frames in one step

        Args:
            video_path: Path to input video
            output_dir: Directory for frame output
            key_frame_count: Number of key frames to select
            strategy: Extraction strategy ('uniform', 'scene', 'hybrid')

        Returns:
            List of selected key frame paths
        """
        if strategy == 'scene':
            return self.extract_frames_by_scene_detection(
                video_path, output_dir, key_frame_count
            )
        elif strategy == 'hybrid':
            return self.extract_frames_hybrid(
                video_path, output_dir, key_frame_count
            )
        else:  # uniform
            all_frames = self.extract_frames(video_path, output_dir)
            key_frames = self.select_key_frames(all_frames, key_frame_count)
            return key_frames


# Convenience function for single-use extraction
def extract_key_frames(
    video_path: str,
    output_dir: str,
    count: int = 12,
    max_frames: int = 180,
    strategy: ExtractionStrategy = 'uniform'
) -> List[str]:
    """
    Extract and select key frames from video

    Args:
        video_path: Path to video file
        output_dir: Output directory for frames
        count: Number of key frames to select
        max_frames: Maximum total frames to extract
        strategy: Extraction strategy ('uniform', 'scene', 'hybrid')

    Returns:
        List of key frame paths
    """
    extractor = FrameExtractor(max_frames=max_frames)
    return extractor.extract_and_select(video_path, output_dir, count, strategy)
