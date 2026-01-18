#!/bin/bash

# ZeroQwait Local Deployment Script with Subdomain Support
# Deploys to local Docker for testing shop subdomains with nip.io

set -e

echo "🚀 Starting ZeroQwait Local Deployment with Subdomain Support"
echo "=============================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Error: docker-compose.yml not found!${NC}"
    echo "Please run this script from the ZeroQwait root directory"
    exit 1
fi

echo -e "${BLUE}📋 Prerequisites Check:${NC}"
echo "✓ Docker: $(docker --version)"
echo "✓ Docker Compose: $(docker-compose --version)"
echo ""

echo -e "${BLUE}🧹 Step 1: Cleaning up old containers...${NC}"
docker-compose down --remove-orphans 2>/dev/null || true
sleep 2

echo -e "${BLUE}🏗️  Step 2: Building containers...${NC}"
docker-compose build --no-cache

echo -e "${BLUE}🚀 Step 3: Starting containers...${NC}"
docker-compose up -d

echo -e "${BLUE}⏳ Step 4: Waiting for services to start...${NC}"
sleep 10

echo ""
echo -e "${BLUE}📊 Container Status:${NC}"
docker-compose ps

echo ""
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo "=============================================================="
echo ""
echo -e "${YELLOW}🌐 Access Your Application:${NC}"
echo ""
echo "  Base URL (for login):"
echo "    http://192.168.2.88.nip.io/"
echo ""
echo "  After login, you'll be redirected to your shop:"
echo "    http://shopname.192.168.2.88.nip.io/dashboard"
echo ""
echo "  Examples (replace 'shopname' with actual shop slug):"
echo "    http://pizza-palace.192.168.2.88.nip.io/"
echo "    http://coffee-shop.192.168.2.88.nip.io/"
echo ""
echo -e "${YELLOW}📱 Frontend:${NC}"
echo "    http://192.168.2.88.nip.io:3000"
echo ""
echo -e "${YELLOW}🔧 Backend API:${NC}"
echo "    http://192.168.2.88.nip.io:8000"
echo "    http://192.168.2.88.nip.io:8000/docs (Swagger UI)"
echo ""
echo -e "${YELLOW}🐛 Debugging:${NC}"
echo "  View logs:"
echo "    docker-compose logs -f"
echo ""
echo "  View backend logs only:"
echo "    docker-compose logs -f backend"
echo ""
echo "  View frontend logs only:"
echo "    docker-compose logs -f frontend"
echo ""
echo "  Stop containers:"
echo "    docker-compose down"
echo ""
echo -e "${YELLOW}✨ Features:${NC}"
echo "  ✓ Multi-shop support with subdomains"
echo "  ✓ Automatic redirect to shop subdomain after login"
echo "  ✓ Shop-specific data isolation"
echo "  ✓ API endpoints work across subdomains"
echo ""
echo -e "${BLUE}💡 Next Steps:${NC}"
echo "  1. Create a shop (shop name becomes the subdomain)"
echo "  2. Login with your shop owner account"
echo "  3. You'll be redirected to: shopname.192.168.2.88.nip.io"
echo ""
