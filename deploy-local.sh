#!/bin/bash
set -e

APP_DIR="/home/neekrishrichu/apps/zeroqwait"
REGISTRY="localhost:5000"
IMAGE_NAME="frontend"
TAG="latest"

echo "🚀 Starting Local CI/CD Pipeline..."

echo "📥 Pulling latest code..."
cd $APP_DIR
# Ensure we are on the correct branch
git checkout main
git pull origin main

echo "🏗️  Building Docker image..."
cd frontend
# Build using the main Dockerfile which has the Nginx setup
# Note: Ensure the Dockerfile is clean and doesn't have local-only paths
docker build -t $REGISTRY/$IMAGE_NAME:$TAG .

echo "⬆️  Pushing to local registry..."
docker push $REGISTRY/$IMAGE_NAME:$TAG

echo "🔄 Applying Kubernetes Manifests..."
cd $APP_DIR
sudo kubectl apply -f k8s-manifests/frontend-deployment.yaml

echo "🔄 Restarting Backend Deployment..."
sudo kubectl rollout restart deployment/backend -n zeroqwait

echo "🔄 Restarting Frontend Deployment..."
sudo kubectl rollout restart deployment/frontend -n zeroqwait

echo "✅ Deployed Successfully!"
