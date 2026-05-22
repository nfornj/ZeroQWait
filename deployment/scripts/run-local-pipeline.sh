#!/usr/bin/env bash
set -euo pipefail

# Local CI/CD pipeline:
# 1) test
# 2) build + push versioned images to local registry
# 3) update manifests with version tags
# 4) prune tags to keep last 10 versions
# 5) optionally sync Argo CD app

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REGISTRY="${REGISTRY:-ghcr.io/nfornj}"
VERSION_TAG="${VERSION_TAG:-v$(date +%Y%m%d%H%M%S)-$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD)}"
AUTO_COMMIT="${AUTO_COMMIT:-true}"
ARGOCD_SYNC="${ARGOCD_SYNC:-false}"
IMAGE_NAMESPACE="${IMAGE_NAMESPACE:-}"
# Comma-separated list of services to build. Empty = build all.
# Valid values: backend,frontend,asr-service,tts-service,voice-mcp,booking-mcp,finance-mcp,hr-mcp,simulation
SERVICES="${SERVICES:-backend,frontend,asr-service,tts-service,voice-mcp,booking-mcp,finance-mcp,hr-mcp,simulation}"
# Set SKIP_TESTS=true to skip backend pytest + frontend npm test steps
SKIP_TESTS="${SKIP_TESTS:-false}"
# Set SKIP_REGISTRY_PRUNE=true to avoid deleting newly-pushed images in the same run.
SKIP_REGISTRY_PRUNE="${SKIP_REGISTRY_PRUNE:-false}"
# Number of image tags to retain when pruning.
RETAIN_VERSIONS="${RETAIN_VERSIONS:-10}"

repo_for() {
  local image_name="$1"
  if [[ -n "${IMAGE_NAMESPACE}" ]]; then
    echo "${IMAGE_NAMESPACE}/${image_name}"
  else
    echo "${image_name}"
  fi
}

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
  # Optional: relative path from PROJECT_ROOT to Dockerfile (use with context "." for project-root builds)
  local dockerfile_override="${3:-}"
  local repo
  local image

  repo="$(repo_for "${name}")"
  image="${REGISTRY}/${repo}:${VERSION_TAG}"

  echo "==> Building ${image}"
  if [[ -n "${dockerfile_override}" ]]; then
    docker build --provenance=false -t "${image}" -f "${PROJECT_ROOT}/${dockerfile_override}" "${PROJECT_ROOT}/${context}"
  else
    docker build --provenance=false -t "${image}" "${PROJECT_ROOT}/${context}"
  fi
  docker push "${image}"
}

update_manifest_tag() {
  local file="$1"
  local image_name="$2"
  local target_repo="$3"
  # Escape dots in REGISTRY for use as a sed regex (e.g. ghcr.io → ghcr\.io)
  local escaped_registry
  escaped_registry="${REGISTRY//./\\.}"
  sed -i -E "s#image: ${escaped_registry}/([[:alnum:]_.-]+/)*${image_name}:[^[:space:]]+#image: ${REGISTRY}/${target_repo}:${VERSION_TAG}#g" "${file}"
}

should_build() {
  local svc="$1"
  [[ ",${SERVICES}," == *",${svc},"* ]]
}

