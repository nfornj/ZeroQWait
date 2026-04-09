#!/usr/bin/env bash
set -euo pipefail

# Local CI/CD pipeline:
# 1) test
# 2) build + push versioned images to local registry
# 3) update manifests with version tags
# 4) prune tags to keep last 10 versions
# 5) optionally sync Argo CD app

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REGISTRY="${REGISTRY:-localhost:5000}"
VERSION_TAG="${VERSION_TAG:-v$(date +%Y%m%d%H%M%S)-$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD)}"
AUTO_COMMIT="${AUTO_COMMIT:-true}"
ARGOCD_SYNC="${ARGOCD_SYNC:-false}"
# Comma-separated list of services to build. Empty = build all.
# Valid values: backend,frontend,asr-service,tts-service,voice-mcp
SERVICES="${SERVICES:-backend,frontend,asr-service,tts-service,voice-mcp}"
# Set SKIP_TESTS=true to skip backend pytest + frontend npm test steps
SKIP_TESTS="${SKIP_TESTS:-false}"
# Set SKIP_REGISTRY_PRUNE=true to avoid deleting newly-pushed images in the same run.
SKIP_REGISTRY_PRUNE="${SKIP_REGISTRY_PRUNE:-false}"

run_tests() {
  if [[ "${SKIP_TESTS}" == "true" ]]; then
    echo "==> SKIP_TESTS=true — skipping all tests"
    return 0
  fi

  echo "==> Running backend smoke tests"
  if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    PYTHON="${PROJECT_ROOT}/.venv/bin/python"
  else
    PYTHON="$(command -v python3 || command -v python)"
  fi
  # Smoke test: verify key modules are importable (no live services needed)
  (
    cd "${PROJECT_ROOT}/backend"
    "${PYTHON}" -c "
import sys, importlib
modules = ['fastapi', 'sqlalchemy', 'pydantic', 'redis', 'httpx']
failed = []
for m in modules:
    try:
        importlib.import_module(m)
    except ImportError as e:
        failed.append(f'{m}: {e}')
if failed:
    print('SMOKE TEST FAILED:')
    for f in failed:
        print(' ', f)
    sys.exit(1)
print('Smoke tests passed:', ', '.join(modules))
"
  )

  echo "==> Running frontend lint + build"
  (
    cd "${PROJECT_ROOT}/frontend"
    npm ci --silent
    CI=true npm test -- --watchAll=false --passWithNoTests
    npm run build
  )
}

build_push() {
  local name="$1"
  local context="$2"
  local image="${REGISTRY}/${name}:${VERSION_TAG}"

  echo "==> Building ${image}"
  docker build -t "${image}" "${PROJECT_ROOT}/${context}"
  docker push "${image}"
}

update_manifest_tag() {
  local file="$1"
  local image_name="$2"
  sed -i -E "s#image: ${REGISTRY}/${image_name}:[^[:space:]]+#image: ${REGISTRY}/${image_name}:${VERSION_TAG}#g" "${file}"
}

should_build() {
  local svc="$1"
  [[ ",${SERVICES}," == *",${svc},"* ]]
}

main() {
  echo "==> Pipeline starting — VERSION_TAG=${VERSION_TAG}"
  echo "==> Services to build: ${SERVICES}"
  run_tests

  should_build "frontend"   && build_push "frontend"   "frontend"
  should_build "backend"    && build_push "backend"    "backend"
  should_build "asr-service" && build_push "asr-service" "asr_service"
  should_build "tts-service" && build_push "tts-service" "tts_service"
  should_build "voice-mcp"  && build_push "voice-mcp"  "mcps/voice"

  should_build "backend"     && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/backend-deployment.yaml"     "backend"
  should_build "frontend"    && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/frontend-deployment.yaml"    "frontend"
  should_build "asr-service" && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/asr-deployment.yaml"         "asr-service"
  should_build "tts-service" && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/tts-deployment.yaml"         "tts-service"
  should_build "voice-mcp"   && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/voice-mcp-deployment.yaml"   "voice-mcp"

  if [[ "${AUTO_COMMIT}" == "true" ]]; then
    # Only stage manifests for services that were built
    local staged=()
    should_build "backend"     && staged+=("k8s-manifests/backend-deployment.yaml")
    should_build "frontend"    && staged+=("k8s-manifests/frontend-deployment.yaml")
    should_build "asr-service" && staged+=("k8s-manifests/asr-deployment.yaml")
    should_build "tts-service" && staged+=("k8s-manifests/tts-deployment.yaml")
    should_build "voice-mcp"   && staged+=("k8s-manifests/voice-mcp-deployment.yaml")
    if [[ ${#staged[@]} -gt 0 ]]; then
      git -C "${PROJECT_ROOT}" add "${staged[@]}"
      git -C "${PROJECT_ROOT}" commit -m "ci: release ${VERSION_TAG}" || true
    fi
  fi

  if [[ "${SKIP_REGISTRY_PRUNE}" == "true" ]]; then
    echo "==> SKIP_REGISTRY_PRUNE=true — skipping prune/garbage-collect for this run"
  else
    KEEP_VERSIONS=10 "${PROJECT_ROOT}/deployment/scripts/prune-registry-tags.sh"
  fi

  if [[ "${ARGOCD_SYNC}" == "true" ]]; then
    if command -v argocd >/dev/null 2>&1; then
      argocd app sync zeroqwait
    else
      echo "argocd CLI not found; skipping manual sync (Argo auto-sync will handle it)."
    fi
  fi

  echo "==> Release complete: ${VERSION_TAG}"
}

main "$@"
