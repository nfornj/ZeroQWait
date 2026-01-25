#!/bin/bash
set -e

echo "Creating namespace..."
kubectl create namespace fastcuts || echo "Namespace might already exist"

echo "Applying PostgreSQL resources..."
kubectl apply -f ~/k8s/apps/fastcuts/postgres-pvc.yaml
kubectl apply -f ~/k8s/apps/fastcuts/postgres-secret.yaml
kubectl apply -f ~/k8s/apps/fastcuts/postgres-statefulset.yaml

echo "Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres -n fastcuts --timeout=120s || echo "Waiting for postgres..."

echo "Applying backend resources..."
kubectl apply -f ~/k8s/apps/fastcuts/backend-secret.yaml
kubectl apply -f ~/k8s/apps/fastcuts/backend-configmap.yaml
kubectl apply -f ~/k8s/apps/fastcuts/backend-deployment.yaml

echo "Applying frontend resources..."
kubectl apply -f ~/k8s/apps/fastcuts/frontend-deployment.yaml

echo "Deployment complete!"
echo ""
echo "Services exposed:"
echo "  Backend:  http://192.168.2.88:30000"
echo "  Frontend: http://192.168.2.88:30001"
echo ""
echo "Check status with:"
echo "  kubectl get pods -n fastcuts"
echo "  kubectl get services -n fastcuts"
