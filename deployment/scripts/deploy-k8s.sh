#!/bin/bash

# ZeroQwait Kubernetes Deployment
# Deploys to Kubernetes cluster with Traefik Ingress and monitoring

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
K8S_MANIFESTS="$PROJECT_ROOT/deployment/kubernetes"

echo "🚀 Starting ZeroQwait Kubernetes Deployment"
echo "=========================================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
CLUSTER_IP="192.168.2.88"
NAMESPACE="zeroqwait"
DOMAIN="192.168.2.88.nip.io"

echo -e "${BLUE}⚙️  Configuration:${NC}"
echo "  Cluster IP: $CLUSTER_IP"
echo "  Domain: $DOMAIN"
echo "  Namespace: $NAMESPACE"
echo ""

# Check kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl not found!${NC}"
    exit 1
fi

# Use sudo for kubectl if needed (for k3s permission issues)
KUBECTL="sudo kubectl"
echo -e "${BLUE}✓ kubectl: Using sudo kubectl${NC}"
echo ""

# Create namespace
echo -e "${BLUE}📋 Creating namespace...${NC}"
$KUBECTL create namespace $NAMESPACE --dry-run=client -o yaml | $KUBECTL apply -f -
echo "✓ Namespace ready"
echo ""

# Create secrets & config
echo -e "${BLUE}📋 Setting up secrets and configuration...${NC}"
$KUBECTL apply -f "$K8S_MANIFESTS/postgres-secret.yaml"
$KUBECTL apply -f "$K8S_MANIFESTS/backend-secret.yaml"
$KUBECTL apply -f "$K8S_MANIFESTS/backend-configmap.yaml"
echo "✓ Secrets and ConfigMaps created"
echo ""

# Database
echo -e "${BLUE}📋 Setting up database...${NC}"
$KUBECTL apply -f "$K8S_MANIFESTS/postgres-statefulset.yaml"
$KUBECTL apply -f "$K8S_MANIFESTS/postgres-pvc.yaml"
echo "⏳ Waiting for PostgreSQL..."
$KUBECTL wait --for=condition=ready pod -l app=postgres -n $NAMESPACE --timeout=300s 2>/dev/null || echo "⚠️  PostgreSQL initializing..."
echo ""

# Deploy backend & frontend
echo -e "${BLUE}📋 Deploying backend...${NC}"
$KUBECTL apply -f "$K8S_MANIFESTS/backend-deployment.yaml"

echo -e "${BLUE}📋 Deploying frontend...${NC}"
$KUBECTL apply -f "$K8S_MANIFESTS/frontend-deployment.yaml"

echo "⏳ Waiting for deployments..."
$KUBECTL wait --for=condition=available --timeout=300s deployment/backend -n $NAMESPACE 2>/dev/null || echo "⚠️  Backend deploying..."
echo ""

# Ingress
echo -e "${BLUE}📋 Setting up Traefik Ingress...${NC}"
$KUBECTL apply -f "$K8S_MANIFESTS/ingress-traefik.yaml"
echo "✓ Ingress configured"
echo ""

# Status
echo ""
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo "=========================================================="
echo ""
echo -e "${YELLOW}🌐 Access Your Application:${NC}"
echo ""
echo "  Base URL:"
echo "    http://$DOMAIN/"
echo ""
echo "  Backend API:"
echo "    http://$DOMAIN/api"
echo "    http://$DOMAIN/api/docs (Swagger UI)"
echo ""
echo "  After login:"
echo "    http://shopname.$DOMAIN/dashboard"
echo ""

echo -e "${YELLOW}🐛 Debugging:${NC}"
echo "  Check pod status:"
echo "    sudo kubectl get pods -n $NAMESPACE"
echo ""
echo "  View logs:"
echo "    sudo kubectl logs -n $NAMESPACE -l app=backend -f"
echo ""
echo "  Check ingress:"
echo "    sudo kubectl get ingress -n $NAMESPACE"
echo ""

echo -e "${YELLOW}📊 Monitoring:${NC}"
echo "  Setup Prometheus & Grafana:"
echo "    bash ../scripts/setup-monitoring.sh"
echo ""
