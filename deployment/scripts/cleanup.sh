#!/bin/bash

# Cleanup script - Stop and remove containers

set -e

# Colors
YELLOW='\033[1;33m'
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${YELLOW}⚠️  This will stop and remove all containers${NC}"
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo -e "${RED}🗑️  Cleaning up Docker containers...${NC}"
docker-compose down --remove-orphans 2>/dev/null || true

echo -e "${RED}🗑️  Cleaning up Docker images...${NC}"
docker system prune -f

echo ""
echo -e "${GREEN}✅ Cleanup complete!${NC}"
echo ""
echo "To restart:"
echo "  bash scripts/deploy-local.sh"
echo ""
