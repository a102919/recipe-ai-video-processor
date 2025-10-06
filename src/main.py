"""
Video Processor Service - FastAPI Application
Handles video frame extraction and Gemini Vision analysis for recipe extraction
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import tempfile
import shutil
import logging
from pathlib import Path
from dotenv import load_dotenv

from extractor import extract_key_frames
from analyzer import analyze_recipe_from_frames
from pipeline import analyze_recipe_from_url

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RecipeAI Video Processor",
    description="Video frame extraction and Gemini Vision analysis service",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
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
    gemini_key = os.getenv('GEMINI_API_KEY')
    checks['gemini_api_key'] = 'ok' if gemini_key else 'missing'

    # Overall status
    all_ok = all(v == 'ok' for v in checks.values())
    status = "ready" if all_ok else "not_ready"

    return {"status": status, "checks": checks}


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "RecipeAI Video Processor Service (Gemini Vision)"}


@app.post("/analyze")
async def analyze_video(
    video: UploadFile = File(...),
    video_url: str = Form(...)
):
    """
    Analyze cooking video using Gemini Vision API

    Process:
    1. Save uploaded video to temp file
    2. Extract frames at 1fps using FFmpeg
    3. Select 12 key frames (evenly distributed)
    4. Analyze with Gemini Vision API
    5. Return structured recipe JSON
    6. Cleanup temp files

    Returns:
        Recipe JSON with name, ingredients, steps, tags, completeness status
    """
    temp_dir = None
    video_path = None

    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix='recipeai_')
        logger.info(f"Created temp dir: {temp_dir}")

        # Save uploaded video
        video_path = os.path.join(temp_dir, f"video_{os.urandom(4).hex()}.mp4")
        with open(video_path, 'wb') as f:
            shutil.copyfileobj(video.file, f)
        logger.info(f"Saved video: {video_path}")

        # Extract key frames
        frames_dir = os.path.join(temp_dir, 'frames')
        key_frames = extract_key_frames(video_path, frames_dir, count=12)
        logger.info(f"Extracted {len(key_frames)} key frames")

        if not key_frames:
            raise HTTPException(
                status_code=400,
                detail="No frames could be extracted from video"
            )

        # Analyze with Gemini Vision
        recipe_data = analyze_recipe_from_frames(key_frames)
        logger.info(f"Analysis complete: {recipe_data.get('name', 'Unknown')}")

        return recipe_data

    except Exception as e:
        logger.error(f"Video analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Video analysis failed: {str(e)}"
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


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"Starting RecipeAI Video Processor on {host}:{port}")
    logger.info(f"Gemini API key configured: {bool(os.getenv('GEMINI_API_KEY'))}")

    uvicorn.run(app, host=host, port=port)
