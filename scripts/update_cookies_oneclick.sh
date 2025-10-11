#!/bin/bash
#
# One-Click Cookie Update Script
# Extracts YouTube cookies from Chrome and uploads to R2
#
# Usage: ./update_cookies_oneclick.sh
#

set -e

echo "=========================================="
echo "  YouTube Cookies One-Click Update"
echo "=========================================="
echo ""

# Check requirements
if ! command -v yt-dlp &> /dev/null; then
    echo "❌ Error: yt-dlp not found"
    echo "   Install: pip install yt-dlp"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 not found"
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "   Please create .env with R2 credentials"
    exit 1
fi

# Step 1: Extract cookies from Chrome
echo "🔄 Step 1/3: Extracting cookies from Chrome..."
echo "   (Make sure you're logged into YouTube in Chrome)"
echo ""

yt-dlp --cookies-from-browser chrome \
       --cookies youtube_cookies_only.txt \
       "https://www.youtube.com/" \
       2>&1 | grep -E "(Extracted|cookies)" || true

if [ ! -f "youtube_cookies_only.txt" ]; then
    echo "❌ Failed to extract cookies"
    echo "   Make sure:"
    echo "   1. You're logged into YouTube in Chrome"
    echo "   2. Chrome is not running (close it first)"
    echo "   3. You have the latest yt-dlp: pip install -U yt-dlp"
    exit 1
fi

# Verify cookies file
COOKIE_COUNT=$(wc -l < youtube_cookies_only.txt)
if [ "$COOKIE_COUNT" -lt 10 ]; then
    echo "❌ Cookies file seems invalid (only $COOKIE_COUNT lines)"
    rm youtube_cookies_only.txt
    exit 1
fi

echo "✅ Extracted $COOKIE_COUNT cookie entries"
echo ""

# Step 2: Upload to R2
echo "🔄 Step 2/3: Uploading to Cloudflare R2..."
echo ""

python3 scripts/upload_youtube_cookies.py

if [ $? -ne 0 ]; then
    echo "❌ Upload failed"
    rm youtube_cookies_only.txt
    exit 1
fi

echo ""

# Step 3: Verify
echo "🔄 Step 3/3: Verifying upload..."
echo ""

# Load R2 URL from config
source .env
COOKIES_URL="${R2_COOKIES_BASE_URL}/www.youtube.com_cookies.txt"

echo "Testing R2 URL: $COOKIES_URL"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$COOKIES_URL")

if [ "$HTTP_CODE" == "200" ]; then
    echo "✅ Cookies successfully uploaded and accessible"
else
    echo "⚠️  Warning: HTTP $HTTP_CODE when accessing cookies URL"
    echo "   URL: $COOKIES_URL"
fi

# Cleanup
rm youtube_cookies_only.txt
echo ""

echo "=========================================="
echo "✅ Cookie Update Complete!"
echo "=========================================="
echo ""
echo "Summary:"
echo "  - Extracted $COOKIE_COUNT cookies from Chrome"
echo "  - Uploaded to R2"
echo "  - Service will use new cookies automatically"
echo "  - No restart required!"
echo ""
echo "Next update recommended: $(date -v+3m '+%Y-%m-%d')"
echo "(Set a reminder for 3 months from now)"
echo ""
