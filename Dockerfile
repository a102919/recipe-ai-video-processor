# 愛煮小幫手 Video Processor - Production Dockerfile
# Multi-stage build for optimized image size

# Stage 1: Base image with system dependencies
FROM python:3.11-slim as base

# Install FFmpeg and other system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Verify FFmpeg installation
RUN ffmpeg -version && ffprobe -version

# Stage 2: Dependencies installation
FROM base as dependencies

# Set working directory
WORKDIR /app

# Copy dependency files
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 3: Production image
FROM base as production

# Set working directory
WORKDIR /app

# Copy installed dependencies from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:${PORT}/health')" || exit 1

# Expose port
EXPOSE 8000

# Start command
# Use exec form to ensure proper signal handling
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT} --workers ${UVICORN_WORKERS:-4}"]
