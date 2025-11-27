#!/bin/bash

# Initial Fly.io Setup Script
# Run this script once to set up your apps on Fly.io

set -e

echo "🛠️  Nowait Fly.io Initial Setup"
echo "================================"
echo ""

# Check prerequisites
if ! command -v flyctl &> /dev/null; then
    echo "❌ flyctl is not installed. Installing..."
    brew install flyctl
fi

echo "✅ flyctl is installed"
echo ""

# Login to Fly.io
echo "📝 Logging in to Fly.io..."
if ! flyctl auth whoami &> /dev/null; then
    flyctl auth login
else
    echo "✅ Already logged in as: $(flyctl auth whoami)"
fi

echo ""
echo "Setting up Backend..."
echo "===================="
cd backend

# Launch backend
echo "Running: flyctl launch --no-deploy"
echo ""
echo "⚠️  IMPORTANT: When prompted:"
echo "  - App name: Choose a unique name (e.g., nowait-backend-yourname)"
echo "  - Region: Choose one closest to you or your users"
echo "  - PostgreSQL: NO (you're using Supabase)"
echo "  - Redis: NO"
echo ""
read -p "Press Enter to continue with backend setup..."

flyctl launch --no-deploy

echo ""
echo "✅ Backend app created!"
echo ""

# Set secrets
echo "Now we'll set up environment variables (secrets)..."
echo ""

read -p "Enter your SECRET_KEY (press Enter to use existing): " secret_key
if [ -z "$secret_key" ]; then
    secret_key="09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
fi

read -p "Enter your SUPABASE_URL: " supabase_url
read -p "Enter your SUPABASE_KEY (service role): " supabase_key
read -p "Enter your SUPABASE_ANON_KEY: " supabase_anon_key
read -p "Enter your EMAIL_USER: " email_user
read -p "Enter your EMAIL_PASSWORD (app password): " email_password
read -p "Enter your EMAIL_FROM: " email_from

echo ""
echo "Setting secrets..."
flyctl secrets set \
    SECRET_KEY="$secret_key" \
    SUPABASE_URL="$supabase_url" \
    SUPABASE_KEY="$supabase_key" \
    SUPABASE_ANON_KEY="$supabase_anon_key" \
    EMAIL_HOST="smtp.gmail.com" \
    EMAIL_PORT="587" \
    EMAIL_USER="$email_user" \
    EMAIL_PASSWORD="$email_password" \
    EMAIL_FROM="$email_from" \
    FRONTEND_URL="https://nowait-frontend.fly.dev"

echo ""
echo "✅ Backend secrets set!"
echo ""
echo "Deploying backend..."
flyctl deploy

backend_url=$(flyctl status --json | grep -o '"Hostname":"[^"]*' | cut -d'"' -f4)
echo ""
echo "✅ Backend deployed at: https://$backend_url"
echo ""

cd ..

# Setup Frontend
echo ""
echo "Setting up Frontend..."
echo "====================="
cd frontend

echo "Running: flyctl launch --no-deploy"
echo ""
echo "⚠️  IMPORTANT: When prompted:"
echo "  - App name: Choose a unique name (e.g., nowait-frontend-yourname)"
echo "  - Region: Choose the SAME region as your backend"
echo "  - PostgreSQL: NO"
echo "  - Redis: NO"
echo ""
read -p "Press Enter to continue with frontend setup..."

flyctl launch --no-deploy

echo ""
echo "✅ Frontend app created!"
echo ""

# Deploy frontend
echo "Deploying frontend with backend URL: https://$backend_url/api"
flyctl deploy --build-arg REACT_APP_API_URL="https://$backend_url/api"

frontend_url=$(flyctl status --json | grep -o '"Hostname":"[^"]*' | cut -d'"' -f4)
echo ""
echo "✅ Frontend deployed at: https://$frontend_url"
echo ""

cd ..

# Summary
echo ""
echo "🎉 Setup Complete!"
echo "=================="
echo ""
echo "Your apps are now deployed:"
echo "  Backend:  https://$backend_url"
echo "  Frontend: https://$frontend_url"
echo ""
echo "Next steps:"
echo "1. Visit https://$frontend_url to test your app"
echo "2. Update FRONTEND_URL in backend secrets if needed:"
echo "   cd backend && flyctl secrets set FRONTEND_URL=https://$frontend_url"
echo "3. For future deployments, use: ./deploy.sh"
echo ""
echo "For more information, see FLY_DEPLOYMENT.md"
