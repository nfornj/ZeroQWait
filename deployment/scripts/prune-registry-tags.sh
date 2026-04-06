#!/usr/bin/env bash
set -euo pipefail

# Keep only last N tags per repository in Docker Registry v2.
# Requires: curl, jq

REGISTRY_URL="${REGISTRY_URL:-http://localhost:5000}"
KEEP_VERSIONS="${KEEP_VERSIONS:-10}"
REPOSITORIES="${REPOSITORIES:-backend frontend asr-service tts-service voice-mcp}"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required"
  exit 1
fi

trim_repo() {
  local repo="$1"
  local tags_json tags_count

  tags_json=$(curl -fsS "${REGISTRY_URL}/v2/${repo}/tags/list" || true)
  if [[ -z "${tags_json}" || "${tags_json}" == "null" ]]; then
    echo "Skipping ${repo}: no tags found"
    return 0
  fi

  mapfile -t tags < <(echo "${tags_json}" | jq -r '.tags[]?' | sed '/^latest$/d' | sort -rV)
  tags_count="${#tags[@]}"

  if (( tags_count <= KEEP_VERSIONS )); then
    echo "${repo}: ${tags_count} tags (within limit ${KEEP_VERSIONS})"
    return 0
  fi

  echo "${repo}: pruning $((tags_count - KEEP_VERSIONS)) old tags"

  for tag in "${tags[@]:KEEP_VERSIONS}"; do
    digest=$(curl -fsSI \
      -H 'Accept: application/vnd.docker.distribution.manifest.v2+json' \
      "${REGISTRY_URL}/v2/${repo}/manifests/${tag}" \
      | awk -F': ' '/Docker-Content-Digest/ {print $2}' \
      | tr -d '\r')

    if [[ -n "${digest}" ]]; then
      curl -fsS -X DELETE "${REGISTRY_URL}/v2/${repo}/manifests/${digest}" >/dev/null
      echo "  deleted ${repo}:${tag}"
    fi
  done
}

for repo in ${REPOSITORIES}; do
  trim_repo "${repo}"
done

echo "Prune complete. Run registry garbage-collect during maintenance for full disk reclaim."
