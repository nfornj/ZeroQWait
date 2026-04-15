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

ensure_docker_daemon() {
	if sudo systemctl is-active --quiet docker; then
		echo "==> Docker daemon is active"
	else
		echo "==> Docker daemon is inactive; starting docker service"
		sudo systemctl start docker
	fi

	if [[ ! -S /var/run/docker.sock ]]; then
		echo "!! Docker socket missing at /var/run/docker.sock after daemon start"
		exit 1
	fi

	if ! sudo docker info >/dev/null 2>&1; then
		echo "!! Docker daemon is not reachable after startup"
		exit 1
	fi
}

ensure_docker_daemon

LOCAL_UID="$(id -u)"
LOCAL_GID="$(id -g)"
# Limit compose parallelism on heavy hosts to reduce peak RAM during build/start.
COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}"
export COMPOSE_PARALLEL_LIMIT
DB_HOST_PORT="${DB_HOST_PORT:-0}"
# Keep frontend endpoint stable so users hit the latest deployed stack when possible.
BACKEND_HOST_PORT="${BACKEND_HOST_PORT:-0}"
FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT:-3000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
# Shared K8s endpoints: one LLM + one TTS for both test/prod workloads.
K8S_NODE_IP="${K8S_NODE_IP:-192.168.2.134}"
SHARED_OLLAMA_URL="${SHARED_OLLAMA_URL:-http://${K8S_NODE_IP}:30002/v1}"
SHARED_MODEL_NAME="${SHARED_MODEL_NAME:-gpt-oss:20b}"
SHARED_TTS_URL="${SHARED_TTS_URL:-http://${K8S_NODE_IP}:30880}"
# Fixed project name so every run replaces the previous test stack
# instead of spawning a new isolated set of containers per run.
COMPOSE_PROJECT_NAME="zeroqwait-test"
export COMPOSE_PROJECT_NAME

# If requested host ports are busy, fall back to ephemeral ports to avoid hard failures.
if [[ "${FRONTEND_HOST_PORT}" != "0" ]] && ss -ltn "( sport = :${FRONTEND_HOST_PORT} )" | tail -n +2 | grep -q .; then
	echo "==> FRONTEND_HOST_PORT ${FRONTEND_HOST_PORT} is busy; falling back to an ephemeral port"
	FRONTEND_HOST_PORT="0"
fi

if [[ "${BACKEND_HOST_PORT}" != "0" ]] && ss -ltn "( sport = :${BACKEND_HOST_PORT} )" | tail -n +2 | grep -q .; then
	echo "==> BACKEND_HOST_PORT ${BACKEND_HOST_PORT} is busy; falling back to an ephemeral port"
	BACKEND_HOST_PORT="0"
fi

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
OLLAMA_URL=http://192.168.2.134:30002/v1
MODEL_NAME=gpt-oss:20b
TTS_SERVICE_URL=http://192.168.2.134:30880
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
cat > "${CI_OVERRIDE_FILE}" <<'EOF'
services:
  backend:
    volumes: []
    environment:
      - OLLAMA_URL=${SHARED_OLLAMA_URL}
      - MODEL_NAME=${SHARED_MODEL_NAME}
      - TTS_SERVICE_URL=${SHARED_TTS_URL}
    command: /opt/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
EOF

COMPOSE_ARGS=(-p "${COMPOSE_PROJECT_NAME}" -f "${COMPOSE_FILE}" -f "${CI_OVERRIDE_FILE}")

# Tear down any previous test stack (same project name) before starting fresh.
# This is what prevents stale containers from accumulating across runs.
echo "==> Tearing down previous test stack (if any)"
sudo --preserve-env=LOCAL_UID,LOCAL_GID,DB_HOST_PORT,BACKEND_HOST_PORT,FRONTEND_HOST_PORT,FRONTEND_URL,SHARED_OLLAMA_URL,SHARED_MODEL_NAME,SHARED_TTS_URL,COMPOSE_PROJECT_NAME,COMPOSE_PARALLEL_LIMIT env \
	LOCAL_UID="${LOCAL_UID}" \
	LOCAL_GID="${LOCAL_GID}" \
	DB_HOST_PORT="${DB_HOST_PORT}" \
	SHARED_OLLAMA_URL="${SHARED_OLLAMA_URL}" \
	SHARED_MODEL_NAME="${SHARED_MODEL_NAME}" \
	SHARED_TTS_URL="${SHARED_TTS_URL}" \
	COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT}" \
	COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME}" \
	docker compose "${COMPOSE_ARGS[@]}" down --remove-orphans --timeout 30 || true

