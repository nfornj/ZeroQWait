# ZeroQwait Complete Deployment & Operations Guide

This file consolidates the current deployment and operations story for the repo.

For the shortest authoritative version, see `deployment/docs/README.md`. This guide expands that into an operations-oriented reference.

## Current Deployment Story

ZeroQwait now has two primary deployment modes:

- non-production and local verification through a single Docker Compose stack named `zeroqwait`
- production through K3s in the `zeroqwait` namespace

The older queue-only and Pi-host-specific deployment story is no longer the active model.

## Canonical URLs

### Local And Non-Prod

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`

### K3s Ingress Test Host

- Base URL: `http://192.168.2.134.nip.io`

### Production

- Main site: `https://zeroqwait.com`
- Backend API: `https://zeroqwait.com/api`

## Main Deployment Paths

### Source-Run Local Development

Start the support services:

```bash
docker compose up -d db redis booking-mcp finance-mcp hr-mcp odoo
```

Run the backend:

```bash
cd backend
uv sync --dev
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Run the frontend:

```bash
cd frontend
REACT_APP_API_URL=http://localhost:8000/api npm start
```

### Full Non-Prod Deploy

```bash
bash deployment/scripts/deploy-test.sh
```

This is the authoritative Compose deployment path for test and non-`prod` branch validation.

### Production Deploy

```bash
bash deployment/scripts/deploy-prod.sh
```

Production is backed by K3s manifests under `k8s-manifests/` and is typically driven through the GitHub Actions workflow on the `prod` branch.

### Local Image Pipeline

```bash
bash deployment/scripts/run-local-pipeline.sh
```

Use this when you need versioned local images, registry retention, or manifest tag updates beyond the regular test deploy.

## Runtime Stack

### Core Services

- PostgreSQL 15
- Redis 7
- FastAPI backend
- React frontend
- Booking MCP
- Finance MCP
- HR MCP
- Odoo 17

### AI And Voice

- Ollama for the local LLM endpoint used by backend agents
- faster-whisper for ASR
- Qwen3-TTS for TTS on the approved voice path

## Health Checks

### Local / Non-Prod

```bash
curl -fsS http://localhost:8000/api/agent/health
curl -fsS http://localhost:8000/api/v2/agent/health
curl -fsS http://localhost:8000/api/voice/tts/health
```

### Production

```bash
curl -sk https://zeroqwait.com/api/agent/health
curl -sk https://zeroqwait.com/api/v2/agent/health
curl -sk https://zeroqwait.com/api/voice/tts/health
```

## Observability And Logs

### Compose

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
```

### K3s

```bash
kubectl get pods -n zeroqwait
kubectl logs -n zeroqwait deployment/backend
kubectl logs -n zeroqwait deployment/frontend
```

## Environment Sources

Current configuration should come from:

- `backend/.env` for local source-run work
- root `docker-compose.yml` for the Compose stack
- `k8s-manifests/` for production configuration

Common runtime values include:

- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `REDIS_HOST`, `REDIS_PORT`
- `OLLAMA_URL`, `MODEL_NAME`
- `TTS_SERVICE_URL`
- `BOOKING_MCP_URL`, `FINANCE_MCP_URL`, `HR_MCP_URL`
- `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, `ODOO_PASSWORD`
- `FRONTEND_URL`

## Common Operations

### Rebuild The Non-Prod Stack

```bash
bash deployment/scripts/deploy-test.sh
```

### Inspect Changed Deployment Files

```bash
git diff -- deployment/scripts k8s-manifests docker-compose.yml
```

### Validate Backend Tests

```bash
cd backend
uv run pytest -q
```

## Troubleshooting

### Backend is up but frontend requests fail

- verify `REACT_APP_API_URL`
- verify backend is reachable on `http://localhost:8000`
- verify nginx or ingress is proxying `/api` correctly in containerized mode

### Compose deploy succeeded but services are unhealthy

- inspect `docker compose logs`
- verify the stack name remains `zeroqwait`
- verify PostgreSQL and Redis are healthy before backend startup

### Production rollout is unhealthy

- inspect pod rollout status and logs in `zeroqwait`
- verify K8s secrets and config maps match current runtime values
- verify ingress and service connectivity for backend and frontend

## What To Avoid Documenting As Current

The following should be treated as historical unless explicitly reintroduced:

- legacy cloud-database setup guides that predate the current PostgreSQL deployment model
- older single-host production assumptions that predate the current K3s model
- queue-only product positioning in deployment docs
- older `192.168.2.88.nip.io` examples

## Related Docs

- `README.md`
- `deployment/docs/README.md`
- `GITHUB_DEPLOYMENT_SETUP.md`
- `claude.md`
