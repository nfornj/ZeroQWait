#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
K8S_MANIFESTS="${PROJECT_ROOT}/k8s-manifests"

echo "==> Production deploy (prod branch)"
echo "==> Building and pushing versioned images"

cd "${PROJECT_ROOT}"

sudo env \
  SKIP_TESTS="${SKIP_TESTS:-true}" \
  SERVICES="${SERVICES:-backend,frontend,asr-service,tts-service,voice-mcp}" \
  AUTO_COMMIT="false" \
  ARGOCD_SYNC="false" \
  bash "${PROJECT_ROOT}/deployment/scripts/run-local-pipeline.sh"

echo "==> Applying K8s manifests"
sudo kubectl apply -f "${K8S_MANIFESTS}/backend-deployment.yaml"
sudo kubectl apply -f "${K8S_MANIFESTS}/frontend-deployment.yaml"
sudo kubectl apply -f "${K8S_MANIFESTS}/asr-deployment.yaml"
sudo kubectl apply -f "${K8S_MANIFESTS}/asr-service.yaml"
sudo kubectl apply -f "${K8S_MANIFESTS}/tts-deployment.yaml"
sudo kubectl apply -f "${K8S_MANIFESTS}/voice-mcp-deployment.yaml"
sudo kubectl apply -f "${K8S_MANIFESTS}/ingress-traefik.yaml"

# Backend currently runs from hostPath code; restart to pick latest branch code.
sudo kubectl rollout restart deployment/backend -n zeroqwait

echo "==> Waiting for frontend and backend rollouts"
sudo kubectl rollout status deployment/frontend -n zeroqwait --timeout=300s
sudo kubectl rollout status deployment/backend -n zeroqwait --timeout=300s

echo "==> Production deployment successful"
echo "    Site: https://zeroqwait.com"
