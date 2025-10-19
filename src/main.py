"""
Video Processor Service - FastAPI Application
Handles video frame extraction and Gemini Vision analysis for recipe extraction
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import tempfile
import shutil
import logging
import asyncio
import gc
from pathlib import Path
from typing import Dict, Any

from .extractor import extract_key_frames
from .analyzer import analyze_recipe_from_frames
from .pipeline import analyze_recipe_from_url
from .video_utils import get_video_metadata
from .thumbnail_generator import ThumbnailProxy
from .config import (
    ALLOWED_ORIGINS,
    GEMINI_API_KEY,
    PROCESSOR_MODE,
    BACKEND_API_URL,
    POLL_INTERVAL_MS
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Memory optimization: More aggressive garbage collection for e2-micro (1GB RAM)
gc.set_threshold(400, 5, 5)  # More aggressive than default (700, 10, 10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Start active mode worker if configured
    """
    # Startup
    if PROCESSOR_MODE == "active":
        logger.info(f"[Active Mode] Starting in ACTIVE mode")
        logger.info(f"[Active Mode] Will poll {BACKEND_API_URL} every {POLL_INTERVAL_MS}ms")
        # Start active mode worker as background task
        task = asyncio.create_task(active_mode_worker())
    else:
        logger.info(f"[Passive Mode] Starting in PASSIVE mode (default)")
        logger.info(f"[Passive Mode] Waiting for requests on /analyze and /analyze-from-url endpoints")
        task = None

    yield

    # Shutdown
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="愛煮小幫手 Video Processor",
    description="Video frame extraction and Gemini Vision analysis service",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "video-processor"}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint with dependency validation"""
    checks = {}

    # Check FFmpeg availability
    try:
        import subprocess
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        checks['ffmpeg'] = 'ok'
    except Exception as e:
        checks['ffmpeg'] = f'error: {str(e)}'

    # Check Gemini API key
    checks['gemini_api_key'] = 'ok' if GEMINI_API_KEY else 'missing'

    # Overall status
    all_ok = all(v == 'ok' for v in checks.values())
    status = "ready" if all_ok else "not_ready"

    return {"status": status, "checks": checks}


def _upload_thumbnail(file_path: str) -> str | None:
    """
    Upload thumbnail to R2, return URL or None

    Args:
        file_path: Path to image file to upload

    Returns:
        Thumbnail URL or None if upload fails
    """
    try:
        logger.info(f"Uploading thumbnail to R2: {file_path}")
        proxy = ThumbnailProxy()
        thumbnail_url = proxy.upload_to_r2(file_path)
        logger.info(f"Thumbnail uploaded: {thumbnail_url}")
        return thumbnail_url
    except Exception as e:
        logger.warning(f"Failed to upload thumbnail: {e}")
        return None


def _build_response(
    recipe_data: Dict[str, Any],
    usage_metadata: Dict[str, Any],
    thumbnail_url: str | None,
    video_info: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build standardized response with recipe and metadata

    Args:
        recipe_data: Parsed recipe data from Gemini
        usage_metadata: Token usage information
        thumbnail_url: R2 thumbnail URL or None
        video_info: Video/image file information

    Returns:
        Complete response dictionary
    """
    return {
        **recipe_data,
        'thumbnail_url': thumbnail_url,
        'metadata': {
            'llm_usage': usage_metadata,  # Renamed from 'gemini_tokens' to be provider-agnostic
            'video_info': video_info
        }
    }


def _process_image(file_path: str, file_size: int) -> Dict[str, Any]:
    """
    Process single image file

    Args:
        file_path: Path to image file
        file_size: File size in bytes

    Returns:
        Response dictionary with recipe and metadata
    """
    logger.info("Processing as single image")

    # Analyze single image
    analysis_result = analyze_recipe_from_frames([file_path])
    recipe_data = analysis_result['recipe']
    usage_metadata = analysis_result['usage_metadata']

    logger.info(f"Analysis complete: {recipe_data.get('name', 'Unknown')}")
    # Log provider info (LangChain format)
    if 'provider' in usage_metadata:
        logger.info(f"LLM Provider: {usage_metadata['provider']}")
    elif 'total_tokens' in usage_metadata:
        logger.info(f"Token usage: {usage_metadata['total_tokens']} tokens")

    # Upload thumbnail
    thumbnail_url = _upload_thumbnail(file_path)

    # Build and return response
    return _build_response(
        recipe_data,
        usage_metadata,
        thumbnail_url,
        video_info={
            'duration_seconds': 0,  # Images have no duration
            'file_size_bytes': file_size,
            'frames_extracted': 1,
            'frames_analyzed': 1
        }
    )


