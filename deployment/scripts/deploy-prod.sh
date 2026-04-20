#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
K8S_MANIFESTS="${PROJECT_ROOT}/k8s-manifests"

KUBECTL_CMD=()
KUBECONFIG_PATH=""

sudo_find_cmd() {
  local cmd_name="$1"
  sudo sh -c "command -v ${cmd_name}" 2>/dev/null | head -n1
}

resolve_kubectl_cmd() {
  # Prefer explicit kubectl binary if available to root.
  local sudo_kubectl="$(sudo_find_cmd kubectl || true)"
  if [[ -n "${sudo_kubectl}" ]]; then
    KUBECTL_CMD=("${sudo_kubectl}")
    return 0
  fi

  if command -v kubectl >/dev/null 2>&1; then
    KUBECTL_CMD=("$(command -v kubectl)")
    return 0
  fi

  # K3s bundles kubectl as a subcommand; use it when standalone kubectl is absent.
  local sudo_k3s="$(sudo_find_cmd k3s || true)"
  if [[ -n "${sudo_k3s}" ]]; then
    KUBECTL_CMD=("${sudo_k3s}" kubectl)
    return 0
  fi

  return 1
}

resolve_kubeconfig_path() {
  # Honor explicit KUBECONFIG when provided.
  if [[ -n "${KUBECONFIG:-}" && -f "${KUBECONFIG}" ]]; then
    KUBECONFIG_PATH="${KUBECONFIG}"
    return 0
  fi

  # Prefer local k3s admin kubeconfig when present.
  if [[ -f "/etc/rancher/k3s/k3s.yaml" ]]; then
    KUBECONFIG_PATH="/etc/rancher/k3s/k3s.yaml"
    return 0
  fi

  # Default to runner user's kubeconfig.
  if [[ -f "${HOME}/.kube/config" ]]; then
    KUBECONFIG_PATH="${HOME}/.kube/config"
    return 0
  fi

  return 1
}

ensure_k8s_api_reachable() {
  if kctl version --request-timeout=15s >/dev/null 2>&1; then
    return 0
  fi

  # If kubeconfig points to local k3s API, try to start/recover k3s and retry once.
  if grep -qE 'server:[[:space:]]+https://(127\.0\.0\.1|localhost):6443' "${KUBECONFIG_PATH}" 2>/dev/null; then
    echo "!! Kubernetes API unreachable on localhost:6443; attempting to start k3s service"
    sudo systemctl start k3s >/dev/null 2>&1 || true
    sleep 5
    if kctl version --request-timeout=20s >/dev/null 2>&1; then
      echo "==> Kubernetes API recovered after starting k3s"
      return 0
    fi
  fi

  return 1
}

