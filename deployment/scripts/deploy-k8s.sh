#!/bin/bash
# ZeroQwait — Local Kubernetes Deployment
# Run directly on this machine (no SSH needed).
# Prerequisite: run bootstrap-server.sh once first.

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
K8S_MANIFESTS="$PROJECT_ROOT/k8s-manifests"
APPS_DIR="/home/neekrishrichu/apps"
REGISTRY="ghcr.io/nfornj"
REGISTRY_CONFIG_PATH="${PROJECT_ROOT}/deployment/registry/config.yml"

# K3s kubeconfig — readable by current user after bootstrap (--write-kubeconfig-mode=644)
export KUBECONFIG="/etc/rancher/k3s/k3s.yaml"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

NAMESPACE="zeroqwait"
DOMAIN="$(hostname -I | awk '{print $1}').nip.io"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   ZeroQwait — K8s Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}  Project : $PROJECT_ROOT${NC}"
echo -e "${YELLOW}  Apps dir: $APPS_DIR${NC}"
echo -e "${YELLOW}  Domain  : $DOMAIN${NC}"
echo -e "${YELLOW}  Registry: $REGISTRY (ghcr.io)${NC}"
echo ""

# ── Sanity checks ─────────────────────────────────────────────────────────
if ! command -v k3s &>/dev/null; then
    echo -e "${RED}✗ K3s not installed. Run: sudo bash deployment/scripts/bootstrap-server.sh${NC}"
    exit 1
fi

if ! sudo kubectl get nodes &>/dev/null; then
    echo -e "${RED}✗ K3s cluster not responding. Check: sudo systemctl status k3s${NC}"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}✗ Docker daemon not running. Start it with: sudo systemctl start docker${NC}"
    exit 1
fi

# Log in to ghcr.io (requires GITHUB_TOKEN or GHCR_TOKEN env var)
if [[ -z "${GITHUB_TOKEN:-}${GHCR_TOKEN:-}" ]]; then
    echo -e "${YELLOW}⚠  Neither GITHUB_TOKEN nor GHCR_TOKEN is set."
    echo -e "   Run: export GHCR_TOKEN=<your_ghcr_pat> before this script${NC}"
    exit 1
fi
echo "${GHCR_TOKEN:-$GITHUB_TOKEN}" | docker login ghcr.io -u nfornj --password-stdin

# Ensure runtime directories exist
mkdir -p "$APPS_DIR/zeroqwait/uploads" "$APPS_DIR/mcps/voice"
echo -e "${GREEN}✓ Pre-flight checks passed${NC}"
echo ""

# ── Helper: build image locally and push to local registry ───────────────
build_and_push() {
    local name="$1"   # e.g. "voice-mcp"
    local ctx="$2"    # build context dir, relative to PROJECT_ROOT
    local img="$REGISTRY/${name}:latest"
    echo -e "${BLUE}  Building ${name}...${NC}"
    docker build -t "$img" "$PROJECT_ROOT/$ctx"
    docker push "$img"
    echo -e "${GREEN}  ✓ ${img}${NC}"
}

# ── Namespace ─────────────────────────────────────────────────────────────
echo -e "${BLUE}[1/8] Namespace...${NC}"
sudo kubectl create namespace $NAMESPACE --dry-run=client -o yaml | sudo kubectl apply -f -
echo ""

# ── Secrets & config ──────────────────────────────────────────────────────
echo -e "${BLUE}[2/8] Secrets & ConfigMap...${NC}"
sudo kubectl apply -f "$K8S_MANIFESTS/postgres-secret.yaml"
sudo kubectl apply -f "$K8S_MANIFESTS/backend-secret.yaml"
sudo kubectl apply -f "$K8S_MANIFESTS/backend-configmap.yaml"
# Redis secret (may not exist yet — ignore error)
sudo kubectl apply -f "$K8S_MANIFESTS/redis-secret.yaml" 2>/dev/null || true
echo ""

# ── Storage (PVCs) ────────────────────────────────────────────────────────
echo -e "${BLUE}[3/9] Storage (PVCs)...${NC}"
sudo kubectl apply -f "$K8S_MANIFESTS/postgres-pvc.yaml"
sudo kubectl apply -f "$K8S_MANIFESTS/redis-pvc.yaml"
sudo kubectl apply -f "$K8S_MANIFESTS/tts-pvc.yaml"
sudo kubectl apply -f "$K8S_MANIFESTS/ollama-deployment.yaml"  # creates llm ns + PVC
echo ""

# ── Database ──────────────────────────────────────────────────────────────
echo -e "${BLUE}[4/9] GPU device plugin + time-slicing...${NC}"
sudo kubectl apply -f "$K8S_MANIFESTS/nvidia-device-plugin.yaml" || echo -e "${YELLOW}  ⚠  GPU device plugin apply failed (non-fatal)${NC}"
echo ""

