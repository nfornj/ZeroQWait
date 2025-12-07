#!/bin/bash

# ZeroQwait Production Deployment Script
# Deploys the AI Queue Counter with Gesture Recognition to production

set -e  # Exit on error

echo "🚀 Starting ZeroQwait Production Deployment..."
echo "================================================"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "docker-compose.prod.yml" ]; then
    echo "❌ Error: docker-compose.prod.yml not found!"
    echo "Please run this script from the FastCuts directory"
    exit 1
fi

echo -e "${BLUE}📦 Step 1: Building production containers...${NC}"
docker-compose -f docker-compose.prod.yml build --no-cache

echo -e "${BLUE}🔄 Step 2: Stopping old containers...${NC}"
docker-compose -f docker-compose.prod.yml down

echo -e "${BLUE}🚀 Step 3: Starting new containers...${NC}"
docker-compose -f docker-compose.prod.yml up -d

echo -e "${BLUE}⏳ Step 4: Waiting for services to be healthy...${NC}"
sleep 10

# Check container status
echo -e "${BLUE}📊 Container Status:${NC}"
docker-compose -f docker-compose.prod.yml ps

# Check logs for any errors
echo -e "${BLUE}📋 Recent logs:${NC}"
docker-compose -f docker-compose.prod.yml logs --tail=20

echo ""
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo "================================================"
echo ""
echo "🌐 Your app should now be accessible at:"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo ""
echo "🎮 New Feature: AI Queue Counter with Gesture Recognition"
echo "   Route: /queue-counter"
echo ""
echo "📊 To view logs:"
echo "   docker-compose -f docker-compose.prod.yml logs -f"
echo ""
echo "🛑 To stop:"
echo "   docker-compose -f docker-compose.prod.yml down"
echo ""
