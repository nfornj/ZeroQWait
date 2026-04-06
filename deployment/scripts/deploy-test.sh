#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"

echo "==> Test deploy (non-prod branch)"
echo "==> Project root: ${PROJECT_ROOT}"

cd "${PROJECT_ROOT}"

# Build and run test stack locally. Frontend is exposed at localhost:3000.
sudo docker compose -f "${COMPOSE_FILE}" up -d --build

echo "==> Waiting for services to become ready"
sleep 8

echo "==> Smoke checks"
curl -fsS "http://localhost:3000" >/dev/null
curl -fsS "http://localhost:8000" >/dev/null

echo "==> Test deployment successful"
echo "    Frontend: http://localhost:3000"
echo "    Backend : http://localhost:8000"
