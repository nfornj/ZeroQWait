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
    digest_headers=$(curl -sSI \
      -H 'Accept: application/vnd.docker.distribution.manifest.v2+json' \
      "${REGISTRY_URL}/v2/${repo}/manifests/${tag}" || true)

    digest=$(echo "${digest_headers}" \
      | awk -F': ' '/Docker-Content-Digest/ {print $2}' \
      | tr -d '\r')

    if [[ -z "${digest}" ]]; then
      echo "  skipped ${repo}:${tag} (manifest not found or no digest)"
      continue
    fi

    delete_code=$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE \
      "${REGISTRY_URL}/v2/${repo}/manifests/${digest}" || true)

    if [[ "${delete_code}" == "202" || "${delete_code}" == "200" ]]; then
      echo "  deleted ${repo}:${tag}"
    elif [[ "${delete_code}" == "404" ]]; then
      echo "  already absent ${repo}:${tag}"
    else
      echo "  failed deleting ${repo}:${tag} (HTTP ${delete_code})"
    fi
  done
}

for repo in ${REPOSITORIES}; do
  trim_repo "${repo}"
done

echo "==> Running registry garbage-collect to reclaim SSD storage"
if docker exec local-registry test -d /var/lib/registry/docker/registry/v2/repositories; then
  docker exec local-registry registry garbage-collect --delete-untagged /etc/docker/registry/config.yml || true
else
  echo "No repositories present yet; skipping garbage-collect"
fi
echo "Prune and garbage-collect complete."
