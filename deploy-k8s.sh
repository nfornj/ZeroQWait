#!/bin/bash

# ZeroQwait Kubernetes Deployment Script with Subdomain Support
# Deploys to K8s cluster with Traefik Ingress for shop subdomains

set -e

echo "🚀 Starting ZeroQwait Kubernetes Deployment with Subdomain Support"
echo "=================================================================="
echo ""

# Colors for output
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

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl not found. Please install kubectl.${NC}"
    exit 1
fi

echo -e "${BLUE}📋 Step 1: Creating namespace...${NC}"
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
echo "✓ Namespace '$NAMESPACE' ready"
echo ""

echo -e "${BLUE}📋 Step 2: Creating secrets...${NC}"
kubectl apply -f k8s-manifests/postgres-secret.yaml
kubectl apply -f k8s-manifests/backend-secret.yaml
echo "✓ Secrets created"
echo ""

echo -e "${BLUE}📋 Step 3: Creating ConfigMap...${NC}"
kubectl apply -f k8s-manifests/backend-configmap.yaml
echo "✓ ConfigMap created with correct URLs for Traefik"
echo ""

echo -e "${BLUE}📋 Step 4: Setting up database...${NC}"
kubectl apply -f k8s-manifests/postgres-statefulset.yaml
kubectl apply -f k8s-manifests/postgres-pvc.yaml
echo "⏳ Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres -n $NAMESPACE --timeout=300s 2>/dev/null || echo "⚠️  PostgreSQL startup in progress"
echo ""

echo -e "${BLUE}📋 Step 5: Deploying backend...${NC}"
kubectl apply -f k8s-manifests/backend-deployment.yaml
echo "⏳ Waiting for backend to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/backend -n $NAMESPACE 2>/dev/null || echo "⚠️  Backend deployment in progress"
echo ""

echo -e "${BLUE}📋 Step 6: Deploying frontend...${NC}"
kubectl apply -f k8s-manifests/frontend-deployment.yaml
echo "⏳ Waiting for frontend to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/frontend -n $NAMESPACE 2>/dev/null || echo "⚠️  Frontend deployment in progress"
echo ""

echo -e "${BLUE}📋 Step 7: Setting up Ingress with Traefik...${NC}"
kubectl apply -f k8s-manifests/ingress-traefik.yaml
echo "✓ Traefik Ingress configured with subdomain support"
echo ""

echo ""
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo "=================================================================="
echo ""
echo -e "${YELLOW}🌐 Access Your Application:${NC}"
echo ""
echo "  Base URL (for login):"
echo "    http://$DOMAIN/"
echo ""
echo "  After login, you'll be redirected to your shop:"
echo "    http://shopname.$DOMAIN/dashboard"
echo ""
echo "  Examples (replace 'shopname' with actual shop slug):"
echo "    http://pizza-palace.$DOMAIN/"
echo "    http://coffee-shop.$DOMAIN/"
echo ""
echo -e "${YELLOW}🔍 Backend API:${NC}"
echo "    http://$DOMAIN/api"
echo "    http://$DOMAIN/api/docs (Swagger UI)"
echo ""
echo -e "${YELLOW}🐛 Debugging:${NC}"
echo "  Check pod status:"
echo "    kubectl get pods -n $NAMESPACE"
echo ""
echo "  View logs:"
echo "    kubectl logs -n $NAMESPACE -l app=backend -f"
echo "    kubectl logs -n $NAMESPACE -l app=frontend -f"
echo ""
echo "  Describe deployment:"
echo "    kubectl describe deployment backend -n $NAMESPACE"
echo "    kubectl describe deployment frontend -n $NAMESPACE"
echo ""
echo "  Check ingress:"
echo "    kubectl get ingress -n $NAMESPACE"
echo ""
echo -e "${YELLOW}✨ Features:${NC}"
echo "  ✓ Multi-shop support with subdomains"
echo "  ✓ Automatic redirect to shop subdomain after login"
echo "  ✓ Shop-specific data isolation"
echo "  ✓ PostgreSQL persistence"
echo "  ✓ Traefik load balancing"
echo ""
echo -e "${BLUE}💡 Troubleshooting:${NC}"
echo "  If pods are not starting:"
echo "    1. Check pod logs: kubectl logs <pod-name> -n $NAMESPACE"
echo "    2. Verify images exist: docker images"
echo "    3. Check persistent volumes: kubectl get pvc -n $NAMESPACE"
echo ""
echo -e "${YELLOW}🔒 Important Notes:${NC}"
echo "  ✓ Make sure 192.168.2.88 is reachable from your browser"
echo "  ✓ nip.io is used for DNS resolution (no setup needed)"
echo "  ✓ Subdomain auto-redirects work only with valid shop slugs"
echo ""
