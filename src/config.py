"""
Configuration management for video processor
Centralizes environment variables and default values
"""
import os
from dotenv import load_dotenv

load_dotenv()

# R2 storage configuration
R2_COOKIES_BASE_URL = os.getenv(
    'R2_COOKIES_BASE_URL',
    'https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails'
)

# Gemini API configuration (backward compatible)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_API_KEYS = os.getenv('GEMINI_API_KEYS', GEMINI_API_KEY or '')

# Grok (xAI) API configuration
GROK_API_KEY = os.getenv('GROK_API_KEY')
GROK_API_KEYS = os.getenv('GROK_API_KEYS', GROK_API_KEY or '')

# OpenAI API configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_API_KEYS = os.getenv('OPENAI_API_KEYS', OPENAI_API_KEY or '')

# LLM Provider priority (comma-separated, e.g., "gemini,grok,openai")
LLM_PROVIDER_PRIORITY = os.getenv('LLM_PROVIDER_PRIORITY', 'gemini,grok,openai')

# Server configuration
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 8000))

# Worker configuration
UVICORN_WORKERS = int(os.getenv('UVICORN_WORKERS', 0))  # 0 means auto-detect

# CORS configuration
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*')

# Processor mode configuration
PROCESSOR_MODE = os.getenv('PROCESSOR_MODE', 'passive')  # 'passive' or 'active'
BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'http://localhost:3000')
POLL_INTERVAL_MS = int(os.getenv('POLL_INTERVAL_MS', 60000))  # 60 seconds default

# Frame extraction mode configuration
EXTRACTION_MODE = os.getenv('EXTRACTION_MODE', 'balanced')  # 'fast', 'balanced', or 'accurate'