# Cleanup legacy compose TTS containers from older project names to prevent GPU contention.
for legacy_project in zeroqwait zeroqwait-test; do
	legacy_tts_id="$(sudo docker ps -aq --filter "label=com.docker.compose.project=${legacy_project}" --filter "label=com.docker.compose.service=tts" || true)"
	if [[ -n "${legacy_tts_id}" ]]; then
		echo "==> Removing legacy Docker TTS container(s) for project: ${legacy_project}"
		sudo docker rm -f ${legacy_tts_id} >/dev/null || true
	fi
done

# Build and run test stack locally with non-conflicting host ports.
sudo --preserve-env=LOCAL_UID,LOCAL_GID,DB_HOST_PORT,BACKEND_HOST_PORT,FRONTEND_HOST_PORT,FRONTEND_URL,SHARED_OLLAMA_URL,SHARED_MODEL_NAME,SHARED_TTS_URL,COMPOSE_PROJECT_NAME,COMPOSE_PARALLEL_LIMIT env \
	LOCAL_UID="${LOCAL_UID}" \
	LOCAL_GID="${LOCAL_GID}" \
	DB_HOST_PORT="${DB_HOST_PORT}" \
	BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" \
	FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" \
	FRONTEND_URL="${FRONTEND_URL}" \
	SHARED_OLLAMA_URL="${SHARED_OLLAMA_URL}" \
	SHARED_MODEL_NAME="${SHARED_MODEL_NAME}" \
	SHARED_TTS_URL="${SHARED_TTS_URL}" \
	COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT}" \
	COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME}" \
	docker compose "${COMPOSE_ARGS[@]}" up -d --build

echo "==> Initializing database schema and seed data"
sudo env DB_HOST_PORT="${DB_HOST_PORT}" BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" SHARED_OLLAMA_URL="${SHARED_OLLAMA_URL}" SHARED_MODEL_NAME="${SHARED_MODEL_NAME}" SHARED_TTS_URL="${SHARED_TTS_URL}" COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME}" COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT}" \
	docker compose "${COMPOSE_ARGS[@]}" exec -T backend /opt/venv/bin/python init_database.py

sudo env DB_HOST_PORT="${DB_HOST_PORT}" BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" SHARED_OLLAMA_URL="${SHARED_OLLAMA_URL}" SHARED_MODEL_NAME="${SHARED_MODEL_NAME}" SHARED_TTS_URL="${SHARED_TTS_URL}" COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME}" COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT}" \
	docker compose "${COMPOSE_ARGS[@]}" exec -T backend /opt/venv/bin/python seed_data.py

echo "==> Ensuring compatibility test login account"
sudo env DB_HOST_PORT="${DB_HOST_PORT}" BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" SHARED_OLLAMA_URL="${SHARED_OLLAMA_URL}" SHARED_MODEL_NAME="${SHARED_MODEL_NAME}" SHARED_TTS_URL="${SHARED_TTS_URL}" COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME}" COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT}" \
	docker compose "${COMPOSE_ARGS[@]}" exec -T backend /opt/venv/bin/python - <<'PY'
from passlib.context import CryptContext
from database import SessionLocal
from models import User, UserRole, SubscriptionTier, Shop

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
username = "test_bulk_owner_0_3504"
email = "test_bulk_owner_0_3504@zeroqwait.com"
password = "password123"

db = SessionLocal()
try:
	user = db.query(User).filter(User.username == username).first()
	if not user:
		user = User(
			email=email,
			username=username,
			hashed_password=pwd.hash(password),
			role=UserRole.SHOP_OWNER,
			is_active=True,
			subscription_tier=SubscriptionTier.PREMIUM,
		)
		db.add(user)
		db.flush()

	shop = db.query(Shop).filter(Shop.owner_id == user.id).first()
	if not shop:
		db.add(Shop(
			owner_id=user.id,
			name="Bulk Owner Test Shop",
			shop_type="barber",
			address="100 Test Street",
			city="Toronto",
			state="ON",
			zip_code="M5V1A1",
			country="Canada",
			phone="555-010-0350",
			slug="bulk-owner-test-shop-3504",
			latitude=43.6532,
			longitude=-79.3832,
			average_service_time=30,
		))

	db.commit()
	print("Compatibility login account ensured")
