# GCP Compute Engine Deployment Guide

This guide explains how to deploy the video-processor service to GCP Compute Engine using Docker Compose.

## Why GCP Compute Engine?

After encountering persistent Docker cache issues with Zeabur serverless platform, we migrated to GCP Compute Engine for:

1. **Full Control**: Direct access to Docker build process, no black-box caching
2. **Reliability**: Guaranteed code updates on every deployment
3. **Debugging**: SSH access for immediate troubleshooting
4. **Cost-Effective**: Fixed pricing for predictable workloads
5. **Auto-Recovery**: Systemd service ensures automatic startup on VM reboot and crash recovery

## Architecture

```
┌─────────────────────────────────────┐
│   GCP Compute Engine (foodai)      │
│   Zone: us-central1-c               │
│                                     │
│   ┌─────────────────────────────┐  │
│   │   Docker Container          │  │
│   │   recipeai-video-processor  │  │
│   │                             │  │
│   │   Port: 8000                │  │
│   │   Workers: 2 (uvicorn)      │  │
│   │   Image: video-processor    │  │
│   └─────────────────────────────┘  │
│                                     │
│   External IP: xxx.xxx.xxx.xxx     │
└─────────────────────────────────────┘
```

## Prerequisites

1. **GCP CLI (`gcloud`)**
   ```bash
   # macOS
   brew install --cask google-cloud-sdk

   # Linux
   curl https://sdk.cloud.google.com | bash

   # Verify
   gcloud --version
   ```

2. **GCP Authentication**
   ```bash
   gcloud auth login
   gcloud config set project gen-lang-client-0768313457
   ```

3. **Environment Variables**
   ```bash
   # Copy template
   cp .env.gcp.example .env

   # Edit with your credentials
   vim .env
   ```

   Required variables:
   - `GEMINI_API_KEY`: Get from https://aistudio.google.com/app/apikey
   - `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`: From Cloudflare R2
   - `R2_BUCKET_NAME`, `R2_PUBLIC_URL`: Your R2 bucket configuration

## First-Time Setup

Run the deployment script in **init mode** to set up Docker on the VM:

```bash
chmod +x deploy_gcp.sh
./deploy_gcp.sh --init
```

This will:
1. Install Docker and Docker Compose on the VM
2. Create deployment directory `/home/recipeai/video-processor`
3. Set up user permissions
4. Install and enable systemd service for auto-start on VM reboot

**Important**: After init, you may need to log out and back into the VM for Docker permissions to take effect.

## Deployment

### Standard Deployment (Update Code)

```bash
./deploy_gcp.sh
```

This will:
1. Package your code into a tarball (excluding `.git`, `node_modules`, etc.)
2. Upload code and `.env` to the VM
3. Build Docker image with `--no-cache` (guarantees fresh build)
4. Stop old container
5. Start new container
6. Show logs and service status

**Build Time**: 2-3 minutes (full rebuild every time)

### What Gets Deployed

**Included**:
- `src/` - Python source code
- `requirements.txt` - Dependencies
- `Dockerfile` - Container configuration
- `docker-compose.yml` - Service orchestration
- `.env` - Environment variables (uploaded separately, not in tarball)

**Excluded**:
- `.git/` - Git history
- `node_modules/`, `__pycache__/` - Dependencies/cache
- `downloads/` - Temporary files
- `.env.local` - Local development config

## Verification

After deployment, the script will show:

```
✅ Deployment Complete!

Service URL: http://xxx.xxx.xxx.xxx:8000
Health Check: http://xxx.xxx.xxx.xxx:8000/health
```

### Test the Service

```bash
# Check health
curl http://xxx.xxx.xxx.xxx:8000/health

# Expected response:
{"status":"healthy"}
```

### Verify Android Client Fix

Check logs for the new version:

```bash
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" \
  --command "cd /home/recipeai/video-processor && docker-compose logs | grep -E '(VideoDownloader|Android client)'"
```

You should see:
```
INFO:src.downloader:VideoDownloader v2.0.0 initialized (Android client for YouTube)
INFO:src.downloader:Using Android client to bypass bot detection (no cookies required)
```

## Managing the Service

### View Logs

```bash
# Real-time logs
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" \
  --command "cd /home/recipeai/video-processor && docker-compose logs -f"

# Last 50 lines
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" \
  --command "cd /home/recipeai/video-processor && docker-compose logs --tail=50"
```

### Restart Service

```bash
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" \
  --command "cd /home/recipeai/video-processor && docker-compose restart"
```

### Stop Service

```bash
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" \
  --command "cd /home/recipeai/video-processor && docker-compose down"
```

### SSH into VM

```bash
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457"

# Once inside:
cd /home/recipeai/video-processor
docker-compose ps
docker-compose logs -f
```

## Firewall Configuration

If the service is not accessible from the internet, configure GCP firewall:

```bash
# Allow port 8000
gcloud compute firewall-rules create allow-video-processor \
  --allow tcp:8000 \
  --source-ranges 0.0.0.0/0 \
  --project gen-lang-client-0768313457
```

**Security Note**: For production, restrict `--source-ranges` to your backend server's IP.

