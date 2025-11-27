#!/bin/bash

# Nowait Fly.io Deployment Script
# This script helps you deploy the backend and frontend to Fly.io

set -e  # Exit on error

echo "🚀 Nowait Fly.io Deployment Script"
echo "===================================="
echo ""

# Check if flyctl is installed
if ! command -v flyctl &> /dev/null; then
    echo "❌ flyctl is not installed. Please install it first:"
    echo "   brew install flyctl"
    exit 1
fi

# Check if user is logged in
if ! flyctl auth whoami &> /dev/null; then
    echo "❌ You're not logged in to Fly.io"
    echo "   Please run: flyctl auth login"
    exit 1
fi

echo "✅ flyctl is installed and you're logged in"
echo ""

# Ask what to deploy
echo "What would you like to deploy?"
echo "1) Backend only"
echo "2) Frontend only"
echo "3) Both (recommended for first deployment)"
read -p "Enter your choice (1-3): " choice

case $choice in
    1)
        deploy_backend=true
        deploy_frontend=false
        ;;
    2)
        deploy_backend=false
        deploy_frontend=true
        ;;
    3)
        deploy_backend=true
        deploy_frontend=true
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

# Deploy Backend
if [ "$deploy_backend" = true ]; then
    echo ""
    echo "📦 Deploying Backend..."
    echo "======================"
    cd backend
    
    # Check if app exists
    if flyctl status &> /dev/null; then
        echo "Backend app already exists. Deploying..."
        flyctl deploy
    else
        echo "Backend app doesn't exist. Please run the initial setup:"
        echo "  cd backend"
        echo "  flyctl launch --no-deploy"
        echo "  # Follow the prompts, then set secrets as described in FLY_DEPLOYMENT.md"
        echo "  flyctl deploy"
        cd ..
        exit 1
    fi
    
    echo "✅ Backend deployed successfully!"
    cd ..
fi

# Deploy Frontend
if [ "$deploy_frontend" = true ]; then
    echo ""
    echo "🎨 Deploying Frontend..."
    echo "======================="
    
    # Ask for backend URL if deploying frontend
    read -p "Enter your backend URL (e.g., https://nowait-backend.fly.dev): " backend_url
    
    if [ -z "$backend_url" ]; then
        echo "❌ Backend URL is required"
        exit 1
    fi
    
    cd frontend
    
    # Check if app exists
    if flyctl status &> /dev/null; then
        echo "Frontend app already exists. Deploying with API URL: $backend_url/api"
        flyctl deploy --build-arg REACT_APP_API_URL="$backend_url/api"
    else
        echo "Frontend app doesn't exist. Please run the initial setup:"
        echo "  cd frontend"
        echo "  flyctl launch --no-deploy"
        echo "  # Follow the prompts"
        echo "  flyctl deploy --build-arg REACT_APP_API_URL=$backend_url/api"
        cd ..
        exit 1
    fi
    
    echo "✅ Frontend deployed successfully!"
    cd ..
fi

echo ""
echo "🎉 Deployment Complete!"
echo "======================="
echo ""
echo "Next steps:"
echo "1. Test your backend: curl https://your-backend.fly.dev/"
echo "2. Visit your frontend: https://your-frontend.fly.dev"
echo "3. Check logs if needed:"
echo "   - Backend: cd backend && flyctl logs"
echo "   - Frontend: cd frontend && flyctl logs"
echo ""
echo "For more details, see FLY_DEPLOYMENT.md"
