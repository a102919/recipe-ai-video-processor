#!/bin/bash
#
# GCP Compute Engine Deployment Script
# Deploys video-processor to GCP VM using Docker Compose
#
# Usage:
#   ./deploy_gcp.sh          # Deploy latest code
#   ./deploy_gcp.sh --init   # First-time setup
#

set -e

# GCP Configuration
GCP_PROJECT="gen-lang-client-0768313457"
GCP_ZONE="us-central1-c"
GCP_VM="foodai"
DEPLOY_DIR="/home/alan/video-processor"

echo "=========================================="
echo "  RecipeAI Video Processor - GCP Deploy"
echo "=========================================="
echo ""

# Parse arguments
INIT_MODE=false
if [[ "$1" == "--init" ]]; then
    INIT_MODE=true
    echo "🔧 Running in INIT mode (first-time setup)"
else
    echo "🚀 Running in DEPLOY mode (update existing)"
fi
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI not found"
    echo "   Install: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Verify .env file exists locally
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "   Please create .env with required credentials"
    echo "   Reference: .env.example"
    exit 1
fi

echo "✅ Pre-flight checks passed"
echo ""

# Step 1: Test SSH connection
echo "🔄 Step 1/5: Testing SSH connection..."
gcloud compute ssh --zone "$GCP_ZONE" "$GCP_VM" --project "$GCP_PROJECT" --command "echo 'SSH connection successful'" || {
    echo "❌ SSH connection failed"
    exit 1
}
echo ""

# Step 2: Setup (if init mode)
if [ "$INIT_MODE" = true ]; then
    echo "🔄 Step 2/5: Initial setup on VM..."

    # Install Docker if not present
    gcloud compute ssh --zone "$GCP_ZONE" "$GCP_VM" --project "$GCP_PROJECT" --command "
        # Check if Docker is installed
        if ! command -v docker &> /dev/null; then
            echo '📦 Installing Docker...'
            sudo apt-get update
            sudo apt-get install -y docker.io docker-compose
            sudo systemctl start docker
            sudo systemctl enable docker
            sudo usermod -aG docker \$USER
            echo '✅ Docker installed'
        else
            echo '✅ Docker already installed'
        fi

        # Create deployment directory
        mkdir -p $DEPLOY_DIR
        echo '✅ Deployment directory created: $DEPLOY_DIR'
    "

    # Upload and install systemd service
    echo "📦 Installing systemd service for auto-start..."
    gcloud compute scp recipeai-video-processor.service "${GCP_VM}:/tmp/" \
        --zone "$GCP_ZONE" --project "$GCP_PROJECT"

    gcloud compute ssh --zone "$GCP_ZONE" "$GCP_VM" --project "$GCP_PROJECT" --command "
        sudo mv /tmp/recipeai-video-processor.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable recipeai-video-processor.service
        echo '✅ Systemd service installed and enabled'
        echo '   Service will auto-start on VM reboot'
    "

    echo ""
    echo "⚠️  IMPORTANT: You may need to log out and back in for Docker permissions"
    echo "   Run: gcloud compute ssh --zone '$GCP_ZONE' '$GCP_VM' --project '$GCP_PROJECT'"
    echo "   Then: exit and re-run this script"
    echo ""
else
    echo "⏭️  Step 2/5: Skipped (not in init mode)"
    echo ""
fi

# Step 3: Upload code and configuration
echo "🔄 Step 3/5: Uploading code to VM..."

# Create temporary archive
TEMP_ARCHIVE="/tmp/video-processor-$(date +%s).tar.gz"
tar -czf "$TEMP_ARCHIVE" \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='downloads' \
    --exclude='*.pyc' \
    --exclude='.env.local' \
    .

# Upload archive
gcloud compute scp "$TEMP_ARCHIVE" "${GCP_VM}:${DEPLOY_DIR}/deploy.tar.gz" \
    --zone "$GCP_ZONE" --project "$GCP_PROJECT"

# Extract on VM
gcloud compute ssh --zone "$GCP_ZONE" "$GCP_VM" --project "$GCP_PROJECT" --command "
    cd $DEPLOY_DIR
    tar -xzf deploy.tar.gz
    rm deploy.tar.gz
    echo '✅ Code extracted'
"

# Cleanup local archive
rm "$TEMP_ARCHIVE"

# Upload .env file separately (secure)
echo "🔒 Uploading .env file..."
gcloud compute scp .env "${GCP_VM}:${DEPLOY_DIR}/.env" \
    --zone "$GCP_ZONE" --project "$GCP_PROJECT"

echo ""

# Step 4: Build and deploy
echo "🔄 Step 4/5: Building Docker image..."
gcloud compute ssh --zone "$GCP_ZONE" "$GCP_VM" --project "$GCP_PROJECT" --command "
    cd $DEPLOY_DIR

    # Stop existing container (if any)
    docker-compose down 2>/dev/null || true

    # Build fresh image (NO CACHE)
    echo '🔨 Building Docker image (this may take 2-3 minutes)...'
    docker-compose build --no-cache

    echo '✅ Build complete'
"
echo ""

# Step 5: Start service
echo "🔄 Step 5/5: Starting service..."
gcloud compute ssh --zone "$GCP_ZONE" "$GCP_VM" --project "$GCP_PROJECT" --command "
    cd $DEPLOY_DIR

    # Start container
    docker-compose up -d

    # Wait for health check
    echo 'Waiting for service to be healthy...'
    sleep 5

    # Show status
    docker-compose ps

    echo ''
    echo '📊 Recent logs:'
    docker-compose logs --tail=20
"
echo ""

# Get VM external IP
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
echo "Useful commands:"
echo "  View logs:    gcloud compute ssh --zone '$GCP_ZONE' '$GCP_VM' --project '$GCP_PROJECT' --command 'cd $DEPLOY_DIR && docker-compose logs -f'"
echo "  Restart:      gcloud compute ssh --zone '$GCP_ZONE' '$GCP_VM' --project '$GCP_PROJECT' --command 'cd $DEPLOY_DIR && docker-compose restart'"
echo "  Stop:         gcloud compute ssh --zone '$GCP_ZONE' '$GCP_VM' --project '$GCP_PROJECT' --command 'cd $DEPLOY_DIR && docker-compose down'"
echo "  SSH into VM:  gcloud compute ssh --zone '$GCP_ZONE' '$GCP_VM' --project '$GCP_PROJECT'"
echo ""
echo "Next steps:"
echo "  1. Test the service: curl http://${EXTERNAL_IP}:8000/health"
echo "  2. Configure firewall rule to allow port 8000 (if needed)"
echo "  3. Update your backend to use: http://${EXTERNAL_IP}:8000"
echo ""
