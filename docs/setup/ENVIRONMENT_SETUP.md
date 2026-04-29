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
DB_HOST=db
DB_PORT=5432
DB_NAME=zeroqwait
DB_USER=postgres
DB_PASSWORD=zeroqwait_dev
REDIS_HOST=redis
REDIS_PORT=6379
OLLAMA_URL=http://192.168.2.134:30002/v1
MODEL_NAME=qwen3:14b-q4_K_M
TTS_SERVICE_URL=http://192.168.2.134:30880
BOOKING_MCP_URL=http://booking-mcp:8890
FINANCE_MCP_URL=http://finance-mcp:8891
HR_MCP_URL=http://hr-mcp:8892
ODOO_URL=http://odoo:8069
ODOO_DB=odoo
ODOO_USER=admin
ODOO_PASSWORD=admin
FRONTEND_URL=http://localhost:3000
```

### Source-Run Workflow

Support services:

```bash
docker compose up -d db redis booking-mcp finance-mcp hr-mcp odoo
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
REACT_APP_API_URL=http://localhost:8000/api npm start
```

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

### Source-Run Frontend

Use:

```env
REACT_APP_API_URL=http://localhost:8000/api
```

This is required because auth and owner-agent routes are mounted under `/api`.

### Containerized Frontend

Use:

```env
REACT_APP_API_URL=/api
```

The containerized frontend expects nginx or ingress to proxy `/api` to the backend.

## Troubleshooting

### Login or API calls fail from the frontend

- verify `REACT_APP_API_URL`
- verify backend is listening on `http://localhost:8000`
- verify frontend is on `http://localhost:3000`

### Backend starts but cannot reach dependencies

- check `backend/.env`
- confirm `db`, `redis`, MCP services, and `odoo` are up
- confirm `OLLAMA_URL` and `TTS_SERVICE_URL` point at reachable services

### Docs show unexpected variables

Validate them against `README.md`, `deployment/docs/README.md`, and `claude.md`.

## Security Notes

- never commit real secrets
- keep `backend/.env` local or managed through deployment secrets
- keep frontend environment values limited to public-safe configuration such as API base URL
