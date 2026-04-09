#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
K8S_MANIFESTS="${PROJECT_ROOT}/k8s-manifests"

KUBECTL_CMD=()

resolve_kubectl_cmd() {
  # Prefer explicit kubectl binary if available to root.
  if sudo command -v kubectl >/dev/null 2>&1; then
    KUBECTL_CMD=("$(sudo command -v kubectl)")
    return 0
  fi

  if command -v kubectl >/dev/null 2>&1; then
    KUBECTL_CMD=("$(command -v kubectl)")
    return 0
  fi

  # K3s bundles kubectl as a subcommand; use it when standalone kubectl is absent.
  if sudo command -v k3s >/dev/null 2>&1; then
    KUBECTL_CMD=("$(sudo command -v k3s)" kubectl)
    return 0
  fi

  return 1
}

kctl() {
  if [[ ${#KUBECTL_CMD[@]} -eq 0 ]]; then
    echo "!! Kubernetes CLI is not configured. Neither 'kubectl' nor 'k3s' was found for this runner." >&2
    echo "!! Install kubectl or ensure k3s is installed and accessible to sudo." >&2
    exit 1
  fi

  sudo "${KUBECTL_CMD[@]}" "$@"
}

echo "==> Production deploy (prod branch)"
echo "==> Building and pushing versioned images"

cd "${PROJECT_ROOT}"

if ! resolve_kubectl_cmd; then
  echo "!! Production deploy aborted: unable to locate Kubernetes CLI on runner host." >&2
  exit 1
fi

echo "==> Using Kubernetes CLI: ${KUBECTL_CMD[*]}"

sudo env \
  SKIP_TESTS="${SKIP_TESTS:-true}" \
  SERVICES="${SERVICES:-backend,frontend,asr-service,tts-service,voice-mcp}" \
  AUTO_COMMIT="false" \
  ARGOCD_SYNC="false" \
  bash "${PROJECT_ROOT}/deployment/scripts/run-local-pipeline.sh"

echo "==> Applying K8s manifests"
kctl apply -f "${K8S_MANIFESTS}/backend-deployment.yaml"
kctl apply -f "${K8S_MANIFESTS}/frontend-deployment.yaml"
kctl apply -f "${K8S_MANIFESTS}/asr-deployment.yaml"
kctl apply -f "${K8S_MANIFESTS}/asr-service.yaml"
kctl apply -f "${K8S_MANIFESTS}/tts-deployment.yaml"
kctl apply -f "${K8S_MANIFESTS}/voice-mcp-deployment.yaml"
kctl apply -f "${K8S_MANIFESTS}/ingress-traefik.yaml"

# Backend currently runs from hostPath code; restart to pick latest branch code.
kctl rollout restart deployment/backend -n zeroqwait

echo "==> Waiting for frontend and backend rollouts"
kctl rollout status deployment/frontend -n zeroqwait --timeout=300s
kctl rollout status deployment/backend -n zeroqwait --timeout=300s

echo "==> Production deployment successful"
echo "    Site: https://zeroqwait.com"
