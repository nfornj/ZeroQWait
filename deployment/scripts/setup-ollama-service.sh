#!/bin/bash

# ZeroQwait Ollama Service Setup
# Installs Ollama as a proper systemd service for stability.

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Setting up Stable Ollama Service${NC}"
echo "========================================"

# 1. Define Service File
SERVICE_FILE="/etc/systemd/system/ollama.service"
OLLAMA_PATH="/bin/ollama" # As found by ps aux

if [ ! -f "$OLLAMA_PATH" ]; then
    echo -e "${YELLOW}Could not find /bin/ollama. Trying 'which ollama'...${NC}"
    OLLAMA_PATH=$(which ollama || echo "")
fi

if [ -z "$OLLAMA_PATH" ]; then
    echo -e "${RED}❌ Error: Could not find 'ollama' binary.${NC}"
    exit 1
fi

echo -e "${BLUE}Found Ollama at: $OLLAMA_PATH${NC}"

# 2. Create Systemd Service
echo -e "${BLUE}📝 Creating service file at $SERVICE_FILE...${NC}"

# Check for sudo
if ! sudo -n true 2>/dev/null; then
    echo -e "${YELLOW}🔑 Sudo access required to install service.${NC}"
fi

cat <<EOF | sudo tee $SERVICE_FILE
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=$OLLAMA_PATH serve
User=root
Group=root
Restart=always
RestartSec=3
Environment="OLLAMA_HOST=0.0.0.0"

[Install]
WantedBy=default.target
EOF

# 3. Reload and Start
echo -e "${BLUE}🔄 Reloading systemd...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl restart ollama

# 4. Verification
echo -e "${BLUE}⏳ Waiting for service to start...${NC}"
sleep 5

if systemctl is-active --quiet ollama; then
    echo -e "${GREEN}✅ Ollama Service is RUNNING and STABLE!${NC}"
    echo "It will now auto-start on boot."
else
    echo -e "${RED}❌ Error: Service failed to start.${NC}"
    sudo systemctl status ollama
fi
echo "========================================"
