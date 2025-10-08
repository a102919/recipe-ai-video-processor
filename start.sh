#!/bin/bash

# RecipeAI Video Processor - Quick Start Script

cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Start server
PORT=${PORT:-8001}
echo "Starting video processor on http://localhost:$PORT"
echo "API docs: http://localhost:$PORT/docs"
uvicorn src.main:app --reload --host 0.0.0.0 --port $PORT
