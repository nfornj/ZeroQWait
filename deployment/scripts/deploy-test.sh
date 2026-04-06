#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
BACKEND_ENV_FILE="${PROJECT_ROOT}/backend/.env"

echo "==> Test deploy (non-prod branch)"
echo "==> Project root: ${PROJECT_ROOT}"

cd "${PROJECT_ROOT}"

LOCAL_UID="$(id -u)"
LOCAL_GID="$(id -g)"
TTS_HOST_PORT="${TTS_HOST_PORT:-18880}"

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

# Build and run test stack locally. Frontend is exposed at localhost:3000.
sudo --preserve-env=LOCAL_UID,LOCAL_GID,TTS_HOST_PORT env \
	LOCAL_UID="${LOCAL_UID}" \
	LOCAL_GID="${LOCAL_GID}" \
	TTS_HOST_PORT="${TTS_HOST_PORT}" \
	docker compose -f "${COMPOSE_FILE}" up -d --build

echo "==> Waiting for services to become ready"
sleep 8

echo "==> Smoke checks"
curl -fsS "http://localhost:3000" >/dev/null
curl -fsS "http://localhost:8000" >/dev/null

echo "==> Test deployment successful"
echo "    Frontend: http://localhost:3000"
echo "    Backend : http://localhost:8000"

# Some container steps can leave root-owned files in the checkout workspace
# (for example backend/.venv). Restore ownership so actions/checkout can clean
# the repo on the next run.
echo "==> Restoring workspace ownership for runner user"
sudo chown -R "$(id -u):$(id -g)" "${PROJECT_ROOT}"
