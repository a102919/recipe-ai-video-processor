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

# Gemini API configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Server configuration
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 8000))

# Worker configuration
UVICORN_WORKERS = int(os.getenv('UVICORN_WORKERS', 0))  # 0 means auto-detect

# CORS configuration
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*')