main() {
  echo "==> Pipeline starting — VERSION_TAG=${VERSION_TAG}"
  if [[ -n "${IMAGE_NAMESPACE}" ]]; then
    echo "==> Image namespace: ${IMAGE_NAMESPACE}"
  fi
  echo "==> Services to build: ${SERVICES}"
  run_tests

  should_build "frontend"   && build_push "frontend"   "frontend"
  should_build "backend"    && build_push "backend"    "backend"
  should_build "asr-service" && build_push "asr-service" "asr_service"
  should_build "tts-service" && build_push "tts-service" "tts_service"
  should_build "voice-mcp"  && build_push "voice-mcp"  "mcps/voice"
  should_build "simulation" && build_push "simulation" "simulation"
  # booking/finance/hr MCPs need project root as context (Dockerfiles reference backend/ + mcps/X/)
  should_build "booking-mcp" && build_push "booking-mcp" "." "mcps/booking/Dockerfile"
  should_build "finance-mcp" && build_push "finance-mcp" "." "mcps/finance/Dockerfile"
  should_build "hr-mcp"      && build_push "hr-mcp"      "." "mcps/hr/Dockerfile"

  should_build "backend"     && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/backend-deployment.yaml"     "backend" "$(repo_for backend)"
  should_build "backend"     && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/temporal-worker-deployment.yaml" "backend" "$(repo_for backend)"
  should_build "frontend"    && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/frontend-deployment.yaml"    "frontend" "$(repo_for frontend)"
  should_build "asr-service" && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/asr-deployment.yaml"         "asr-service" "$(repo_for asr-service)"
  should_build "tts-service" && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/tts-deployment.yaml"         "tts-service" "$(repo_for tts-service)"
  should_build "voice-mcp"   && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/voice-mcp-deployment.yaml"   "voice-mcp" "$(repo_for voice-mcp)"
  should_build "simulation"  && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/simulation-deployment.yaml"  "simulation" "$(repo_for simulation)"
  should_build "booking-mcp" && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/booking-mcp-deployment.yaml" "booking-mcp" "$(repo_for booking-mcp)"
  should_build "finance-mcp" && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/finance-mcp-deployment.yaml" "finance-mcp" "$(repo_for finance-mcp)"
  should_build "hr-mcp"      && update_manifest_tag "${PROJECT_ROOT}/k8s-manifests/hr-mcp-deployment.yaml"      "hr-mcp" "$(repo_for hr-mcp)"

  if [[ "${AUTO_COMMIT}" == "true" ]]; then
    # Only stage manifests for services that were built
    local staged=()
    should_build "backend"     && staged+=("k8s-manifests/backend-deployment.yaml")
    should_build "backend"     && staged+=("k8s-manifests/temporal-worker-deployment.yaml")
    should_build "frontend"    && staged+=("k8s-manifests/frontend-deployment.yaml")
    should_build "asr-service" && staged+=("k8s-manifests/asr-deployment.yaml")
    should_build "tts-service" && staged+=("k8s-manifests/tts-deployment.yaml")
    should_build "voice-mcp"   && staged+=("k8s-manifests/voice-mcp-deployment.yaml")
    should_build "simulation"  && staged+=("k8s-manifests/simulation-deployment.yaml")
    should_build "booking-mcp" && staged+=("k8s-manifests/booking-mcp-deployment.yaml")
    should_build "finance-mcp" && staged+=("k8s-manifests/finance-mcp-deployment.yaml")
    should_build "hr-mcp"      && staged+=("k8s-manifests/hr-mcp-deployment.yaml")
    if [[ ${#staged[@]} -gt 0 ]]; then
      git -C "${PROJECT_ROOT}" add "${staged[@]}"
      git -C "${PROJECT_ROOT}" commit -m "ci: release ${VERSION_TAG}" || true
    fi
  fi

  if [[ "${SKIP_REGISTRY_PRUNE}" == "true" ]]; then
    echo "==> SKIP_REGISTRY_PRUNE=true — skipping prune/garbage-collect for this run"
  else
    local prune_repos=()
    should_build "backend" && prune_repos+=("$(repo_for backend)")
    should_build "frontend" && prune_repos+=("$(repo_for frontend)")
    should_build "asr-service" && prune_repos+=("$(repo_for asr-service)")
    should_build "tts-service" && prune_repos+=("$(repo_for tts-service)")
    should_build "voice-mcp"   && prune_repos+=("$(repo_for voice-mcp)")
    should_build "simulation"  && prune_repos+=("$(repo_for simulation)")
    should_build "booking-mcp" && prune_repos+=("$(repo_for booking-mcp)")
    should_build "finance-mcp" && prune_repos+=("$(repo_for finance-mcp)")
    should_build "hr-mcp"      && prune_repos+=("$(repo_for hr-mcp)")

    KEEP_VERSIONS="${RETAIN_VERSIONS}" REPOSITORIES="${prune_repos[*]}" "${PROJECT_ROOT}/deployment/scripts/prune-registry-tags.sh"
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