def _process_video(file_path: str, file_size: int, temp_dir: str) -> Dict[str, Any]:
    """
    Process video file

    Args:
        file_path: Path to video file
        file_size: File size in bytes
        temp_dir: Temporary directory for frame extraction

    Returns:
        Response dictionary with recipe and metadata
    """
    logger.info("Processing as video")

    # Get video metadata
    metadata = get_video_metadata(file_path)
    video_duration = metadata['duration']
    logger.info(f"Video file size: {file_size} bytes")
    logger.info(f"Video duration: {video_duration}s")

    # Extract key frames
    frames_dir = os.path.join(temp_dir, 'frames')
    all_frames = extract_key_frames(file_path, frames_dir, count=12)
    logger.info(f"Extracted {len(all_frames)} frames")

    if not all_frames:
        raise HTTPException(
            status_code=400,
            detail="No frames could be extracted from video"
        )

    # Analyze with LLM (multi-provider support)
    analysis_result = analyze_recipe_from_frames(all_frames)
    recipe_data = analysis_result['recipe']
    usage_metadata = analysis_result['usage_metadata']

    logger.info(f"Analysis complete: {recipe_data.get('name', 'Unknown')}")
    # Log provider info (LangChain format)
    if 'provider' in usage_metadata:
        logger.info(f"LLM Provider: {usage_metadata['provider']}")
    elif 'total_tokens' in usage_metadata:
        logger.info(f"Token usage: {usage_metadata['total_tokens']} tokens")

    # Upload thumbnail (use first frame)
    thumbnail_url = _upload_thumbnail(all_frames[0])

    # Build and return response
    return _build_response(
        recipe_data,
        usage_metadata,
        thumbnail_url,
        video_info={
            'duration_seconds': video_duration,
            'file_size_bytes': file_size,
            'frames_extracted': len(all_frames),
            'frames_analyzed': len(all_frames)
        }
    )


def _is_image_file(content_type: str, filename: str) -> bool:
    """
    Detect if uploaded file is an image

    Args:
        content_type: MIME content type
        filename: Original filename

    Returns:
        True if file is an image
    """
    return (
        content_type.startswith('image/') or
        filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
    )


def _save_uploaded_file(upload: UploadFile, temp_dir: str, is_image: bool) -> str:
    """
    Save uploaded file to temporary directory

    Args:
        upload: FastAPI UploadFile object
        temp_dir: Temporary directory path
        is_image: Whether file is an image

    Returns:
        Path to saved file
    """
    if is_image:
        ext = '.jpg'  # Default to jpg for images
        if upload.filename and upload.filename.lower().endswith('.png'):
            ext = '.png'
        file_path = os.path.join(temp_dir, f"image_{os.urandom(4).hex()}{ext}")
    else:
        file_path = os.path.join(temp_dir, f"video_{os.urandom(4).hex()}.mp4")

    with open(file_path, 'wb') as f:
        shutil.copyfileobj(upload.file, f)

    logger.info(f"Saved {'image' if is_image else 'video'}: {file_path}")
    return file_path


@app.post("/analyze")
async def analyze_video(video: UploadFile = File(...)):
    """
    Analyze cooking video or image using Gemini Vision API

    Process:
    1. Save uploaded file to temp directory
    2. Detect if image or video
    3. Route to appropriate processor (image or video)
    4. Return structured recipe JSON with metadata
    5. Cleanup temp files

    Args:
        video: Uploaded video or image file

    Returns:
        Recipe JSON with name, ingredients, steps, tags, and metadata
    """
    temp_dir = None

    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix='recipeai_')
        logger.info(f"Created temp dir: {temp_dir}")

        # Detect file type
        content_type = video.content_type or ''
        filename = video.filename or ''
        is_image = _is_image_file(content_type, filename)

        # Save uploaded file
        file_path = _save_uploaded_file(video, temp_dir, is_image)
        file_size = os.path.getsize(file_path)

        # Route to appropriate processor
        if is_image:
            return _process_image(file_path, file_size)
        else:
            return _process_video(file_path, file_size, temp_dir)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Media analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Media analysis failed: {str(e)}"
        )

    finally:
        # Cleanup temp files
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temp dir: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {temp_dir}: {e}")


