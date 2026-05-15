# Environment Setup

This document describes the active environment model for ZeroQwait.

## Current Environment Sources

### Backend

Primary local source of truth:

- `backend/.env`

Primary configuration groups:

- database connection
- Redis connection
- Ollama and model selection
- TTS service URL
- MCP service URLs
- Odoo connection settings
- frontend origin

### Frontend

Primary runtime setting:

- `REACT_APP_API_URL`

Common values:

- source-run local frontend: `http://localhost:8000/api`
- containerized frontend behind nginx: `/api`

## Recommended Local Setup

### Backend `.env`

Use values that match the root `docker-compose.yml` and your local runtime:

```env
DB_HOST=localhost
DB_PORT=5433
DB_NAME=zeroqwait
DB_USER=postgres
DB_PASSWORD=zeroqwait_dev
REDIS_HOST=localhost
REDIS_PORT=6379
OLLAMA_URL=http://192.168.2.134:30002/v1
MODEL_NAME=qwen3:14b-q4_K_M
TTS_SERVICE_URL=http://192.168.2.134:30880
BOOKING_MCP_URL=http://localhost:8890
FINANCE_MCP_URL=http://localhost:8891
HR_MCP_URL=http://localhost:8892
ODOO_URL=http://localhost:8069
ODOO_DB=odoo
ODOO_USER=admin
ODOO_PASSWORD=admin
FRONTEND_URL=http://localhost:3000
```

> **Port 5433, not 5432.** The Docker Compose postgres is exposed on host port 5433 to avoid colliding with any local Homebrew or system postgres that already owns port 5432. If nothing else is running on 5432 you can change `DB_HOST_PORT` in `docker-compose.yml` and `DB_PORT` in `backend/.env` to 5432, but 5433 is the safe default.

### Source-Run Workflow

Support services:

```bash
docker compose up -d db redis booking-mcp finance-mcp hr-mcp odoo
```

First-time database setup (only needed once, or after recreating the `db` container):

```bash
# Enable pgvector extension — required for the conversation_history.embedding column
docker exec zeroqwait-db-1 psql -U postgres -d zeroqwait -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Create all app tables
cd backend
PYTHONPATH=. .venv/bin/python scripts/init_database.py
```

Backend:

```bash
cd backend
uv sync --dev
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm start
```

> **Do not set `REACT_APP_API_URL` in `.env.local` to an absolute URL (e.g. `http://localhost:8000/api`) if you are running the frontend inside Docker.** The containerised nginx already proxies `/api` to the backend; an absolute URL bypasses nginx and causes CORS errors. Use the relative `/api` value for Docker and the absolute URL only when running `npm start` directly against a local backend.

### Full Test Deployment

Use the repo’s authoritative non-prod flow when you want the full Docker Compose stack:

```bash
bash deployment/scripts/deploy-test.sh
```

That publishes:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

## Production Configuration Model

Production configuration comes from:

- K8s manifests under `k8s-manifests/`
- backend environment variables injected through deployment config
- frontend container config and nginx proxying

This project uses Compose for local and non-prod flows and K3s for production.

## Frontend API Routing Rules

### Source-Run Frontend (`npm start`)

Use:

```env
REACT_APP_API_URL=http://localhost:8000/api
```

This is required because `npm start` does not run nginx — requests must go directly to the backend. Auth and owner-agent routes are mounted under `/api`.

### Containerized Frontend

Use:

```env
REACT_APP_API_URL=/api
```

The containerized frontend expects nginx or ingress to proxy `/api` to the backend.

## Troubleshooting

### Login or API calls fail from the frontend

- Verify `REACT_APP_API_URL` — use `/api` for containerised nginx, `http://localhost:8000/api` for bare `npm start`.
- Verify the backend is listening on `http://localhost:8000`.
- Verify the frontend is on `http://localhost:3000`.
- If the browser reports a CORS error but CORS config looks correct, check that the backend is actually returning a 2xx, not a 5xx. FastAPI strips CORS headers from 500 responses — a backend crash will look like a CORS failure in the browser.

### Registration or signup fails with "Registration failed. Please try again."

- Confirm the `db` container is running: `docker compose ps db`
- Confirm the `vector` extension is enabled: `docker exec zeroqwait-db-1 psql -U postgres -d zeroqwait -c "SELECT extname FROM pg_extension WHERE extname='vector';"`
- Confirm app tables exist: `docker exec zeroqwait-db-1 psql -U postgres -d zeroqwait -c "\dt"` — you should see `users`, `shops`, `queues`, etc.
- If tables are missing, run `PYTHONPATH=. .venv/bin/python scripts/init_database.py` from `backend/`.

### Backend starts but cannot reach dependencies

- Check `backend/.env` — confirm `DB_PORT=5433` (not 5432) for source-run mode.
- Confirm `db`, `redis`, MCP services, and `odoo` are up: `docker compose ps`.
- Confirm `OLLAMA_URL` and `TTS_SERVICE_URL` point at reachable services.

### Docs show unexpected variables

Validate them against `README.md`, `deployment/docs/README.md`, and `claude.md`.

## Security Notes

- never commit real secrets
- keep `backend/.env` local or managed through deployment secrets
- keep frontend environment values limited to public-safe configuration such as API base URL
