#!/usr/bin/env bash
set -euo pipefail

# WARNING: DEPRECATED — DO NOT USE
# This script set up a self-hosted Docker registry on localhost:5000.
# As of the GHCR migration, all container images are stored in GitHub Container
# Registry (ghcr.io/nfornj). This script is kept only for historical reference.
#
# To clean up the old local registry container and its data on the runner host:
#   docker rm -f local-registry 2>/dev/null || true
#   sudo rm -rf "/media/neekrishrichu/One Touch/projects/zeroqwait"  # only if no other data
#   docker image prune -f
#
# Original script purpose: Local Docker registry with data on SSD path.

echo "ERROR: setup-local-registry.sh is DEPRECATED. Images are now stored in ghcr.io/nfornj." >&2
echo "       Log in to GHCR with: echo \$GITHUB_TOKEN | docker login ghcr.io -u <github_user> --password-stdin" >&2
exit 1

REGISTRY_CONFIG_PATH="${REGISTRY_CONFIG_PATH:-$(pwd)/deployment/registry/config.yml}"

mkdir -p "${REGISTRY_DATA_PATH}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required"
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${REGISTRY_NAME}$"; then
  echo "Removing existing ${REGISTRY_NAME} container to apply new config..."
  docker rm -f "${REGISTRY_NAME}" >/dev/null
fi

echo "Starting ${REGISTRY_NAME} on port ${REGISTRY_PORT}"
docker run -d \
  --name "${REGISTRY_NAME}" \
  --restart=always \
  -p "${REGISTRY_PORT}:5000" \
  -v "${REGISTRY_DATA_PATH}:/var/lib/registry" \
  -v "${REGISTRY_CONFIG_PATH}:/etc/docker/registry/config.yml:ro" \
  registry:2 >/dev/null

echo "Registry started: localhost:${REGISTRY_PORT}"
echo "Data path: ${REGISTRY_DATA_PATH}"
echo "Catalog URL: http://localhost:${REGISTRY_PORT}/v2/_catalog"
