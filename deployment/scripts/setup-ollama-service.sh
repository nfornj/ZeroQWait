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
OLLAMA_PATH=""

# Try finding it via 'which'
if command -v ollama &> /dev/null; then
    OLLAMA_PATH=$(command -v ollama)
fi

# Fallback: Extract from running process (since permissions might hide the file)
if [ -z "$OLLAMA_PATH" ]; then
    echo -e "${YELLOW}Binary hidden? Checking running process...${NC}"
    # Grab the command path from ps output (e.g., "/bin/ollama serve" -> "/bin/ollama")
    RUNNING_PATH=$(ps aux | grep 'ollama serve' | grep -v grep | awk '{print $11}' | head -n 1)
    if [ -n "$RUNNING_PATH" ]; then
        OLLAMA_PATH=$RUNNING_PATH
        echo -e "${BLUE}Found running instance at: $OLLAMA_PATH${NC}"
    fi
fi

# Final Fallback: Hardcode if ps said /bin/ollama earlier
if [ -z "$OLLAMA_PATH" ]; then
    if [ -f "/bin/ollama" ]; then OLLAMA_PATH="/bin/ollama"; fi
    if [ -f "/usr/bin/ollama" ]; then OLLAMA_PATH="/usr/bin/ollama"; fi
    if [ -f "/usr/local/bin/ollama" ]; then OLLAMA_PATH="/usr/local/bin/ollama"; fi
fi

if [ -z "$OLLAMA_PATH" ]; then
     # Trust the previous evidence if everything else fails
     echo -e "${YELLOW}Warning: Could not verify path permissions. Assuming /bin/ollama based on logs.${NC}"
     OLLAMA_PATH="/bin/ollama"
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
