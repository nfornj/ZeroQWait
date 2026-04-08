#!/usr/bin/env bash
set -euo pipefail

# Installs Argo CD and registers the ZeroQwait app from this repo.
# Usage:
#   ./deployment/scripts/setup-argocd-gitops.sh
# Optional:
#   REPO_URL=... TARGET_REVISION=main ./deployment/scripts/setup-argocd-gitops.sh

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_TEMPLATE="${PROJECT_ROOT}/k8s-manifests/argocd/zeroqwait-app.template.yaml"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required"
  exit 1
fi

REPO_URL="${REPO_URL:-$(git -C "${PROJECT_ROOT}" config --get remote.origin.url || true)}"
TARGET_REVISION="${TARGET_REVISION:-$(git -C "${PROJECT_ROOT}" rev-parse --abbrev-ref HEAD || echo main)}"

if [[ -z "${REPO_URL}" ]]; then
  echo "Could not detect git remote. Set REPO_URL and rerun."
  exit 1
fi

echo "Installing Argo CD..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=300s

tmp_file=$(mktemp)
sed "s|__REPO_URL__|${REPO_URL}|g; s|__TARGET_REVISION__|${TARGET_REVISION}|g" "${APP_TEMPLATE}" > "${tmp_file}"
kubectl apply -f "${tmp_file}"
rm -f "${tmp_file}"

echo "Argo CD app created: zeroqwait"
echo "Port-forward UI with: kubectl port-forward svc/argocd-server -n argocd 8080:443"
echo "Initial admin password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath=\"{.data.password}\" | base64 -d; echo"
