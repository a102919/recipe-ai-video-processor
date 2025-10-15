#!/bin/bash

# 愛煮小幫手 Video Processor - Quick Start Script

set -e
cd "$(dirname "$0")"

echo "🚀 Starting 愛煮小幫手 Video Processor..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found"
    echo "   Creating .env from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "   ✅ .env created. Please edit it and add your API keys:"
        echo "      - GEMINI_API_KEY or GEMINI_API_KEYS"
        echo "      - GROK_API_KEYS (optional)"
        echo "      - OPENAI_API_KEYS (optional)"
        exit 1
    else
        echo "   ❌ .env.example not found"
        exit 1
    fi
fi

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Check if LangChain is installed
echo "🔍 Checking dependencies..."
if ! pip show langchain-core &> /dev/null; then
    echo "📥 Installing dependencies (this may take a minute)..."
    pip install -q -r requirements.txt
else
    echo "✅ Dependencies already installed"
fi

# Check API keys
echo "🔑 Checking API key configuration..."
API_KEY_CONFIGURED=0
if grep -q "^GEMINI_API_KEY=\|^GEMINI_API_KEYS=" .env 2>/dev/null; then
    if ! grep -q "your_gemini_api_key_here" .env 2>/dev/null; then
        echo "✅ Gemini API key configured"
        API_KEY_CONFIGURED=1
    fi
fi
if grep -q "^GROK_API_KEYS=" .env 2>/dev/null; then
    echo "✅ Grok API key configured"
    API_KEY_CONFIGURED=1
fi
if grep -q "^OPENAI_API_KEYS=" .env 2>/dev/null; then
    echo "✅ OpenAI API key configured"
    API_KEY_CONFIGURED=1
fi

if [ $API_KEY_CONFIGURED -eq 0 ]; then
    echo "⚠️  Warning: No LLM API keys configured in .env"
    echo "   Please configure at least one of:"
    echo "      - GEMINI_API_KEY or GEMINI_API_KEYS"
    echo "      - GROK_API_KEYS"
    echo "      - OPENAI_API_KEYS"
    exit 1
fi

# Start server
PORT=${PORT:-8000}
echo ""
echo "✅ Starting uvicorn server..."
echo "   🌐 URL:  http://localhost:$PORT"
echo "   📚 Docs: http://localhost:$PORT/docs"
echo "   💡 Health: http://localhost:$PORT/health"
echo ""
echo "Press Ctrl+C to stop"
echo ""

uvicorn src.main:app --reload --host 0.0.0.0 --port $PORT
