#!/bin/bash
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY="localhost:5000"
IMAGE_NAME="frontend"
TAG="latest"

echo "🚀 Starting Local CI/CD Pipeline..."

echo "📥 Pulling latest code..."
cd "$APP_DIR"
# Ensure we are on the correct branch
git checkout main
git pull origin main

echo "🏗️  Building Frontend Docker image..."
cd "$APP_DIR/frontend"
docker build --no-cache -t $REGISTRY/frontend:$TAG .
docker push $REGISTRY/frontend:$TAG

echo "🏗️  Building Backend Docker image..."
cd "$APP_DIR/backend"
docker build --no-cache -t $REGISTRY/backend:$TAG .
docker push $REGISTRY/backend:$TAG

echo "🔄 Applying Kubernetes Manifests..."
cd "$APP_DIR"
sudo kubectl apply -f k8s-manifests/frontend-deployment.yaml
sudo kubectl apply -f k8s-manifests/backend-deployment.yaml

echo "🔄 Restarting Deployments..."
sudo kubectl rollout restart deployment/backend -n zeroqwait
sudo kubectl rollout restart deployment/frontend -n zeroqwait

echo "✅ Deployed Successfully!"
