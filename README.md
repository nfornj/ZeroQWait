# ZeroQwait

ZeroQwait is an AI operations system for service businesses. The product is aimed at barbershops, salons, clinics, and similar appointment or queue-based businesses that need an AI receptionist for customers and a supervised AI operations workspace for owners.

The current product direction is not a generic queue SaaS. It is a vertical Agent-as-a-Service product built around a shop-specific supervisor agent, specialist agents, approval-gated actions, and real business workflows.

Live production URL: https://zeroqwait.com

## Product Shape

ZeroQwait currently has two primary experiences:

- Customer-facing receptionist experience
   Customer chat, queue help, service discovery, and voice interactions on the landing page and public shop surfaces.
- Owner-facing operations workspace
   A supervisor agent for queue, finance, HR, and CRM workflows with streamed chat, charts, files, approvals, and feed-style operational updates.

The customer-facing chat is still served by the legacy `pydantic-ai` path during migration. The owner-facing workspace is served by the LangGraph-based v2 agent stack.

## Core Capabilities

- AI receptionist for shop discovery, service questions, and queue or booking help
- Owner operations chat with streamed responses and inline charts
- Finance summaries and revenue trend visualization
- HR and staffing actions with approval checkpoints
- CRM integration through Odoo-backed tools
- Voice pipeline with Whisper ASR and Qwen3-TTS
- Multi-tenant shop isolation across agents, data, and checkpoints

## Current Stack

- Frontend: React 18, TypeScript, MUI 7, MUI X Chat, MUI X Charts
- Backend: FastAPI on Python 3.12
- Agent orchestration: LangGraph, LangChain Ollama, PostgreSQL checkpoints
- Legacy customer chat: `pydantic-ai` transition path in `backend/agent_logic.py`
- Database: PostgreSQL 15
- Cache and session state: Redis 7
- Voice: faster-whisper ASR and Qwen3-TTS (`Vivian`)
- ERP / CRM: Odoo 17 via XML-RPC
- Deployment: Docker Compose for local and non-prod test flows, K3s for production, GitHub Actions on a self-hosted runner

## Repository Status

The authoritative product and deployment story is:

- Current product: AI operations system for service businesses
- Current data layer: PostgreSQL and Redis
- Current production deployment: K3s in the `zeroqwait` namespace
- Current non-prod deployment: the single-stack Docker Compose test path published to `http://localhost:3000` and `http://localhost:8000`

## Local Development

### Prerequisites

- Python 3.12
- Node.js 18+
- Docker and Docker Compose
- `uv` recommended for backend dependency sync

### Recommended Setup

1. Clone the repo.

```bash
git clone <your-repo-url>
cd FastCuts
```

2. Set up the backend environment.

```bash
cd backend
uv sync --dev
```

Ensure `backend/.env` exists before starting the backend. If you do not already have one, create it with the database, Redis, Ollama, TTS, MCP, and frontend URL settings used by your local environment.

3. Set up the frontend.

```bash
cd ../frontend
npm install
```

4. Start the local supporting stack.

```bash
cd ..
docker compose up -d db redis booking-mcp finance-mcp hr-mcp odoo
```

5. Start the backend and frontend in source mode.

```bash
cd backend
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd frontend
REACT_APP_API_URL=http://localhost:8000/api npm start
```

6. Open the app.

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- OpenAPI docs: http://localhost:8000/docs

### Full Non-Prod Test Deploy

The authoritative non-prod deployment path is:

```bash
bash deployment/scripts/deploy-test.sh
```

That script brings up the single `zeroqwait` Docker Compose stack and publishes the canonical local URLs:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000

## Deployment Model

- Non-`prod` branch push: GitHub Actions runs the test deployment flow through `deployment/scripts/deploy-test.sh`
- `prod` branch push: GitHub Actions runs the production deployment flow to K3s
- Local image versioning and registry flow: `deployment/scripts/run-local-pipeline.sh`

Production runs on K3s with supporting services and manifests in `k8s-manifests/`.

## Project Structure

```text
FastCuts/
├── backend/                  FastAPI app, LangGraph agents, DB and auth modules
├── frontend/                 React app, landing page, owner dashboard, agent inbox UI
├── mcps/                     Booking, finance, HR, and voice MCP services
├── deployment/               Deployment scripts, local registry tooling, docs
├── k8s-manifests/            Production K3s manifests
├── asr_service/              Whisper ASR service
├── tts_service/              Qwen3-TTS service
├── voice_mcp/                Voice gateway / proxy
├── docker-compose.yml        Local and non-prod stack definition
└── claude.md                 Project operating context and architecture notes
```

## Documentation Map

- `README.md`: top-level product, stack, and development overview
- `docs/README.md`: documentation index and current-vs-legacy guidance
- `backend/README.md`: backend runtime and API overview
- `deployment/docs/README.md`: current deployment model and script guide
- `claude.md`: detailed product, architecture, and operational context used by coding agents

## Key API Surfaces

- Legacy customer chat: `/api/agent/master/chat` and `/api/agent/master/chat/stream`
- Owner agent v2: `/api/v2/agent/chat`, `/api/v2/agent/chat/stream`, `/api/v2/agent/approve`
- Voice: `/api/voice/transcribe`, `/api/voice/tts`
- Auth: `/api/auth/token`, `/api/auth/forgot-password`, `/api/auth/reset-password`

## Notes For Contributors

- The backend dependency source of truth is `backend/pyproject.toml` and `backend/uv.lock`
- The frontend runs against `/api` in containerized mode and `http://localhost:8000/api` in source-run mode
- The owner agent stack is already live in the repo; do not document it as future work unless the note is explicitly marked as historical

## License

This project is licensed under the MIT License.
