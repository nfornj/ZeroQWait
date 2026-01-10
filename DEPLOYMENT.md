# Deployment Guide

## Overview

This project uses an optimized deployment process where Docker images are built on your Mac development machine and pushed to the Raspberry Pi for execution. This approach is much faster than building directly on the Pi.

## Prerequisites

- Docker Desktop on Mac with buildx support
- SSH access to Raspberry Pi (pi@192.168.2.85)
- Docker installed on Raspberry Pi

## Quick Deployment

To deploy the latest code to the Raspberry Pi:

```bash
./build-and-push.sh
```

This script will:
1. Build Docker images on your Mac for ARM64 architecture
2. Save images as tar files
3. Copy tar files to the Pi via SCP
4. Load images on the Pi
5. Restart containers with the new images

## Manual Deployment Steps

If you need to deploy manually:

### 1. Build Images on Mac

```bash
# Backend
docker buildx build --platform linux/arm64 \
  -t fastcuts-backend:latest \
  -f backend/Dockerfile \
  --load backend/

# Frontend
docker buildx build --platform linux/arm64 \
  -t fastcuts-frontend:latest \
  -f frontend/Dockerfile \
  --load frontend/
```

### 2. Save Images

```bash
docker save fastcuts-backend:latest -o /tmp/backend.tar
docker save fastcuts-frontend:latest -o /tmp/frontend.tar
```

### 3. Copy to Pi

```bash
scp /tmp/backend.tar pi@192.168.2.85:~/FastCuts/
scp /tmp/frontend.tar pi@192.168.2.85:~/FastCuts/
```

### 4. Load and Run on Pi

```bash
ssh pi@192.168.2.85
cd FastCuts
docker load -i backend.tar
docker load -i frontend.tar
rm backend.tar frontend.tar
docker compose down
docker compose up -d
```

## Troubleshooting

### Out of Disk Space on Pi

Clean up old Docker resources:

```bash
ssh pi@192.168.2.85 "docker system prune -a -f"
```

### Check Container Status

```bash
ssh pi@192.168.2.85 "docker ps"
```

### View Logs

```bash
# Backend logs
ssh pi@192.168.2.85 "docker logs fastcuts-backend-1"

# Frontend logs
ssh pi@192.168.2.85 "docker logs fastcuts-frontend-1"
```

## Architecture Notes

- **Mac (Development)**: Intel/ARM64 - Builds images for ARM64 target
- **Raspberry Pi (Production)**: ARM64 - Runs the pre-built images
- **Cross-compilation**: Docker buildx handles building ARM64 images on Mac

## Performance

Building on Mac (vs Pi):
- Backend: ~30-60 seconds (vs 5-10 minutes on Pi)
- Frontend: ~2-3 minutes (vs 10-20 minutes on Pi)
- Total deployment: ~5 minutes (vs 30+ minutes on Pi)