@app.post("/analyze-from-url")
async def analyze_video_from_url(video_url: str = Form(...)):
    """
    Analyze cooking video from URL using Gemini Vision API

    Process:
    1. Download video from URL (YouTube, Instagram, Facebook, etc.)
    2. Extract frames at 1fps using FFmpeg
    3. Select 12 key frames (evenly distributed)
    4. Analyze with Gemini Vision API
    5. Return structured recipe JSON
    6. Cleanup temp files

    Args:
        video_url: Video URL (supports YouTube, Instagram, Facebook, etc.)

    Returns:
        Recipe JSON with name, ingredients, steps, tags, completeness status
    """
    try:
        logger.info(f"Analyzing video from URL: {video_url}")

        # Use pipeline to handle download -> extract -> analyze
        recipe_data = analyze_recipe_from_url(video_url, cleanup=True)

        logger.info(f"Analysis complete: {recipe_data.get('name', 'Unknown')}")
        return recipe_data

    except ValueError as e:
        logger.error(f"Invalid input: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Video analysis from URL failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Video analysis failed: {str(e)}"
        )


# ============================================================================
# Active Mode Worker Logic
# ============================================================================

async def process_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single failed analysis job

    Args:
        job: Job data from backend API

    Returns:
        Result dict with recipe and metadata

    Raises:
        ValueError: If input validation fails
        NotImplementedError: If processing method not available
        Exception: If video analysis fails
    """
    job_id = job['job_id']
    video_url = job.get('video_url')
    video_file_id = job.get('video_file_id')

    logger.info(f"[Active Mode] Processing job {job_id}")

    # Choose processing method based on input type
    if video_url:
        logger.info(f"[Active Mode] Analyzing from URL: {video_url}")
        # Use existing analyze_recipe_from_url function
        recipe_data = analyze_recipe_from_url(video_url, cleanup=True)

        return {
            'recipe': recipe_data,
            'metadata': recipe_data.get('metadata')
        }
    elif video_file_id:
        # TODO: Implement LINE video download if needed
        raise NotImplementedError("LINE video_file_id processing not yet implemented in active mode")
    else:
        raise ValueError("No video_url or video_file_id provided")


async def _report_job_failure(
    client,
    job_id: str,
    error_message: str,
    error_type: str = "unknown",
    retries: int = 3
) -> bool:
    """
    Report job failure to backend with retry logic

    Args:
        client: httpx AsyncClient
        job_id: Job ID
        error_message: Error description
        error_type: Type of error (validation, processing, network, etc.)
        retries: Number of retry attempts

    Returns:
        True if failure was reported successfully, False if all retries failed
    """
    for attempt in range(retries):
        try:
            failure_payload = {
                'error_type': error_type,
                'error_message': error_message,
                'timestamp': str(__import__('datetime').datetime.utcnow().isoformat())
            }

            logger.info(
                f"[Active Mode] Reporting failure for job {job_id} "
                f"(attempt {attempt + 1}/{retries}): {error_type}"
            )

            resp = await client.put(
                f"{BACKEND_API_URL}/v1/analysis/{job_id}/failure",
                json=failure_payload,
                timeout=30.0
            )

            if resp.status_code == 200:
                logger.info(f"[Active Mode] ✅ Failure reported for job {job_id}")
                return True
            else:
                logger.warning(
                    f"[Active Mode] Failed to report failure for job {job_id}: "
                    f"{resp.status_code} - {resp.text[:200]}"
                )

                # Exponential backoff before retry
                if attempt < retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"[Active Mode] Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)

        except Exception as e:
            logger.warning(
                f"[Active Mode] Error reporting failure for job {job_id}: {str(e)}"
            )
            if attempt < retries - 1:
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)

    logger.error(
        f"[Active Mode] ❌ Failed to report failure for job {job_id} "
        f"after {retries} attempts"
    )
    return False


async def active_mode_worker():
    """
    Active mode worker that polls backend API for failed jobs
    Runs indefinitely until application shutdown

    Flow:
    1. Poll backend for failed jobs
    2. Process each job (analyze video/images)
    3. On success: Submit result via PUT /v1/analysis/{job_id}/result
    4. On failure (first attempt): Do not report, just skip on next poll
    5. Silent failure handling - no user notification after retry fails
    """
    import httpx
    import time

    poll_interval_seconds = POLL_INTERVAL_MS / 1000
    logger.info(f"[Active Mode] Starting active worker (poll interval: {poll_interval_seconds}s)")
    logger.info(f"[Active Mode] Backend API: {BACKEND_API_URL}")

    # Local tracking of already-failed jobs to prevent infinite retry
    processed_failures = set()
    last_reset_time = time.time()
    RESET_INTERVAL_HOURS = 24
    RESET_INTERVAL_SECONDS = RESET_INTERVAL_HOURS * 3600

    while True:
        try:
            # Reset processed failures every 24 hours
            current_time = time.time()
            if current_time - last_reset_time > RESET_INTERVAL_SECONDS:
                logger.info(f"[Active Mode] Resetting processed failures (tracked {len(processed_failures)} jobs)")
                processed_failures.clear()
                last_reset_time = current_time

            async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout
                # 1. Poll for failed jobs
                logger.info(f"[Active Mode] Polling for failed jobs... (currently tracking {len(processed_failures)} failed retries)")
                resp = await client.get(
                    f"{BACKEND_API_URL}/v1/analysis/failed",
                    params={"limit": 3}
                )

                if resp.status_code != 200:
                    logger.error(f"[Active Mode] Failed to fetch jobs: {resp.status_code} - {resp.text}")
                    await asyncio.sleep(poll_interval_seconds)
                    continue

                # Parse JSON response with error handling
                try:
                    response_text = resp.text
                    if not response_text or response_text.strip() == '':
                        logger.warning("[Active Mode] Backend returned empty response, waiting for next poll...")
                        await asyncio.sleep(poll_interval_seconds)
                        continue

                    data = resp.json()
                except Exception as e:
                    logger.error(f"[Active Mode] Failed to parse JSON response: {e}")
                    logger.error(f"[Active Mode] Response status: {resp.status_code}")
                    logger.error(f"[Active Mode] Response text (first 500 chars): {response_text[:500] if response_text else 'None'}")
                    await asyncio.sleep(poll_interval_seconds)
                    continue

                jobs = data.get('jobs', [])

                if not jobs:
                    logger.info("[Active Mode] No failed jobs found")
                    await asyncio.sleep(poll_interval_seconds)
                    continue

                logger.info(f"[Active Mode] Found {len(jobs)} failed jobs")

                # 2. Process each job
                for job in jobs:
                    job_id = job['job_id']

                    # Skip if this job has already failed retry once
                    if job_id in processed_failures:
                        logger.info(f"[Active Mode] ⏭️  Skipping job {job_id} (already failed retry, silently ignoring)")
                        continue

                    try:
                        # Process the job
                        result = await process_job(job)

                        # 3. Submit result back to backend (success path)
                        logger.info(f"[Active Mode] Submitting result for job {job_id}")
                        submit_resp = await client.put(
                            f"{BACKEND_API_URL}/v1/analysis/{job_id}/result",
                            json=result,
                            timeout=30.0
                        )

                        if submit_resp.status_code == 200:
                            logger.info(f"[Active Mode] ✅ Job {job_id} completed successfully")
                        else:
                            # Failed to submit result - mark as processed failure but don't report
                            error_msg = (
                                f"Failed to submit result: "
                                f"{submit_resp.status_code} - {submit_resp.text[:200]}"
                            )
                            logger.error(f"[Active Mode] Job {job_id} submission failed (silent): {error_msg}")
                            processed_failures.add(job_id)

                    except ValueError as e:
                        # Input validation error - silent failure
                        error_msg = f"Invalid job input: {str(e)}"
                        logger.error(f"[Active Mode] Job {job_id} validation error (silent): {error_msg}")
                        processed_failures.add(job_id)

                    except NotImplementedError as e:
                        # Feature not implemented - silent failure
                        error_msg = f"Feature not implemented: {str(e)}"
                        logger.error(f"[Active Mode] Job {job_id} not implemented (silent): {error_msg}")
                        processed_failures.add(job_id)

                    except Exception as e:
                        # Generic processing error - silent failure
                        error_msg = str(e)
                        logger.error(
                            f"[Active Mode] Job {job_id} processing failed (silent): {error_msg}",
                            exc_info=True
                        )
                        processed_failures.add(job_id)

        except Exception as e:
            logger.error(f"[Active Mode] Polling error: {str(e)}", exc_info=True)

        # Wait before next poll
        await asyncio.sleep(poll_interval_seconds)


if __name__ == "__main__":
    import uvicorn
    import multiprocessing
    from .config import HOST, PORT, UVICORN_WORKERS

    # Calculate workers based on CPU cores if not specified
    cpu_count = multiprocessing.cpu_count()
    workers = UVICORN_WORKERS if UVICORN_WORKERS > 0 else cpu_count * 2

    logger.info(f"Starting 愛煮小幫手 Video Processor on {HOST}:{PORT}")
    logger.info(f"Gemini API key configured: {bool(GEMINI_API_KEY)}")
    logger.info(f"CPU cores detected: {cpu_count}, starting {workers} workers")

    # Use import string format to enable workers functionality
    uvicorn.run(
        "src.main:app",
        host=HOST,
        port=PORT,
        workers=workers
    )