# ── Database ──────────────────────────────────────────────────────────────
echo -e "${BLUE}[5/9] PostgreSQL + Redis...${NC}"
sudo kubectl apply -f "$K8S_MANIFESTS/postgres-statefulset.yaml"
sudo kubectl apply -f "$K8S_MANIFESTS/redis-statefulset.yaml"
sudo kubectl apply -f "$K8S_MANIFESTS/redis-service.yaml"
echo -e "  Waiting for PostgreSQL..."
sudo kubectl wait --for=condition=ready pod -l app=postgres -n $NAMESPACE --timeout=300s 2>/dev/null \
    || echo -e "${YELLOW}  ⚠  PostgreSQL still initializing (continuing)${NC}"
echo ""

# ── Build & push custom images ────────────────────────────────────────────
echo -e "${BLUE}[6/9] Building service images...${NC}"
build_and_push "frontend"    "frontend"      # uses frontend/Dockerfile
build_and_push "asr-service" "asr_service"
build_and_push "tts-service" "tts_service"
build_and_push "voice-mcp"   "mcps/voice"    # voice MCP gateway
echo ""

# ── Core services ─────────────────────────────────────────────────────────
echo -e "${BLUE}[7/9] Deploying backend, frontend, ASR, TTS...${NC}"
sudo kubectl apply -f "$K8S_MANIFESTS/backend-deployment.yaml"
sudo kubectl apply -f "$K8S_MANIFESTS/temporal-configmap.yaml"
sudo kubectl apply -f "$K8S_MANIFESTS/temporal-deployment.yaml"
sudo kubectl apply -f "$K8S_MANIFESTS/temporal-worker-deployment.yaml"
sudo kubectl apply -f "$K8S_MANIFESTS/frontend-deployment.yaml"
sudo kubectl apply -f "$K8S_MANIFESTS/asr-deployment.yaml"
sudo kubectl apply -f "$K8S_MANIFESTS/asr-service.yaml"
sudo kubectl apply -f "$K8S_MANIFESTS/tts-deployment.yaml"
echo ""

# ── Voice MCP gateway ─────────────────────────────────────────────────────
echo -e "${BLUE}[8/9] Deploying Voice MCP gateway...${NC}"
sudo kubectl apply -f "$K8S_MANIFESTS/voice-mcp-deployment.yaml"
sudo kubectl rollout restart deployment/voice-mcp -n $NAMESPACE 2>/dev/null || true
echo ""

# ── Ingress ───────────────────────────────────────────────────────────────
echo -e "${BLUE}[9/9] Traefik Ingress...${NC}"
sudo kubectl apply -f "$K8S_MANIFESTS/ingress-traefik.yaml"
echo ""

# ── Wait for critical deployments ────────────────────────────────────────
echo -e "${BLUE}Waiting for deployments to become available...${NC}"
sudo kubectl wait --for=condition=available --timeout=300s deployment/backend  -n $NAMESPACE 2>/dev/null \
    || echo -e "${YELLOW}  ⚠  backend still starting (startup probe takes ~2min)${NC}"
sudo kubectl wait --for=condition=available --timeout=300s deployment/temporal -n $NAMESPACE 2>/dev/null \
    || echo -e "${YELLOW}  ⚠  temporal still starting${NC}"
sudo kubectl wait --for=condition=available --timeout=300s deployment/temporal-worker -n $NAMESPACE 2>/dev/null \
    || echo -e "${YELLOW}  ⚠  temporal-worker still starting${NC}"
sudo kubectl wait --for=condition=available --timeout=120s  deployment/frontend -n $NAMESPACE 2>/dev/null \
    || echo -e "${YELLOW}  ⚠  frontend still starting${NC}"

# ── Final summary ─────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}  App URL : http://$DOMAIN/${NC}"
echo -e "${YELLOW}  API     : http://$DOMAIN/api/docs${NC}"
echo -e "${YELLOW}  Voice MCP health: http://$DOMAIN/api/voice/tts/health${NC}"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo "  sudo kubectl get pods -n $NAMESPACE"
echo "  sudo kubectl get pods -n llm  (Ollama)"
echo "  sudo kubectl logs -n $NAMESPACE -l app=backend -f"
echo "  sudo kubectl logs -n $NAMESPACE -l app=voice-mcp -f"
echo "  sudo kubectl rollout restart deployment/backend -n $NAMESPACE"
echo ""
echo -e "${YELLOW}NOTE: gpt-oss:20b model must be pulled after first deploy:${NC}"
echo "  sudo kubectl exec -n llm deployment/ollama -- ollama pull gpt-oss:20b"

