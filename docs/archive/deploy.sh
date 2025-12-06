#!/bin/bash

# Nowait Fly.io Deployment Script (Combined Deployment)
# This script helps you deploy the combined backend+frontend app to Fly.io

set -e  # Exit on error

echo "🚀 Nowait Fly.io Deployment Script (Combined)"
echo "============================================="
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

# Check if app exists
if ! flyctl status --app nowait &> /dev/null; then
    echo "❌ App 'nowait' doesn't exist yet."
    echo "   Please run the initial setup first:"
    echo "   See DEPLOYMENT_COMBINED_SUCCESS.md for instructions"
    exit 1
fi

echo "📦 Deploying Combined App (Backend + Frontend)..."
echo "================================================="
echo ""

# Deploy from project root
flyctl deploy --app nowait

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Deployment Complete!"
    echo "======================"
    echo ""
    echo "✅ App: https://nowait.fly.dev"
    echo "✅ API: https://nowait.fly.dev/api"
    echo "✅ Docs: https://nowait.fly.dev/docs"
    echo ""
    echo "Useful commands:"
    echo "  - View logs: flyctl logs --app nowait"
    echo "  - Check status: flyctl status --app nowait"
    echo "  - Open app: flyctl apps open nowait"
    echo ""
else
    echo ""
    echo "❌ Deployment failed!"
    echo "Check the logs: flyctl logs --app nowait"
    exit 1
fi
