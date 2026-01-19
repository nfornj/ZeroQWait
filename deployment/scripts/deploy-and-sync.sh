#!/bin/bash

# ZeroQwait Deploy & Sync - One command to sync code and deploy
# Syncs from current branch, then deploys to K8s on remote server

set -e

# Configuration
DESTINATION_SERVER="${1:-neekrishrichu@192.168.2.88}"
DESTINATION_PATH="${2:-/home/neekrishrichu/zeroqwait}"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}🚀 ZeroQwait Deploy & Sync${NC}"
echo "=========================================================="
echo ""

# Get current branch
CURRENT_BRANCH=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD)
echo -e "${YELLOW}📌 Current branch: ${GREEN}$CURRENT_BRANCH${NC}"
echo -e "${YELLOW}📌 Server: ${GREEN}$DESTINATION_SERVER${NC}"
echo -e "${YELLOW}📌 Path: ${GREEN}$DESTINATION_PATH${NC}"
echo ""

# Step 1: Commit and push
echo -e "${BLUE}Step 1️⃣  - Pushing code to Git...${NC}"
UNCOMMITTED=$(git -C "$PROJECT_ROOT" status --porcelain | wc -l)
if [ $UNCOMMITTED -gt 0 ]; then
    echo -e "${YELLOW}You have $UNCOMMITTED uncommitted changes${NC}"
    read -p "Commit changes? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter commit message: " COMMIT_MSG
        git -C "$PROJECT_ROOT" add -A
        git -C "$PROJECT_ROOT" commit -m "$COMMIT_MSG"
    fi
fi
git -C "$PROJECT_ROOT" push origin "$CURRENT_BRANCH"
echo -e "${GREEN}✓ Code pushed${NC}"
echo ""

# Step 2: Sync on remote
echo -e "${BLUE}Step 2️⃣  - Syncing on remote server...${NC}"
ssh "$DESTINATION_SERVER" "
    cd $DESTINATION_PATH && \
    git fetch origin && \
    git checkout $CURRENT_BRANCH 2>/dev/null || git checkout -b $CURRENT_BRANCH origin/$CURRENT_BRANCH && \
    git pull origin $CURRENT_BRANCH
" || {
    echo -e "${RED}❌ Failed to sync on remote server${NC}"
    exit 1
}
echo -e "${GREEN}✓ Code synced${NC}"
echo ""

# Step 3: Deploy
echo -e "${BLUE}Step 3️⃣  - Deploying to Kubernetes...${NC}"
ssh "$DESTINATION_SERVER" "cd $DESTINATION_PATH/deployment && bash scripts/deploy-k8s.sh" || {
    echo -e "${RED}❌ Deployment failed${NC}"
    exit 1
}

echo ""
echo -e "${GREEN}✅ Deploy & Sync Complete!${NC}"
echo "=========================================================="
echo ""
echo -e "${YELLOW}🌐 Access Your Application:${NC}"
echo "  http://192.168.2.88.nip.io/"
echo ""
echo -e "${YELLOW}🐛 Monitor Deployment:${NC}"
echo "  ssh $DESTINATION_SERVER \"kubectl get pods -n zeroqwait -w\""
echo ""
