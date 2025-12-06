#!/bin/bash

# ZeroQwait GitHub Deployment Script
# This script deploys from GitHub to your Raspberry Pi

set -e

echo "🚀 ZeroQwait GitHub Deployment"
echo "=============================="
echo ""

# Configuration
PI_USER=${PI_USER:-pi}
PI_HOST=${PI_HOST:-192.168.29.220}
PI_DIR="/home/pi/Documents/projects/apps/zeroqwait"
GITHUB_REPO=${GITHUB_REPO:-"origin"}
BRANCH=${BRANCH:-"main"}

echo "📋 Configuration:"
echo "  Pi User: $PI_USER"
echo "  Pi Host: $PI_HOST"
echo "  Pi Directory: $PI_DIR"
echo "  GitHub Repo: $GITHUB_REPO"
echo "  Branch: $BRANCH"
echo ""

# Step 1: Push to GitHub (if on local machine)
if [ -d ".git" ]; then
    echo "📤 Pushing latest changes to GitHub..."
    git add .
    git status
    read -p "Commit message (or press Enter to skip commit): " COMMIT_MSG
    
    if [ ! -z "$COMMIT_MSG" ]; then
        git commit -m "$COMMIT_MSG" || echo "No changes to commit"
    fi
    
    git push $GITHUB_REPO $BRANCH
    echo "✅ Pushed to GitHub"
    echo ""
fi

# Step 2: Deploy to Pi
echo "🔄 Deploying to Raspberry Pi..."
ssh $PI_USER@$PI_HOST << 'ENDSSH'
    set -e
    
    cd /home/pi/Documents/projects/apps/zeroqwait
    
    echo "📥 Pulling latest changes from GitHub..."
    git pull origin main
    
    echo "🐳 Stopping containers..."
    docker compose -f docker-compose.prod.simple.yml down
    
    echo "🔨 Building Docker images..."
    docker compose -f docker-compose.prod.simple.yml build --no-cache
    
    echo "🚀 Starting containers..."
    docker compose -f docker-compose.prod.simple.yml up -d
    
    echo "⏳ Waiting for containers to be healthy..."
    sleep 10
    
    echo "📊 Container Status:"
    docker compose -f docker-compose.prod.simple.yml ps
    
    echo ""
    echo "✅ Deployment Complete!"
ENDSSH

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Deployment Successful!"
    echo "======================="
    echo ""
    echo "Your application is now live at:"
    echo "  🌐 Website: https://zeroqwait.com"
    echo "  🔌 API: https://zeroqwait.com/api"
    echo "  📚 Docs: https://zeroqwait.com/docs"
    echo ""
    echo "Useful commands to run on Pi:"
    echo "  ssh $PI_USER@$PI_HOST"
    echo "  cd $PI_DIR"
    echo "  docker compose -f docker-compose.prod.simple.yml logs -f"
    echo ""
else
    echo ""
    echo "❌ Deployment failed!"
    echo "Check the error messages above."
    exit 1
fi
