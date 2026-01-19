#!/bin/bash

# ZeroQwait Git Sync - Syncs code from current branch to remote server
# Usage: bash sync-code.sh [destination_server] [destination_path]

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

echo -e "${BLUE}🔄 ZeroQwait Git Sync${NC}"
echo "=========================================================="
echo ""

# Get current branch
CURRENT_BRANCH=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD)
echo -e "${YELLOW}Current branch: ${GREEN}$CURRENT_BRANCH${NC}"
echo ""

# Check for uncommitted changes
UNCOMMITTED=$(git -C "$PROJECT_ROOT" status --porcelain | wc -l)
if [ $UNCOMMITTED -gt 0 ]; then
    echo -e "${YELLOW}⚠️  You have $UNCOMMITTED uncommitted changes:${NC}"
    git -C "$PROJECT_ROOT" status --short
    echo ""
    read -p "Commit changes before pushing? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter commit message: " COMMIT_MSG
        git -C "$PROJECT_ROOT" add -A
        git -C "$PROJECT_ROOT" commit -m "$COMMIT_MSG"
    else
        echo -e "${RED}❌ Aborting - please commit or stash changes first${NC}"
        exit 1
    fi
fi

echo -e "${BLUE}📤 Pushing to remote...${NC}"
git -C "$PROJECT_ROOT" push origin "$CURRENT_BRANCH"
echo -e "${GREEN}✓ Code pushed${NC}"
echo ""

echo -e "${BLUE}📥 Pulling on remote server...${NC}"
ssh "$DESTINATION_SERVER" "
    cd $DESTINATION_PATH && \
    echo '⏳ Fetching latest changes...' && \
    git fetch origin && \
    echo '⏳ Pulling branch: $CURRENT_BRANCH' && \
    git checkout $CURRENT_BRANCH && \
    git pull origin $CURRENT_BRANCH && \
    echo -e '\033[0;32m✓ Code synced to $CURRENT_BRANCH\033[0m'
"

echo ""
echo -e "${GREEN}✅ Sync Complete!${NC}"
echo "=========================================================="
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  Deploy to Kubernetes:"
echo "    ssh $DESTINATION_SERVER \"cd $DESTINATION_PATH/deployment && bash scripts/deploy-k8s.sh\""
echo ""
echo "  Or in one command:"
echo "    bash deploy-and-sync.sh"
echo ""
