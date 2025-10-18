#!/usr/bin/env python3
"""
Test script for streaming frame extraction
Tests the new fast path vs traditional download method
"""
import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.pipeline import analyze_recipe_from_url
from src.streaming_extractor import StreamingError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_streaming_extraction(test_url: str):
    """
    Test streaming extraction with timing comparison

    Args:
        test_url: YouTube or other video URL to test
    """
    print("=" * 80)
    print("TESTING STREAMING FRAME EXTRACTION")
    print("=" * 80)

    # Test 1: Streaming mode (fast path)
    print("\n" + "=" * 80)
    print("TEST 1: STREAMING MODE (Fast Path)")
    print("=" * 80)

    try:
        start_time = time.time()
        result_streaming = analyze_recipe_from_url(
            test_url,
            cleanup=True,
            extraction_mode='fast',
            use_streaming=True
        )
        streaming_time = time.time() - start_time

        print(f"\n✅ STREAMING EXTRACTION SUCCESSFUL")
        print(f"   Time taken: {streaming_time:.2f}s")
        print(f"   Recipe: {result_streaming.get('name', 'Unknown')}")
        print(f"   Extraction method: {result_streaming['metadata']['extraction_method']}")
        print(f"   Frames extracted: {result_streaming['metadata']['video_info']['frames_extracted']}")
        print(f"   Duration: {result_streaming['metadata']['video_info']['duration_seconds']}s")

    except Exception as e:
        print(f"\n❌ STREAMING EXTRACTION FAILED: {e}")
        streaming_time = None
        result_streaming = None

    # Test 2: Traditional download mode (for comparison)
    print("\n" + "=" * 80)
    print("TEST 2: TRADITIONAL DOWNLOAD MODE (Comparison)")
    print("=" * 80)

    try:
        start_time = time.time()
        result_traditional = analyze_recipe_from_url(
            test_url,
            cleanup=True,
            extraction_mode='fast',
            use_streaming=False  # Force traditional download
        )
        traditional_time = time.time() - start_time

        print(f"\n✅ TRADITIONAL DOWNLOAD SUCCESSFUL")
        print(f"   Time taken: {traditional_time:.2f}s")
        print(f"   Recipe: {result_traditional.get('name', 'Unknown')}")
        print(f"   Extraction method: {result_traditional['metadata']['extraction_method']}")
        print(f"   Frames extracted: {result_traditional['metadata']['video_info']['frames_extracted']}")

    except Exception as e:
        print(f"\n❌ TRADITIONAL DOWNLOAD FAILED: {e}")
        traditional_time = None
        result_traditional = None

    # Comparison
    print("\n" + "=" * 80)
    print("PERFORMANCE COMPARISON")
    print("=" * 80)

    if streaming_time and traditional_time:
        speedup = traditional_time / streaming_time
        time_saved = traditional_time - streaming_time

        print(f"\nStreaming time:   {streaming_time:.2f}s")
        print(f"Traditional time: {traditional_time:.2f}s")
        print(f"Time saved:       {time_saved:.2f}s ({time_saved/60:.1f} minutes)")
        print(f"Speedup:          {speedup:.1f}x faster")

        if speedup >= 3:
            print("\n🚀 EXCELLENT! Streaming is 3x+ faster than traditional method")
        elif speedup >= 2:
            print("\n✅ GOOD! Streaming is 2x+ faster than traditional method")
        else:
            print("\n⚠️  WARNING: Speedup is less than 2x, may need optimization")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    # Test URLs (short YouTube videos work best for testing)
    test_urls = [
        # Example: A short cooking video (replace with actual test URL)
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Replace with real cooking video
    ]

    if len(sys.argv) > 1:
        # Use URL from command line argument
        test_url = sys.argv[1]
        test_streaming_extraction(test_url)
    else:
        print("Usage: python test_streaming.py <VIDEO_URL>")
        print("\nExample:")
        print("  python test_streaming.py 'https://www.youtube.com/watch?v=...'")
        print("\nTesting with default URL...")
        test_streaming_extraction(test_urls[0])