## Update Backend Configuration

After deployment, update your backend's video processor URL:

```typescript
// Before (Zeabur)
const VIDEO_PROCESSOR_URL = "https://video-processor.zeabur.app";

// After (GCP)
const VIDEO_PROCESSOR_URL = "http://xxx.xxx.xxx.xxx:8000";
```

## Troubleshooting

### Issue: Deployment Script Fails at SSH

**Error**: `Permission denied (publickey)`

**Solution**:
```bash
# Regenerate SSH keys
gcloud compute config-ssh --project gen-lang-client-0768313457

# Test connection
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457"
```

### Issue: Docker Build Fails

**Error**: `Cannot connect to the Docker daemon`

**Solution**:
```bash
# SSH into VM
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457"

# Check Docker status
sudo systemctl status docker

# Restart Docker
sudo systemctl restart docker

# Add user to docker group (if needed)
sudo usermod -aG docker $USER
exit  # Log out and back in
```

### Issue: Old Code Still Running

**This was the original problem with Zeabur. With GCP, this is solved because:**

1. Script always uses `docker-compose build --no-cache`
2. You have SSH access to verify:
   ```bash
   gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457"
   cd /home/recipeai/video-processor
   cat src/downloader.py | grep -A2 "Version:"
   ```

### Issue: Service Not Accessible

**Check**:
```bash
# 1. Container is running
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" \
  --command "cd /home/recipeai/video-processor && docker-compose ps"

# 2. Firewall allows port 8000
gcloud compute firewall-rules list --filter="allowed[]:8000"

# 3. Service is healthy
curl http://xxx.xxx.xxx.xxx:8000/health
```

## Auto-Recovery and High Availability

The deployment includes automatic recovery mechanisms:

### 1. Container Crash Recovery
- Docker restart policy: `always`
- Containers automatically restart on crash
- No manual intervention required

### 2. VM Reboot Recovery
- Systemd service: `recipeai-video-processor.service`
- Automatically starts service on VM reboot
- Installed during `./deploy_gcp.sh --init`

### 3. Health Monitoring
- Docker healthcheck runs every 30 seconds
- Monitors `/health` endpoint
- Marks unhealthy containers (visible in `docker-compose ps`)

### Manual Service Management

```bash
# Check service status
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" \
  --command "sudo systemctl status recipeai-video-processor"

# Start service
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" \
  --command "sudo systemctl start recipeai-video-processor"

# Stop service
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" \
  --command "sudo systemctl stop recipeai-video-processor"

# Restart service
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" \
  --command "sudo systemctl restart recipeai-video-processor"
```

## Cost Estimation

**GCP n1-standard-1 (1 vCPU, 3.75 GB RAM)**:
- **On-Demand**: ~$24.27/month (730 hours)
- **Preemptible**: ~$7.30/month (cheaper but can be interrupted)

**Recommendation**: Use on-demand for production stability with auto-recovery.

## Monitoring

### Health Check (Optional)

**Note**: With `restart: always` and systemd service, automatic recovery is already configured. This cron job is optional for additional monitoring.

If you want an extra layer of health monitoring:

```bash
# Optional: Set up cron job on VM to restart on failure
gcloud compute ssh --zone "us-central1-c" "foodai" --project "gen-lang-client-0768313457" --command "
cat > /home/recipeai/healthcheck.sh << 'EOF'
#!/bin/bash
if ! curl -f http://localhost:8000/health &>/dev/null; then
  cd /home/recipeai/video-processor && docker-compose restart
fi
EOF

chmod +x /home/recipeai/healthcheck.sh
(crontab -l 2>/dev/null; echo '*/5 * * * * /home/recipeai/healthcheck.sh') | crontab -
"
```

This checks health every 5 minutes and restarts if unresponsive.

### Logs Rotation

Docker Compose is configured with log rotation:
- Max size: 10 MB per file
- Max files: 3 (30 MB total)

## Backup and Recovery

### Backup .env File

```bash
# Download .env from VM
gcloud compute scp foodai:/home/recipeai/video-processor/.env .env.backup \
  --zone "us-central1-c" --project "gen-lang-client-0768313457"
```

### Disaster Recovery

If VM is lost, redeploy to new VM:

1. Create new VM with same name or update `deploy_gcp.sh`
2. Run `./deploy_gcp.sh --init`
3. Run `./deploy_gcp.sh`

## Next Steps

1. ✅ Deploy to GCP: `./deploy_gcp.sh --init`
2. ✅ Verify health: `curl http://xxx.xxx.xxx.xxx:8000/health`
3. ✅ Check logs for Android client messages
4. ✅ Test YouTube download with a cooking video
5. ✅ Update backend configuration
6. ✅ Configure firewall if needed
7. ✅ Set up monitoring/health checks

## Support

**Issues?**
1. Check logs: `docker-compose logs -f`
2. Verify code version: `cat src/downloader.py | grep "Version:"`
3. Check Docker status: `docker-compose ps`
4. Review this guide's Troubleshooting section

**Still stuck?** SSH into the VM and investigate directly - you have full control!
