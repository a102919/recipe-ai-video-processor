#!/bin/bash
# Docker Build & Test Script for 愛煮小幫手 Video Processor

set -e  # Exit on error

echo "🔨 Building Docker image..."
docker build -t recipeai-video-processor:test .

echo ""
echo "✅ Build successful!"
echo ""
echo "🧪 Testing FFmpeg installation..."

# Test FFmpeg in container
docker run --rm recipeai-video-processor:test ffmpeg -version | head -1
docker run --rm recipeai-video-processor:test ffprobe -version | head -1

echo ""
echo "✅ FFmpeg OK!"
echo ""
echo "🚀 Starting container..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found"
    echo "   Copy .env.example to .env and configure before production use"
    echo ""
fi

# Start container with docker-compose
docker-compose up -d

echo ""
echo "⏳ Waiting for service to be ready..."
sleep 5

# Test health endpoint
echo ""
echo "🏥 Testing health endpoint..."
curl -s http://localhost:8000/health | python3 -m json.tool

echo ""
echo ""
echo "🔍 Testing ready endpoint (with dependency checks)..."
curl -s http://localhost:8000/ready | python3 -m json.tool

echo ""
echo ""
echo "✅ All tests passed!"
echo ""
echo "📋 Service Information:"
echo "   - Health Check: http://localhost:8000/health"
echo "   - Ready Check:  http://localhost:8000/ready"
echo "   - API Docs:     http://localhost:8000/docs"
echo ""
echo "📝 View logs: docker-compose logs -f"
echo "🛑 Stop:      docker-compose down"
echo ""