kctl() {
  if [[ ${#KUBECTL_CMD[@]} -eq 0 ]]; then
    echo "!! Kubernetes CLI is not configured. Neither 'kubectl' nor 'k3s' was found for this runner." >&2
    echo "!! Install kubectl or ensure k3s is installed and accessible to sudo." >&2
    exit 1
  fi

  if [[ -n "${KUBECONFIG_PATH}" ]]; then
    sudo env KUBECONFIG="${KUBECONFIG_PATH}" "${KUBECTL_CMD[@]}" "$@"
  else
    sudo "${KUBECTL_CMD[@]}" "$@"
  fi
}

echo "==> Production deploy (prod branch)"
echo "==> Building and pushing versioned images"

cd "${PROJECT_ROOT}"

if ! resolve_kubectl_cmd; then
  echo "!! Production deploy aborted: unable to locate Kubernetes CLI on runner host." >&2
  exit 1
fi

if ! resolve_kubeconfig_path; then
  echo "!! Production deploy aborted: unable to locate kubeconfig for cluster access." >&2
  echo "!! Provide KUBECONFIG or ensure ~/.kube/config exists for the runner user." >&2
  exit 1
fi

echo "==> Using Kubernetes CLI: ${KUBECTL_CMD[*]}"
echo "==> Using kubeconfig: ${KUBECONFIG_PATH}"

if ! ensure_k8s_api_reachable; then
  echo "!! Production deploy aborted: Kubernetes API is unreachable with current kubeconfig." >&2
  exit 1
fi

echo "==> Ensuring required namespaces exist"
kctl create namespace zeroqwait --dry-run=client -o yaml | kctl apply -f -
kctl create namespace llm --dry-run=client -o yaml | kctl apply -f -

sudo env \
  SKIP_TESTS="${SKIP_TESTS:-true}" \
  IMAGE_NAMESPACE="prod" \
  RETAIN_VERSIONS="10" \
  SKIP_REGISTRY_PRUNE="true" \
  SERVICES="${SERVICES:-backend,frontend,asr-service,tts-service,voice-mcp}" \
  AUTO_COMMIT="false" \
  ARGOCD_SYNC="false" \
  bash "${PROJECT_ROOT}/deployment/scripts/run-local-pipeline.sh"

echo "==> Applying K8s manifests"
echo "==> Applying shared LLM manifests"
kctl apply -f "${K8S_MANIFESTS}/ollama-pvc.yaml"
kctl apply -f "${K8S_MANIFESTS}/ollama-deployment.yaml"

echo "==> Waiting for shared LLM rollout"
kctl rollout status deployment/ollama -n llm --timeout=900s

echo "==> Applying core data manifests (Postgres/Redis)"
# Secrets are NOT applied automatically — they contain REPLACE_ME placeholders in Git.
# On a fresh cluster, create the secrets manually BEFORE running this script:
#   kubectl apply -f k8s-manifests/postgres-secret.local.yaml
#   kubectl apply -f k8s-manifests/redis-secret.local.yaml
#   kubectl apply -f k8s-manifests/backend-secret.local.yaml
# (*.local.yaml files are gitignored; copy the templates and fill in real values)
#
# Pre-flight: abort if any required secret is missing in the cluster.
for _secret in backend-secret postgres-secret redis-secret; do
  if ! kctl get secret "${_secret}" -n zeroqwait >/dev/null 2>&1; then
    echo "!! Secret '${_secret}' not found in namespace zeroqwait." >&2
    echo "!! Apply it manually with real credentials before running this deploy." >&2
    echo "!! See k8s-manifests/${_secret}.yaml for the required keys." >&2
    exit 1
  fi
done
echo "==> Secrets verified (pre-existing in cluster)."

kctl apply -f "${K8S_MANIFESTS}/postgres-pvc.yaml"
kctl apply -f "${K8S_MANIFESTS}/postgres-statefulset.yaml"
kctl apply -f "${K8S_MANIFESTS}/redis-pvc.yaml"
kctl apply -f "${K8S_MANIFESTS}/redis-service.yaml"
kctl apply -f "${K8S_MANIFESTS}/redis-statefulset.yaml"

echo "==> Waiting for core data workloads"
kctl rollout status statefulset/postgres -n zeroqwait --timeout=300s
kctl rollout status statefulset/redis -n zeroqwait --timeout=300s

echo "==> Applying app manifests"
kctl apply -f "${K8S_MANIFESTS}/backend-configmap.yaml"
# Secret is pre-existing (not auto-applied — see note above).
kctl apply -f "${K8S_MANIFESTS}/backend-deployment.yaml"
kctl apply -f "${K8S_MANIFESTS}/frontend-deployment.yaml"
kctl apply -f "${K8S_MANIFESTS}/asr-deployment.yaml"
kctl apply -f "${K8S_MANIFESTS}/asr-service.yaml"
kctl apply -f "${K8S_MANIFESTS}/tts-deployment.yaml"
kctl apply -f "${K8S_MANIFESTS}/voice-mcp-deployment.yaml"
kctl apply -f "${K8S_MANIFESTS}/ingress-traefik.yaml"
kctl apply -f "${K8S_MANIFESTS}/network-policy.yaml"
kctl apply -f "${K8S_MANIFESTS}/backend-pdb.yaml"

# run-local-pipeline.sh already updated the backend image tag in the manifest
# (sed replaces localhost:5000/backend:* with the new versioned tag).
# The rollout restart triggers the new image to roll out.
kctl rollout restart deployment/backend -n zeroqwait

echo "==> Pruning production image tags (retain last 10 per service)"
sudo env \
  KEEP_VERSIONS="10" \
  REPOSITORIES="prod/backend prod/frontend prod/asr-service prod/tts-service prod/voice-mcp" \
  bash "${PROJECT_ROOT}/deployment/scripts/prune-registry-tags.sh"

echo "==> Waiting for frontend and backend rollouts"
kctl rollout status deployment/frontend -n zeroqwait --timeout=300s
# Pre-built image startup: ~2 min (model warm-up). 5 min ceiling is sufficient.
kctl rollout status deployment/backend -n zeroqwait --timeout=300s

echo "==> Production deployment successful"
echo "    Site: https://zeroqwait.com"
