#!/bin/bash

# Production-like Docker Compose Deployment
# Uses docker-compose.prod.yml for more realistic setup

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🚀 Starting ZeroQwait Production Docker Compose Deployment"
echo "==========================================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "$PROJECT_ROOT"

# Limit compose parallelism on heavy hosts to reduce peak memory usage.
export COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}"
echo -e "${BLUE}🧠 Compose parallel limit: ${COMPOSE_PARALLEL_LIMIT}${NC}"

echo -e "${BLUE}🧹 Cleaning up old containers...${NC}"
docker-compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
sleep 2

echo -e "${BLUE}🏗️  Building production containers...${NC}"
docker-compose -f docker-compose.prod.yml build --no-cache

echo -e "${BLUE}🚀 Starting production environment...${NC}"
docker-compose -f docker-compose.prod.yml up -d

echo -e "${BLUE}⏳ Waiting for services...${NC}"
sleep 15

# Health checks
echo ""
echo -e "${BLUE}🏥 Running health checks...${NC}"

if docker-compose -f docker-compose.prod.yml exec -T backend curl -f http://localhost:8000/ >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Backend not responding yet${NC}"
fi

if docker-compose -f docker-compose.prod.yml exec -T frontend curl -f http://localhost:80/ >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend not responding yet${NC}"
fi

echo ""
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo "==========================================================="
echo ""
echo -e "${YELLOW}🌐 Access Your Application:${NC}"
echo ""
echo "  Frontend: http://192.168.2.88.nip.io"
echo "  Backend:  http://192.168.2.88.nip.io/api"
echo ""
echo -e "${YELLOW}🐛 Debugging:${NC}"
echo "  View logs:"
echo "    docker-compose -f docker-compose.prod.yml logs -f"
echo ""
echo "  Stop:"
echo "    docker-compose -f docker-compose.prod.yml down"
echo ""
