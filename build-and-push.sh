#!/bin/bash
# Build and push Docker images from Mac to Raspberry Pi
# This script builds images on Mac and saves them as tar files, then copies to Pi

set -e

PI_HOST="pi@192.168.2.85"
PI_DIR="/home/pi/FastCuts"
IMAGE_DIR="/tmp/fastcuts-images"

echo "🏗️  Building Docker images on Mac..."

# Create temp directory for images
mkdir -p $IMAGE_DIR

# Build backend image for linux/arm64 (Raspberry Pi architecture)
echo "Building backend image..."
docker buildx build --platform linux/arm64 \
  -t fastcuts-backend:latest \
  -f backend/Dockerfile \
  --load \
  backend/

# Build frontend image for linux/arm64
echo "Building frontend image..."
docker buildx build --platform linux/arm64 \
  -t fastcuts-frontend:latest \
  -f frontend/Dockerfile \
  --load \
  frontend/

# Save images to tar files
echo "💾 Saving images to tar files..."
docker save fastcuts-backend:latest -o $IMAGE_DIR/backend.tar
docker save fastcuts-frontend:latest -o $IMAGE_DIR/frontend.tar

# Copy tar files to Pi
echo "📦 Copying images to Raspberry Pi..."
scp $IMAGE_DIR/backend.tar $PI_HOST:$PI_DIR/backend.tar
scp $IMAGE_DIR/frontend.tar $PI_HOST:$PI_DIR/frontend.tar

# Load images on Pi and restart containers
echo "🚀 Loading images and restarting containers on Pi..."
ssh $PI_HOST << 'EOF'
cd /home/pi/FastCuts
echo "Loading backend image..."
docker load -i backend.tar
echo "Loading frontend image..."
docker load -i frontend.tar
echo "Removing tar files..."
rm backend.tar frontend.tar
echo "Restarting containers..."
docker compose down
docker compose up -d
echo "✅ Deployment complete!"
docker ps
EOF

# Cleanup local tar files
echo "🧹 Cleaning up local files..."
rm -rf $IMAGE_DIR

echo ""
echo "✨ Deployment successful!"
echo "Backend: http://192.168.2.85:8000"
echo "Frontend: http://192.168.2.85:3000"
