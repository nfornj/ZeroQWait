# Environment Setup

This document describes the active environment model for ZeroQwait and the configuration surfaces that matter when you run the system locally or in non-prod.

## Runtime Model

ZeroQwait currently operates in two primary runtime modes:

- local and non-prod: single Docker Compose stack published at `http://localhost:3000` and `http://localhost:8000`
- production: K3s workloads behind `https://zeroqwait.com`

The local and non-prod model is intentionally simple. It is the fastest way to validate product behavior without reproducing the full production topology on a laptop or workstation.

## Configuration Sources

### Backend

Primary configuration surfaces:

- `backend/.env` for source-run development
- root `docker-compose.yml` for containerized local execution
- `k8s-manifests/` for production runtime configuration

Main backend configuration groups:

- database and Redis connectivity
- LLM provider configuration
- voice service endpoints
- MCP service endpoints
- Odoo integration
- Temporal configuration
- Telegram and notification settings
- frontend origin and auth-related runtime values

### Frontend

Primary runtime surface:

- `REACT_APP_API_URL`

Expected values:

- source-run frontend: `http://localhost:8000/api`
- containerized frontend behind nginx: `/api`

## Current Local Defaults

These are the current default local ports exposed by the active `docker-compose.yml`:

| Service | Default |
| --- | --- |
| Frontend | `http://localhost:3000` |
| Backend | `http://localhost:8000` |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |
| Temporal | `localhost:7233` when the Temporal profile is enabled |

If your machine already uses one of these ports, override the corresponding host port variable in your shell or `.env` before running Compose.

## Provider Strategy

The platform supports a provider strategy rather than a single hardcoded inference path.

### LLM

- primary production provider: NVIDIA NIM using `meta/llama-3.1-8b-instruct`
- fallback and local compatibility path: Ollama using `qwen3:14b-q4_K_M` when NVIDIA is not configured

Relevant variables:

```env
LLM_PROVIDER=nvidia
NVIDIA_API_KEY=
NVIDIA_MODEL=meta/llama-3.1-8b-instruct
OLLAMA_URL=http://192.168.2.134:30002
MODEL_NAME=qwen3:14b-q4_K_M
```

### Voice

- ASR: Whisper service
- TTS: Qwen3-TTS with voice `Vivian`

Relevant variable:

```env
TTS_SERVICE_URL=http://192.168.2.134:30880
```

The voice stack is intentionally externalized so the backend can remain focused on API, orchestration, and agent execution.

## Recommended Source-Run Backend Environment

Use values that match your local runtime and available services:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=zeroqwait
DB_USER=postgres
DB_PASSWORD=zeroqwait_dev
REDIS_HOST=localhost
REDIS_PORT=6379
LLM_PROVIDER=nvidia
NVIDIA_API_KEY=
NVIDIA_MODEL=meta/llama-3.1-8b-instruct
OLLAMA_URL=http://192.168.2.134:30002
MODEL_NAME=qwen3:14b-q4_K_M
TTS_SERVICE_URL=http://192.168.2.134:30880
BOOKING_MCP_URL=http://localhost:8890
FINANCE_MCP_URL=http://localhost:8891
HR_MCP_URL=http://localhost:8892
ODOO_MCP_URL=http://localhost:8893
POSTGRES_MCP_URL=http://localhost:8894
ODOO_URL=http://localhost:8069
ODOO_DB=odoo
ODOO_USER=admin
ODOO_PASSWORD=admin
TEMPORAL_ENABLED=false
TEMPORAL_ADDRESS=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=zeroqwait-agent-brain
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
FRONTEND_URL=http://localhost:3000
```

## Local Execution Paths

### Fastest Full Stack Path

Use the authoritative test deployment script:

```bash
bash deployment/scripts/deploy-test.sh
```

This gives you the canonical local URLs:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`

### Source-Run Path

Start support services first:

```bash
docker compose up -d db redis booking-mcp finance-mcp hr-mcp odoo-mcp postgres-mcp odoo
```

If you need Temporal-backed workflows locally, enable the Temporal profile as well:

```bash
docker compose --profile temporal up -d temporal temporal-worker
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

## Frontend API Routing Rules

### Source-Run Frontend

Use:

```env
REACT_APP_API_URL=http://localhost:8000/api
```

`npm start` does not use nginx, so requests must go directly to the backend.

### Containerized Frontend

Use:

```env
REACT_APP_API_URL=/api
```

The containerized frontend expects nginx or ingress to proxy `/api` to the backend.

Do not point the containerized frontend at an absolute backend URL unless you are intentionally bypassing the proxy path.

## Production Configuration Model

Production configuration comes from:

- Kubernetes manifests under `k8s-manifests/`
- deployment-managed environment variables and secrets
- frontend nginx proxying and ingress rules

Production runs on K3s with Traefik and is published at `https://zeroqwait.com`.

## Troubleshooting

### Login or API calls fail from the frontend

- verify `REACT_APP_API_URL`
- verify the backend is listening on `http://localhost:8000`
- verify the frontend is on `http://localhost:3000`
- if the browser reports a CORS error, confirm the backend is not actually returning a 500; FastAPI strips CORS headers from many server-side failures

### Backend starts but cannot reach dependencies

- confirm `db`, `redis`, MCP services, and `odoo` are running with `docker compose ps`
- confirm `backend/.env` matches the ports you actually published
- confirm `TTS_SERVICE_URL`, `OLLAMA_URL`, and provider credentials point at reachable services

### Temporal features are missing locally

- verify you enabled the `temporal` Compose profile
- verify `TEMPORAL_ENABLED=true` when you expect agent-brain workflows to run through Temporal

### Telegram integration does not activate

- confirm `TELEGRAM_BOT_TOKEN` is present
- confirm webhook or polling mode matches your local setup

### SMS delivery does not arrive

- confirm AWS credentials are configured
- confirm the SNS account is not blocked by sandbox restrictions or spend-limit settings

## Security Notes

- never commit real credentials or API keys
- keep `backend/.env` local or managed through deployment secrets
- keep frontend environment variables limited to public-safe values such as API base URLs
- validate production runtime settings against `k8s-manifests/` and deployment secrets rather than copying local defaults into cluster config
