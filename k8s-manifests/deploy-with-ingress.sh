#!/bin/bash

# FastCuts Deployment with Ingress Controller
# This script sets up subdomain routing for shop owners

set -e

echo "======================================"
echo "FastCuts Deployment with Ingress"
echo "======================================"
echo ""

export KUBECONFIG=~/.kube/config

# Check if nginx-ingress is installed
echo "1. Checking for nginx-ingress controller..."
if kubectl get namespace ingress-nginx &> /dev/null; then
    echo "   ✓ nginx-ingress namespace exists"
else
    echo "   Installing nginx-ingress controller..."
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/baremetal/deploy.yaml
    echo "   Waiting for ingress controller to be ready..."
    sleep 30
    kubectl wait --namespace ingress-nginx \
      --for=condition=ready pod \
      --selector=app.kubernetes.io/component=controller \
      --timeout=120s || echo "   Still starting..."
fi

echo ""
echo "2. Applying Ingress configuration..."
kubectl apply -f ~/k8s/apps/fastcuts/ingress.yaml

echo ""
echo "3. Checking ingress status..."
kubectl get ingress -n fastcuts

echo ""
echo "======================================"
echo "Deployment Complete!"
echo "======================================"
echo ""
echo "Access your application:"
echo "  Main site:    http://192.168.2.88.nip.io"
echo "  Or direct:    http://192.168.2.88:30001"
echo ""
echo "Shop owner subdomain example:"
echo "  downtown-barbershop.192.168.2.88.nip.io"
echo ""
echo "API endpoints:"
echo "  http://192.168.2.88.nip.io/api"
echo "  http://192.168.2.88:30000/api (direct)"
echo ""
echo "Note: Shop owners will automatically be redirected"
echo "      to their dashboard after login."
echo ""
