#!/bin/bash

# ZeroQwait Production Update Script
# Usage: Run this ON THE SERVER to pull latest code and restart app.

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🚀 Starting ZeroQwait Production Update${NC}"
echo "================================================="

# 1. Ensure we are in the correct directory
TARGET_DIR="$HOME/apps/zeroqwait"

if [ -d "$TARGET_DIR" ]; then
    echo -e "${BLUE}📂 Switching to $TARGET_DIR...${NC}"
    cd "$TARGET_DIR"
else
    echo -e "${RED}❌ Error: Directory $TARGET_DIR not found!${NC}"
    echo "This script expects the app to be in ~/apps/zeroqwait"
    exit 1
fi

# 2. Pull latest code
echo -e "${BLUE}⬇️  Pulling latest code from git...${NC}"
git pull origin main

# 3. Verify Permisssions & Run Deploy
echo -e "${BLUE}🔄 restarting services...${NC}"

# Check for sudo access for k3s
if sudo -n true 2>/dev/null; then
    # Sudo is passwordless (ideal)
    sudo bash ./deployment/scripts/deploy-k8s.sh
else
    # Prompt for password
    echo -e "${YELLOW}🔑 Sudo access required for Kubernetes operations.${NC}"
    sudo bash ./deployment/scripts/deploy-k8s.sh
fi

echo ""
echo -e "${GREEN}✅ Update Complete! Check the Agent in ~2 minutes.${NC}"
echo "================================================="
