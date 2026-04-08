#!/bin/bash
# ZeroQwait — One-time server bootstrap
# Run this ONCE on a fresh machine before using deploy-k8s.sh
#
# What this does:
#   1. Creates the apps/ directory structure
#   2. Starts a local Docker image registry at localhost:5000
#   3. Installs K3s (lightweight K8s) and configures it to trust localhost:5000
#   4. Waits for the cluster to be ready

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

APPS_DIR="/home/neekrishrichu/apps"
PROJECT_ROOT="/home/neekrishrichu/projects/FastCuts"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   ZeroQwait — Server Bootstrap${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ── 1. Directory structure ────────────────────────────────────────────────
echo -e "${BLUE}[1/4] Creating app directory structure...${NC}"

mkdir -p \
    "$APPS_DIR/zeroqwait/uploads" \
    "$APPS_DIR/zeroqwait/logs" \
    "$APPS_DIR/mcps/voice"

# Give the running user (neekrishrichu) ownership — K8s pods run as root
# but we want the user able to inspect/clear these dirs.
chown -R "$(logname 2>/dev/null || echo neekrishrichu):" "$APPS_DIR" 2>/dev/null || true

echo -e "${GREEN}  ✓ $APPS_DIR/${NC}"
echo -e "${GREEN}  ✓ $APPS_DIR/zeroqwait/uploads${NC}"
echo -e "${GREEN}  ✓ $APPS_DIR/zeroqwait/logs${NC}"
echo -e "${GREEN}  ✓ $APPS_DIR/mcps/voice${NC}"
echo ""

# ── 2. Local Docker registry ──────────────────────────────────────────────
echo -e "${BLUE}[2/4] Setting up local Docker registry (localhost:5000)...${NC}"

if docker ps --format '{{.Names}}' | grep -q "^local-registry$"; then
    echo -e "${YELLOW}  ↻ Registry already running — skipping${NC}"
else
    if docker ps -a --format '{{.Names}}' | grep -q "^local-registry$"; then
        docker start local-registry
        echo -e "${GREEN}  ✓ Restarted existing registry container${NC}"
    else
        docker run -d \
            --name local-registry \
            --restart=always \
            -p 5000:5000 \
            -v "$APPS_DIR/docker-registry:/var/lib/registry" \
            registry:2
        echo -e "${GREEN}  ✓ Started new registry container${NC}"
    fi
fi
echo ""

# ── 3. K3s install ────────────────────────────────────────────────────────
echo -e "${BLUE}[3/4] Installing K3s...${NC}"

if command -v k3s &>/dev/null; then
    echo -e "${YELLOW}  ↻ K3s already installed ($(k3s --version | head -1)) — skipping install${NC}"
else
    echo "  Downloading and installing K3s..."

    # Write K3s registry config BEFORE install so it is picked up at first start
    sudo mkdir -p /etc/rancher/k3s
    sudo tee /etc/rancher/k3s/registries.yaml > /dev/null <<'REGISTRIES_EOF'
mirrors:
  "localhost:5000":
    endpoint:
      - "http://localhost:5000"
REGISTRIES_EOF
    echo -e "${GREEN}  ✓ K3s registries.yaml written${NC}"

    # Install K3s — uses containerd (production default)
    # INSTALL_K3S_EXEC passes extra flags; disable traefik v1 (we apply our own ingress manifest)
    curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --write-kubeconfig-mode=644" sh -
    echo -e "${GREEN}  ✓ K3s installed${NC}"
fi

# Ensure registries.yaml exists even if K3s was already installed
if [[ ! -f /etc/rancher/k3s/registries.yaml ]]; then
    sudo mkdir -p /etc/rancher/k3s
    sudo tee /etc/rancher/k3s/registries.yaml > /dev/null <<'REGISTRIES_EOF'
mirrors:
  "localhost:5000":
    endpoint:
      - "http://localhost:5000"
REGISTRIES_EOF
    echo -e "${GREEN}  ✓ K3s registries.yaml written${NC}"
    sudo systemctl restart k3s
fi
echo ""

# ── 4. Wait for cluster ───────────────────────────────────────────────────
echo -e "${BLUE}[4/4] Waiting for K3s cluster to be ready...${NC}"
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

MAX_WAIT=120
WAITED=0
until sudo kubectl get nodes &>/dev/null; do
    if [[ $WAITED -ge $MAX_WAIT ]]; then
        echo -e "${RED}  ✗ K3s did not become ready within ${MAX_WAIT}s${NC}"
        echo "    Check: sudo systemctl status k3s"
        exit 1
    fi
    printf "."
    sleep 3
    WAITED=$((WAITED + 3))
done
echo ""

# Wait for the node to be Ready
sudo kubectl wait --for=condition=Ready node --all --timeout=120s
echo -e "${GREEN}  ✓ K3s cluster is ready${NC}"
echo ""

# ── Show kubectl shortcut hint ────────────────────────────────────────────
echo -e "${YELLOW}Tip: Add to your ~/.bashrc for password-free kubectl:${NC}"
echo "  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Bootstrap complete!${NC}"
echo -e "${GREEN}  Run next: bash deployment/scripts/deploy-k8s.sh${NC}"
echo -e "${GREEN}========================================${NC}"
