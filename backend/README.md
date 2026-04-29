# ZeroQwait Backend

FastAPI backend for the current ZeroQwait product.

This backend serves two AI interaction surfaces:

- Legacy customer-facing chat on the landing page and public flows
- Owner-facing v2 agent workspace powered by LangGraph

It also owns authentication, tenant-aware business data access, voice routing, approvals, and integration points such as MCP services and Odoo CRM.

## Runtime Overview

- Framework: FastAPI
- Python: 3.12
- ORM: SQLAlchemy 2.x
- Database: PostgreSQL 15
- Cache and transient state: Redis
- Owner agent orchestration: LangGraph + langchain-ollama
- Legacy customer agent path: `backend/agent_logic.py`
- Voice integration: Whisper ASR and Qwen3-TTS

## Backend Surfaces

### Legacy Customer Agent

- `POST /api/agent/master/chat`
- `POST /api/agent/master/chat/stream`

This path is still used for the landing-page receptionist experience during migration.

### Owner Agent v2

- `POST /api/v2/agent/chat`
- `POST /api/v2/agent/chat/stream`
- `POST /api/v2/agent/approve`
- `GET /api/v2/agent/history`
- `GET /api/v2/agent/pending`
- `GET /api/v2/agent/feed`

This path is the current owner operations experience. It uses a supervisor agent, specialist routing, approval checkpoints, and streamed UI events.

## Local Setup

The dependency source of truth is `pyproject.toml` and `uv.lock`.

### Preferred

```bash
uv sync --dev
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Notes

- The repo may also be run from an existing local virtualenv, but it should match the versions declared in `pyproject.toml`
- Local source-run frontend development should point to `http://localhost:8000/api`
- Local containerized runs use `backend/.env` plus service names from `docker-compose.yml`

## Local Dependencies

The backend expects these services for full-stack local operation:

- PostgreSQL
- Redis
- Booking MCP
- Finance MCP
- HR MCP
- Odoo

These are provided by the main root-level `docker-compose.yml`.

## Important Backend Directories

- `agents/`: LangGraph owner-agent stack
- `routers/`: API routes including `agent_v2.py` and voice routes
- `modules/`: auth, shops, employees, queues, and other domain modules
- `integrations/`: external service integration code such as Odoo and finance clients
- `tests/`: backend test suite

## API Docs

When the server is running:

- Swagger UI: `/docs`
- ReDoc: `/redoc`

## Documentation

- See `../README.md` for the repo-wide product and deployment story
- See `../claude.md` for detailed architecture and operational constraints
- See `../deployment/docs/README.md` for current deployment paths
