#!/bin/bash

# ZeroQwait Raspberry Pi Deployment Script
# This script helps deploy the application to your Raspberry Pi

set -e  # Exit on error

echo "🚀 ZeroQwait Raspberry Pi Deployment Script"
echo "==========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PI_USER=${PI_USER:-pi}
PI_HOST=${PI_HOST:-raspberrypi.local}
PI_DIR=${PI_DIR:-~/zeroqwait}

echo "Configuration:"
echo "  User: $PI_USER"
echo "  Host: $PI_HOST"
echo "  Directory: $PI_DIR"
echo ""

# Check if we're on local machine or Pi
if [ -f /etc/rpi-issue ]; then
    echo "✅ Running on Raspberry Pi"
    ON_PI=true
else
    echo "📦 Running on local machine - will deploy to Pi"
    ON_PI=false
fi
echo ""

# Function to run command on Pi or locally
run_cmd() {
    if [ "$ON_PI" = true ]; then
        eval "$1"
    else
        ssh "$PI_USER@$PI_HOST" "$1"
    fi
}

# If on local machine, transfer files first
if [ "$ON_PI" = false ]; then
    echo "📤 Transferring files to Raspberry Pi..."
    rsync -avz --progress \
        --exclude 'node_modules' \
        --exclude '__pycache__' \
        --exclude '.git' \
        --exclude '*.pyc' \
        --exclude '.env' \
        --exclude 'venv' \
        --exclude '.venv' \
        ./ "$PI_USER@$PI_HOST:$PI_DIR/"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Files transferred successfully${NC}"
    else
        echo -e "${RED}❌ File transfer failed${NC}"
        exit 1
    fi
    echo ""
fi

# Deploy on Pi
echo "🔧 Building and starting Docker containers..."
run_cmd "cd $PI_DIR && docker-compose -f docker-compose.prod.yml down"
run_cmd "cd $PI_DIR && docker-compose -f docker-compose.prod.yml build --no-cache"
run_cmd "cd $PI_DIR && docker-compose -f docker-compose.prod.yml up -d"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Docker containers started successfully${NC}"
else
    echo -e "${RED}❌ Failed to start containers${NC}"
    exit 1
fi
echo ""

# Check container status
echo "📊 Container Status:"
run_cmd "cd $PI_DIR && docker-compose -f docker-compose.prod.yml ps"
echo ""

# Health check
echo "🏥 Running health checks..."
sleep 10

# Check backend
echo "Checking backend..."
if run_cmd "curl -f http://localhost:8000/ >/dev/null 2>&1"; then
    echo -e "${GREEN}✅ Backend is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Backend health check failed - may still be starting${NC}"
fi

# Check frontend
echo "Checking frontend..."
if run_cmd "curl -f http://localhost:3000/ >/dev/null 2>&1"; then
    echo -e "${GREEN}✅ Frontend is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend health check failed - may still be starting${NC}"
fi
echo ""

# Show logs
echo "📋 Recent logs (last 20 lines):"
run_cmd "cd $PI_DIR && docker-compose -f docker-compose.prod.yml logs --tail=20"
echo ""

echo "🎉 Deployment Complete!"
echo "======================"
echo ""
echo "Access your application:"
echo "  • Website: https://zeroqwait.com"
echo "  • API: https://zeroqwait.com/api"
echo "  • Docs: https://zeroqwait.com/docs"
echo ""
echo "Useful commands on the Pi:"
echo "  • View logs: docker-compose -f docker-compose.prod.yml logs -f"
echo "  • Restart: docker-compose -f docker-compose.prod.yml restart"
echo "  • Stop: docker-compose -f docker-compose.prod.yml down"
echo "  • Check Nginx: sudo systemctl status nginx"
echo ""
