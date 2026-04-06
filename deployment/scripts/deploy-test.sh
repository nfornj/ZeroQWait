#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
BACKEND_ENV_FILE="${PROJECT_ROOT}/backend/.env"
CI_OVERRIDE_FILE="$(mktemp)"

echo "==> Test deploy (non-prod branch)"
echo "==> Project root: ${PROJECT_ROOT}"

cleanup() {
	rm -f "${CI_OVERRIDE_FILE}" || true
}
trap cleanup EXIT

cd "${PROJECT_ROOT}"

LOCAL_UID="$(id -u)"
LOCAL_GID="$(id -g)"
BACKEND_HOST_PORT="${BACKEND_HOST_PORT:-0}"
FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT:-0}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
# Use ephemeral host port for TTS during test deploy to avoid collisions.
TTS_HOST_PORT="${TTS_HOST_PORT:-0}"

# Actions checkout on self-hosted runners may not include backend/.env
# because it is typically gitignored. Create a local CI-safe file when absent.
if [[ ! -f "${BACKEND_ENV_FILE}" ]]; then
	echo "==> backend/.env missing, generating CI-safe local defaults"
	cat > "${BACKEND_ENV_FILE}" << 'EOF'
SECRET_KEY=ci_test_secret_key_change_in_prod
DB_HOST=db
DB_PORT=5432
DB_NAME=zeroqwait
DB_USER=postgres
DB_PASSWORD=zeroqwait_dev
REDIS_HOST=redis
REDIS_PORT=6379
FRONTEND_URL=http://localhost:3000
EOF
fi

# Remove stale runner workspace virtualenv if previous runs left root-owned files.
if [[ -d "${PROJECT_ROOT}/backend/.venv" ]]; then
	echo "==> Removing stale backend/.venv before compose run"
	sudo rm -rf "${PROJECT_ROOT}/backend/.venv" || true
fi

# CI override: run backend from image-built environment, not bind-mounted source.
# This avoids runtime dependency installation during readiness checks.
cat > "${CI_OVERRIDE_FILE}" << 'EOF'
services:
  backend:
    volumes: []
    command:
      - /app/.venv/bin/uvicorn
      - main:app
      - --host
      - 0.0.0.0
      - --port
      - '8000'
EOF

COMPOSE_ARGS=(-f "${COMPOSE_FILE}" -f "${CI_OVERRIDE_FILE}")

# Build and run test stack locally with non-conflicting host ports.
sudo --preserve-env=LOCAL_UID,LOCAL_GID,BACKEND_HOST_PORT,FRONTEND_HOST_PORT,FRONTEND_URL,TTS_HOST_PORT env \
	LOCAL_UID="${LOCAL_UID}" \
	LOCAL_GID="${LOCAL_GID}" \
	BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" \
	FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" \
	FRONTEND_URL="${FRONTEND_URL}" \
	TTS_HOST_PORT="${TTS_HOST_PORT}" \
	docker compose "${COMPOSE_ARGS[@]}" up -d --build

resolve_published_port() {
	local service="$1"
	local target_port="$2"
	local timeout_seconds="${3:-60}"
	local elapsed=0
	local resolved=""

	while (( elapsed < timeout_seconds )); do
		resolved="$(sudo env BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" TTS_HOST_PORT="${TTS_HOST_PORT}" docker compose "${COMPOSE_ARGS[@]}" port "${service}" "${target_port}" 2>/dev/null | awk -F: 'NF {print $NF}' | tail -n1 || true)"
		if [[ -n "${resolved}" ]]; then
			echo "${resolved}"
			return 0
		fi
		sleep 2
		elapsed=$((elapsed + 2))
	done

	return 1
}

FRONTEND_PUBLISHED_PORT="$(resolve_published_port frontend 80 60 || true)"
BACKEND_PUBLISHED_PORT="$(resolve_published_port backend 8000 60 || true)"

if [[ -z "${FRONTEND_PUBLISHED_PORT}" || -z "${BACKEND_PUBLISHED_PORT}" ]]; then
	echo "!! Failed to resolve published ports from docker compose"
	sudo env BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" TTS_HOST_PORT="${TTS_HOST_PORT}" docker compose "${COMPOSE_ARGS[@]}" ps || true
	exit 1
fi

echo "==> Waiting for services to become ready"

wait_for_http() {
	local name="$1"
	local url="$2"
	local timeout_seconds="${3:-120}"
	local elapsed=0

	until curl -fsS "$url" >/dev/null; do
		sleep 2
		elapsed=$((elapsed + 2))
		if (( elapsed >= timeout_seconds )); then
			echo "!! ${name} did not become ready within ${timeout_seconds}s: ${url}"
			return 1
		fi
	done
}

echo "==> Smoke checks"
if ! wait_for_http "frontend" "http://localhost:${FRONTEND_PUBLISHED_PORT}" 120; then
	echo "==> docker compose ps"
	sudo env BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" TTS_HOST_PORT="${TTS_HOST_PORT}" docker compose "${COMPOSE_ARGS[@]}" ps || true
	echo "==> frontend logs (tail)"
	sudo env BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" TTS_HOST_PORT="${TTS_HOST_PORT}" docker compose "${COMPOSE_ARGS[@]}" logs --tail=120 frontend || true
	exit 1
fi

if ! wait_for_http "backend" "http://localhost:${BACKEND_PUBLISHED_PORT}" 180; then
	echo "==> docker compose ps"
	sudo env BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" TTS_HOST_PORT="${TTS_HOST_PORT}" docker compose "${COMPOSE_ARGS[@]}" ps || true
	echo "==> backend logs (tail)"
	sudo env BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" TTS_HOST_PORT="${TTS_HOST_PORT}" docker compose "${COMPOSE_ARGS[@]}" logs --tail=200 backend || true
	exit 1
fi

echo "==> Test deployment successful"
echo "    Frontend: http://localhost:${FRONTEND_PUBLISHED_PORT}"
echo "    Backend : http://localhost:${BACKEND_PUBLISHED_PORT}"

# Some container steps can leave root-owned files in the checkout workspace
# (for example backend/.venv). Restore ownership so actions/checkout can clean
# the repo on the next run.
echo "==> Restoring workspace ownership for runner user"
sudo chown -R "$(id -u):$(id -g)" "${PROJECT_ROOT}"
