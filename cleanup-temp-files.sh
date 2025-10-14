#!/bin/bash
# Cleanup temporary files created by video-processor
# This script removes old temporary files to prevent disk/memory accumulation
# Run this periodically via cron (e.g., every hour)

set -e

LOG_PREFIX="[cleanup-temp-files]"

echo "$LOG_PREFIX Starting temporary file cleanup..."

# Cleanup recipeai temporary directories older than 1 hour
# These are created by tempfile.mkdtemp() in pipeline.py and main.py
find /tmp -name "recipeai_*" -type d -mmin +60 -print0 2>/dev/null | while IFS= read -r -d '' dir; do
    echo "$LOG_PREFIX Removing old temp directory: $dir"
    rm -rf "$dir" || echo "$LOG_PREFIX Warning: Failed to remove $dir"
done

# Cleanup aizhu-helper directory (used by thumbnail_generator.py)
if [ -d "/tmp/aizhu-helper" ]; then
    echo "$LOG_PREFIX Cleaning /tmp/aizhu-helper..."
    find /tmp/aizhu-helper -type f -mmin +60 -delete 2>/dev/null || true
fi

# Cleanup FFmpeg temp files (sometimes FFmpeg leaves temp files)
find /tmp -name "ffmpeg*" -type f -mmin +60 -delete 2>/dev/null || true

# Cleanup yt-dlp temp files
find /tmp -name "yt-dlp*" -type f -mmin +60 -delete 2>/dev/null || true
find /tmp -name "tmpyt*" -type f -mmin +60 -delete 2>/dev/null || true

echo "$LOG_PREFIX Cleanup completed"

# Show disk usage of /tmp
echo "$LOG_PREFIX Current /tmp disk usage:"
du -sh /tmp 2>/dev/null || echo "$LOG_PREFIX (du command failed)"
