#!/bin/bash

# ZeroQwait Deploy & Sync - One command to sync code and deploy
# Syncs from current branch, then deploys to K8s on remote server
# Auto-generates commit messages using local LLM (llama3)

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

# Function to generate commit message using llama3
generate_commit_message() {
    local git_diff="$1"
    
    if command -v ollama &> /dev/null; then
        echo -e "${BLUE}🤖 Generating commit message with llama3...${NC}" >&2
        
        # Create prompt and get response
        local prompt="Based on these changes, write ONE SHORT git commit message (max 60 chars). Be concise. Output ONLY the message.\n\n$git_diff"
        local message=$(echo -e "$prompt" | ollama run llama3 2>/dev/null | grep -v "^>" | head -1 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//;s/^[0-9]\+:[[:space:]]*//g' | head -c 60)
        
        if [ ! -z "$message" ] && [ ${#message} -gt 5 ]; then
            echo "$message"
            return 0
        fi
    fi
    
    # Fallback: generate basic message
    echo "chore: sync code and deploy"
}

# Step 1: Commit and push
echo -e "${BLUE}Step 1️⃣  - Pushing code to Git...${NC}"
UNCOMMITTED=$(git -C "$PROJECT_ROOT" status --porcelain | wc -l)

if [ $UNCOMMITTED -gt 0 ]; then
    echo -e "${YELLOW}You have $UNCOMMITTED uncommitted changes${NC}"
    echo ""
    
    # Get git diff for LLM
    GIT_DIFF=$(git -C "$PROJECT_ROOT" diff --stat 2>/dev/null | head -5)
    
    # Auto-generate commit message with llama3
    COMMIT_MSG=$(generate_commit_message "$GIT_DIFF")
    echo -e "${GREEN}✓ Generated: \"$COMMIT_MSG\"${NC}"
    echo ""
    
    read -p "Use this message? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git -C "$PROJECT_ROOT" add -A
        git -C "$PROJECT_ROOT" commit -m "$COMMIT_MSG"
    else
        read -p "Enter custom commit message: " CUSTOM_MSG
        git -C "$PROJECT_ROOT" add -A
        git -C "$PROJECT_ROOT" commit -m "$CUSTOM_MSG"
    fi
fi

git -C "$PROJECT_ROOT" push origin "$CURRENT_BRANCH"
echo -e "${GREEN}✓ Code pushed${NC}"
echo ""

# Step 2: Sync on remote
echo -e "${BLUE}Step 2️⃣  - Syncing on remote server...${NC}"

# Create path if doesn't exist, then sync
ssh "$DESTINATION_SERVER" "
    # Create directory if needed
    mkdir -p $DESTINATION_PATH
    cd $DESTINATION_PATH
    
    # Initialize git if not already
    if [ ! -d .git ]; then
        echo '⏳ Initializing git repository...'
        git init
        git remote add origin git@github.com:nfornj/FastCuts.git || true
    fi
    
    # Sync code
    git fetch origin && \
    git checkout $CURRENT_BRANCH 2>/dev/null || git checkout -b $CURRENT_BRANCH origin/$CURRENT_BRANCH && \
    git pull origin $CURRENT_BRANCH
" || {
    echo -e "${RED}❌ Failed to sync on remote server${NC}"
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo "  1. Check SSH connection: ssh $DESTINATION_SERVER 'echo ok'"
    echo "  2. Setup SSH key on remote: ssh-copy-id -i ~/.ssh/id_rsa.pub $DESTINATION_SERVER"
    echo "  3. Check Git SSH access: ssh $DESTINATION_SERVER 'ssh -T git@github.com'"
    echo "  4. Or use git clone: ssh $DESTINATION_SERVER 'rm -rf $DESTINATION_PATH && git clone git@github.com:nfornj/FastCuts.git $DESTINATION_PATH && cd $DESTINATION_PATH && git checkout $CURRENT_BRANCH'"
    exit 1
}

echo -e "${GREEN}✓ Code synced${NC}"
echo ""

# Step 3: Deploy
echo -e "${BLUE}Step 3️⃣  - Deploying to Kubernetes...${NC}"

# Copy script to /tmp and run as sudo to avoid kubeconfig permission issues
ssh "$DESTINATION_SERVER" bash <<'DEPLOY_SCRIPT'
set -e
DEST_PATH="/home/neekrishrichu/zeroqwait"
cd "$DEST_PATH/deployment"
sudo bash scripts/deploy-k8s.sh
DEPLOY_SCRIPT

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Deployment failed${NC}"
    exit 1
fi

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
