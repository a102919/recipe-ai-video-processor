#!/bin/bash
#
# GCP Free Tier Deployment Script
# Modified for ephemeral IP (no static IP charges)
#

set -e

# GCP Configuration
GCP_PROJECT="gen-lang-client-0768313457"
GCP_ZONE="us-central1-c"
GCP_VM="foodai-free"  # New free-tier VM
DEPLOY_DIR="/home/alan/video-processor"

echo "=========================================="
echo "  RecipeAI Video Processor - FREE Deploy"
echo "=========================================="
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI not found"
    exit 1
fi

# Verify .env.gcp file exists locally
if [ ! -f ".env.gcp" ]; then
    echo "❌ Error: .env.gcp file not found (copy from .env.gcp.example)"
    exit 1
fi

echo "✅ Pre-flight checks passed"
echo ""

# Step 1: Test SSH connection
echo "🔄 Step 1/4: Testing SSH connection..."
gcloud compute ssh --zone "$GCP_ZONE" "$GCP_VM" --project "$GCP_PROJECT" \
    --command "echo 'SSH connection successful'" || {
    echo "❌ SSH connection failed"
    exit 1
}
echo ""

# Step 2: Upload code
echo "🔄 Step 2/4: Uploading code to VM..."
TEMP_ARCHIVE="/tmp/video-processor-$(date +%s).tar.gz"
tar -czf "$TEMP_ARCHIVE" \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='downloads' \
    --exclude='*.pyc' \
    --exclude='.env.local' \
    --exclude='.env.gcp' \
    --exclude='venv' \
    .

gcloud compute scp "$TEMP_ARCHIVE" "${GCP_VM}:${DEPLOY_DIR}/deploy.tar.gz" \
    --zone "$GCP_ZONE" --project "$GCP_PROJECT"

gcloud compute ssh --zone "$GCP_ZONE" "$GCP_VM" --project "$GCP_PROJECT" --command "
    mkdir -p $DEPLOY_DIR
    cd $DEPLOY_DIR
    tar -xzf deploy.tar.gz
    rm deploy.tar.gz
    echo '✅ Code extracted'
"

rm "$TEMP_ARCHIVE"

# Upload .env.gcp
echo "🔒 Uploading .env.gcp file..."
gcloud compute scp .env.gcp "${GCP_VM}:${DEPLOY_DIR}/.env" \
    --zone "$GCP_ZONE" --project "$GCP_PROJECT"
echo ""

# Step 3: Build Docker image
echo "🔄 Step 3/4: Building Docker image..."
gcloud compute ssh --zone "$GCP_ZONE" "$GCP_VM" --project "$GCP_PROJECT" --command "
    cd $DEPLOY_DIR
    docker-compose down 2>/dev/null || true
    docker-compose build --no-cache
    echo '✅ Build complete'
"
echo ""

# Step 4: Start service
echo "🔄 Step 4/4: Starting service..."
gcloud compute ssh --zone "$GCP_ZONE" "$GCP_VM" --project "$GCP_PROJECT" --command "
    cd $DEPLOY_DIR
    docker-compose up -d
    sleep 5
    docker-compose ps
    echo ''
    echo '📊 Recent logs:'
    docker-compose logs --tail=20
"
echo ""

# Get current ephemeral IP
EXTERNAL_IP=$(gcloud compute instances describe "$GCP_VM" \
    --zone "$GCP_ZONE" \
    --project "$GCP_PROJECT" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "Service URL: http://${EXTERNAL_IP}:8000"
echo "Health Check: http://${EXTERNAL_IP}:8000/health"
echo ""
echo "⚠️  Note: This is an ephemeral IP (FREE but may change)"
echo "   Current IP: $EXTERNAL_IP"
echo ""
echo "Useful commands:"
echo "  View logs:  gcloud compute ssh --zone '$GCP_ZONE' '$GCP_VM' --project '$GCP_PROJECT' --command 'cd $DEPLOY_DIR && docker-compose logs -f'"
echo "  Restart:    gcloud compute ssh --zone '$GCP_ZONE' '$GCP_VM' --project '$GCP_PROJECT' --command 'cd $DEPLOY_DIR && docker-compose restart'"
echo "  Stop:       gcloud compute ssh --zone '$GCP_ZONE' '$GCP_VM' --project '$GCP_PROJECT' --command 'cd $DEPLOY_DIR && docker-compose down'"
echo ""
