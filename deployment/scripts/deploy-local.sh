#!/bin/bash

# ZeroQwait Local Docker Deployment
# Deploys backend and frontend to local Docker with subdomain support

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🚀 Starting ZeroQwait Local Docker Deployment"
echo "=============================================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd "$PROJECT_ROOT"

# Limit compose parallelism on heavy hosts to reduce peak memory usage.
export COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}"
echo "✓ Compose parallel limit: ${COMPOSE_PARALLEL_LIMIT}"

# Check prerequisites
echo -e "${BLUE}📋 Prerequisites Check:${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found!${NC}"
    exit 1
fi
echo "✓ Docker: $(docker --version)"

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found!${NC}"
    exit 1
fi
echo "✓ Docker Compose: $(docker-compose --version)"
echo ""

# Cleanup old containers
echo -e "${BLUE}🧹 Cleaning up old containers...${NC}"
docker-compose down --remove-orphans 2>/dev/null || true
sleep 2

# Build
echo -e "${BLUE}🏗️  Building containers...${NC}"
docker-compose build --no-cache

# Start
echo -e "${BLUE}🚀 Starting containers...${NC}"
docker-compose up -d

# Wait
echo -e "${BLUE}⏳ Waiting for services to start...${NC}"
sleep 10

# Status
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
echo "    http://192.168.2.88.nip.io:3000"
echo ""
echo "  Backend API:"
echo "    http://192.168.2.88.nip.io:8000"
echo "    http://192.168.2.88.nip.io:8000/docs (Swagger UI)"
echo ""
echo "  After login, you'll be redirected to:"
echo "    http://shopname.192.168.2.88.nip.io"
echo ""
echo -e "${YELLOW}🐛 Debugging:${NC}"
echo "  View logs:"
echo "    docker-compose logs -f"
echo ""
echo "  View backend logs:"
echo "    docker-compose logs -f backend"
echo ""
echo "  Stop containers:"
echo "    docker-compose down"
echo ""
echo -e "${YELLOW}✨ Next Steps:${NC}"
echo "  1. Register as shop owner"
echo "  2. Create a shop (slug auto-generated)"
echo "  3. Login and verify subdomain redirect"
echo ""
