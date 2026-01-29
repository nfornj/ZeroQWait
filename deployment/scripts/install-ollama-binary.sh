#!/bin/bash

# ZeroQwait: Fix Broken Ollama Installation
# Downloads a fresh binary to /usr/local/bin and updates the service.

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🔧 Fixing Ollama Service...${NC}"
echo "========================================"

# 1. Download official binary
echo -e "${BLUE}⬇️  Downloading fresh Ollama binary...${NC}"
curl -L https://ollama.com/download/ollama-linux-amd64.tgz -o ollama-linux-amd64.tgz

# 2. Install to /usr/local/bin (Standard Location)
echo -e "${BLUE}📦 Installing to /usr/local/bin (Requires Sudo)...${NC}"
sudo tar -C /usr -xzf ollama-linux-amd64.tgz

# 3. Verify Installation
if [ -f "/usr/bin/ollama" ]; then
    echo -e "${GREEN}✓ Installed successfully at /usr/bin/ollama${NC}"
    OLLAMA_PATH="/usr/bin/ollama"
else
    # Sometimes it goes to /usr/bin directly depending on the tar structure
    if [ -f "/usr/local/bin/ollama" ]; then
         echo -e "${GREEN}✓ Installed successfully at /usr/local/bin/ollama${NC}"
         OLLAMA_PATH="/usr/local/bin/ollama"
    else
         echo -e "${RED}❌ Error: Installation failed. Could not find binary after tar extraction.${NC}"
         exit 1
    fi
fi

# 4. Update Service File
echo -e "${BLUE}📝 Updating service path...${NC}"
SERVICE_FILE="/etc/systemd/system/ollama.service"

# We use sed to replace the broken ExecStart line
sudo sed -i "s|ExecStart=.*|ExecStart=$OLLAMA_PATH serve|g" $SERVICE_FILE

# 5. Restart
echo -e "${BLUE}🔄 Restarting service...${NC}"
sudo systemctl daemon-reload
sudo systemctl restart ollama

# 6. Final Check
sleep 2
if systemctl is-active --quiet ollama; then
    echo -e "${GREEN}✅ SUCCESS! Ollama is running correctly.${NC}"
else
    echo -e "${RED}❌ Service still failed. Checking logs...${NC}"
    sudo journalctl -u ollama --no-pager | tail -n 10
fi