finally:
	db.close()
PY

resolve_published_port() {
	local service="$1"
	local target_port="$2"
	local timeout_seconds="${3:-60}"
	local elapsed=0
	local resolved=""

	while (( elapsed < timeout_seconds )); do
		resolved="$(sudo env DB_HOST_PORT="${DB_HOST_PORT}" BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" SHARED_OLLAMA_URL="${SHARED_OLLAMA_URL}" SHARED_MODEL_NAME="${SHARED_MODEL_NAME}" SHARED_TTS_URL="${SHARED_TTS_URL}" COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME}" COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT}" docker compose "${COMPOSE_ARGS[@]}" port "${service}" "${target_port}" 2>/dev/null | awk -F: 'NF {print $NF}' | tail -n1 || true)"
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
	sudo env DB_HOST_PORT="${DB_HOST_PORT}" BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" SHARED_OLLAMA_URL="${SHARED_OLLAMA_URL}" SHARED_MODEL_NAME="${SHARED_MODEL_NAME}" SHARED_TTS_URL="${SHARED_TTS_URL}" COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT}" docker compose "${COMPOSE_ARGS[@]}" ps || true
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
	sudo env DB_HOST_PORT="${DB_HOST_PORT}" BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" SHARED_OLLAMA_URL="${SHARED_OLLAMA_URL}" SHARED_MODEL_NAME="${SHARED_MODEL_NAME}" SHARED_TTS_URL="${SHARED_TTS_URL}" COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME}" COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT}" docker compose "${COMPOSE_ARGS[@]}" ps || true
	echo "==> frontend logs (tail)"
	sudo env DB_HOST_PORT="${DB_HOST_PORT}" BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" SHARED_OLLAMA_URL="${SHARED_OLLAMA_URL}" SHARED_MODEL_NAME="${SHARED_MODEL_NAME}" SHARED_TTS_URL="${SHARED_TTS_URL}" COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME}" COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT}" docker compose "${COMPOSE_ARGS[@]}" logs --tail=120 frontend || true
	exit 1
fi

if ! wait_for_http "backend" "http://localhost:${BACKEND_PUBLISHED_PORT}" 360; then
	echo "==> docker compose ps"
	sudo env DB_HOST_PORT="${DB_HOST_PORT}" BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" SHARED_OLLAMA_URL="${SHARED_OLLAMA_URL}" SHARED_MODEL_NAME="${SHARED_MODEL_NAME}" SHARED_TTS_URL="${SHARED_TTS_URL}" COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME}" COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT}" docker compose "${COMPOSE_ARGS[@]}" ps || true
	echo "==> backend logs (tail)"
	sudo env DB_HOST_PORT="${DB_HOST_PORT}" BACKEND_HOST_PORT="${BACKEND_HOST_PORT}" FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT}" SHARED_OLLAMA_URL="${SHARED_OLLAMA_URL}" SHARED_MODEL_NAME="${SHARED_MODEL_NAME}" SHARED_TTS_URL="${SHARED_TTS_URL}" COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME}" COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT}" docker compose "${COMPOSE_ARGS[@]}" logs --tail=200 backend || true
	exit 1
fi

echo "==> Test deployment successful"
echo "    Frontend: http://localhost:${FRONTEND_PUBLISHED_PORT}"
echo "    Backend : http://localhost:${BACKEND_PUBLISHED_PORT}"

ARCHIVE_SERVICES="${TEST_ARCHIVE_SERVICES:-backend,frontend}"
echo "==> Archiving test images to local registry (retain last 3 tags)"
echo "==> Archive services: ${ARCHIVE_SERVICES}"
sudo env \
	SKIP_TESTS="true" \
	IMAGE_NAMESPACE="test" \
	RETAIN_VERSIONS="3" \
	SKIP_REGISTRY_PRUNE="false" \
	SERVICES="${ARCHIVE_SERVICES}" \
	AUTO_COMMIT="false" \
	ARGOCD_SYNC="false" \
	bash "${PROJECT_ROOT}/deployment/scripts/run-local-pipeline.sh"

# Some container steps can leave root-owned files in the checkout workspace
# (for example backend/.venv). Restore ownership so actions/checkout can clean
# the repo on the next run.
echo "==> Restoring workspace ownership for runner user"
sudo chown -R "$(id -u):$(id -g)" "${PROJECT_ROOT}"
