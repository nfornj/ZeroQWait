# ZeroQwait

ZeroQwait is an AI operations system for service businesses — barbershops, salons, clinics, auto shops, and any appointment or queue-based business. It provides an AI receptionist for customers and a supervised AI operations workspace for owners.

Live production URL: https://zeroqwait.com

## What It Does

**For customers** — landing page chat with voice support, shop discovery, service questions, queue joining, and real-time position updates.

**For shop owners** — a supervisor agent backed by specialist agents (Receptionist, Finance, HR, CRM) that monitors the business, surfaces insights, proposes actions, and waits for approval before executing high-impact changes. The owner interacts through a streamed chat inbox with inline charts, file attachments, and an approval feed.

## Core Capabilities

- AI receptionist on the landing page and public shop surfaces (voice + text, Whisper ASR, Qwen3-TTS)
- Owner operations chat with SSE streaming, inline charts, and file uploads
- Finance summaries and revenue trend visualization from daily analytics
- HR and staffing management with Human-in-the-Loop approval checkpoints
- Booking and queue management via the Booking MCP
- CRM via Odoo 17 — contacts, leads, pipeline, invoices, and payments
- Inventory and POS agent flows
- Payroll calculation workflows via Temporal
- Shop SOUL — persistent shop personality and learned patterns injected into agent context
- Inferred commitments — the agent tracks promises made in chat and follows up automatically
- Natural-language schedule parser — owner can set recurring agent tasks in plain English
- Agent Brain page — visual node graph of active SOUL patterns, commitments, and schedules
- Telegram integration — receive agent notifications and reply to the supervisor via Telegram
- Multi-tenant isolation: every shop gets its own agent state, DB context, and checkpoints

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, MUI v7, MUI X Chat, MUI X Charts |
| Backend | FastAPI, Python 3.12, SQLAlchemy 2, Alembic |
| Agent framework | LangGraph ≥ 0.4, langgraph-checkpoint-postgres, langchain-ollama |
| LLM | Ollama — `qwen3:14b-q4_K_M` (local GPU, RTX 5070 Ti) |
| Legacy customer chat | `pydantic-ai` path in `backend/agent_logic.py` (transition) |
| Async workflows | Temporal (soul evolution, commitment resolver, payroll, custom schedules) |
| Database | PostgreSQL 15 |
| Cache / sessions | Redis 7 |
| Voice ASR | faster-whisper (`medium`) |
| Voice TTS | Qwen3-TTS 1.7B — voice `Vivian`, port 8880 |
| ERP / CRM | Odoo 17 via XML-RPC |
| Messaging | Telegram bot (notifications + owner chat) |
| Container registry | GitHub Container Registry (`ghcr.io/nfornj`) |
| Production orchestration | K3s, namespace `zeroqwait`, Traefik ingress, GitOps via Argo CD |
| CI / CD | GitHub Actions, self-hosted runner, `deploy-test.yml` / `deploy-prod.yml` |

## Agent Architecture

```
Owner chat  →  POST /api/v2/agent/chat/stream
                      │
               Supervisor Agent (LangGraph)
               ├── classify_intent
               ├── execute_plan → specialist agent or tool
               ├── synthesize_response (SOUL-injected)
               └── human_approval breakpoint (HITL)
                      │
        ┌─────────────┼──────────────────┐
   Receptionist    Finance       HR / Payroll
   Booking MCP    Finance MCP      HR MCP
        │              │              │
   CRM (Odoo)   Inventory / POS   Telegram
        │              │              │
              PostgreSQL + Redis
         LangGraph checkpoint store
```

**Agent brain modules** (all in `backend/agents/`):

| Module | Purpose |
|---|---|
| `supervisor.py` | Central router and response synthesizer |
| `receptionist.py` | Customer-facing booking and queue agent |
| `finance.py` | Revenue, analytics, and financial reporting |
| `hr.py` | Employee management and shift scheduling |
| `crm.py` | Odoo CRM — leads, contacts, pipeline |
| `soul_reader.py` / `soul_updater.py` | Persistent shop personality and learned patterns |
| `commitment_scanner.py` / `commitment_workflows.py` | Inferred follow-through on owner promises |
| `schedule_intent_parser.py` / `custom_schedule_workflow.py` | Natural-language recurring task scheduling |
| `payroll_workflows.py` | Temporal-based payroll calculation |
| `appointment_workflows.py` | Appointment booking and confirmation flows |
| `inventory.py` / `pos_agent.py` | Inventory tracking and POS operations |
| `telegram_agent_bridge.py` | Bidirectional Telegram notification and chat |
| `briefings.py` | Daily and on-demand business briefings |
| `memory_context.py` | Per-conversation memory injection |
| `llm_factory.py` | Tier-aware LLM client factory |
| `checkpoints.py` | PostgreSQL-backed AsyncPostgresSaver setup |

## MCP Tool Servers

| Server | Tools |
|---|---|
| `mcps/booking/` | queue, appointments, wait times, service search |
| `mcps/finance/` | daily revenue, weekly summary, top services, customer metrics |
| `mcps/hr/` | employees, shifts, clock-in/out |
| `mcps/voice/` | TTS and ASR proxy |

## Frontend Pages

| Page | Path | Description |
|---|---|---|
| Landing page | `/` | Marketing, hero, features, pricing, AI chat bubble |
| Public shop | `/shop/:slug` | Customer-facing queue joining |
| Owner dashboard | `/dashboard` | Analytics, queue, team management |
| Agent inbox | `/dashboard/inbox` | Supervisor chat, approval cards, activity feed |
| Agent brain | `/dashboard/brain` | Visual SOUL + commitment + schedule graph |
| Admin | `/admin` | Platform administration |

## Local Development

### Prerequisites

- Python 3.12, Node.js 18+, Docker and Docker Compose
- `uv` for backend dependency management

### Setup

```bash
# 1. Backend
cd backend
uv sync --dev
# Create backend/.env with DB, Redis, Ollama, TTS, MCP, and FRONTEND_URL settings

# 2. Frontend
cd ../frontend
npm install

# 3. Supporting services
cd ..
docker compose up -d db redis booking-mcp finance-mcp hr-mcp odoo

# 4. Run backend and frontend
cd backend && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
cd frontend && REACT_APP_API_URL=http://localhost:8000/api npm start
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- OpenAPI docs: http://localhost:8000/docs

### Full Non-Prod Test Deploy

```bash
bash deployment/scripts/deploy-test.sh
```

Brings up the single `zeroqwait` Docker Compose stack at `http://localhost:3000` / `http://localhost:8000`.

## Deployment

| Trigger | Outcome |
|---|---|
| Push to any non-`prod` branch | `deploy-test.yml` — Docker Compose test stack on runner host |
| Push to `prod` branch | `deploy-prod.yml` — K3s production deploy to `zeroqwait.com` |
| Manual pipeline build | `deployment/scripts/run-local-pipeline.sh` — build, tag, push to GHCR, update manifests |

Production K3s pods: `backend`, `frontend`, `postgres`, `redis`, `asr-service`, `tts-service`, `voice-mcp`, `booking-mcp`, `finance-mcp`, `hr-mcp`, `temporal-worker`, `ollama`.

Images are versioned as `ghcr.io/nfornj/<service>:vYYYYMMDDHHMMSS-<sha>` and managed through Argo CD GitOps.

## Project Structure

```text
FastCuts/
├── backend/
│   ├── agents/           LangGraph agent graphs, SOUL, commitments, scheduling, Temporal workflows
│   ├── agent/            Legacy pydantic-ai cache, analyzer, and customer chat path
│   ├── agent_logic.py    Legacy customer-facing chat (landing page, public booking)
│   ├── routers/          API routers (agent, agent_v2, voice, analytics, payments, POS, Telegram)
│   ├── modules/          Auth, users, shops, employees, queues, admin
│   ├── integrations/     Odoo XML-RPC client
│   ├── services/         Business logic services
│   ├── migrations/       Alembic database migrations
│   └── main.py           FastAPI app entry point
├── frontend/
│   └── src/
│       ├── landing-page/ Marketing page and AI chat bubble
│       ├── features/
│       │   ├── agent-inbox/    Owner supervisor chat, approvals, feed
│       │   ├── agent-brain/    Visual SOUL / commitment / schedule graph
│       │   ├── shop-dashboard/ Analytics, queue, team management
│       │   └── public-booking/ Customer-facing shop and queue page
│       └── contexts/     Auth, Shop, Theme contexts
├── mcps/                 Booking, Finance, HR, Voice MCP servers
├── asr_service/          Whisper ASR microservice
├── tts_service/          Qwen3-TTS microservice (GPU, Vivian voice)
├── voice_mcp/            Voice gateway proxy
├── k8s-manifests/        Production K3s deployment manifests
├── deployment/           Deploy scripts, Argo CD setup, GHCR pipeline tooling
├── docker-compose.yml    Local and non-prod stack
└── claude.md             Project architecture and operating rules for coding agents
```

## Key API Surfaces

| Group | Endpoints |
|---|---|
| Legacy customer chat | `POST /api/agent/master/chat`, `POST /api/agent/master/chat/stream` |
| Owner agent v2 | `POST /api/v2/agent/chat`, `POST /api/v2/agent/chat/stream`, `POST /api/v2/agent/approve`, `GET /api/v2/agent/history`, `GET /api/v2/agent/pending` |
| Voice | `POST /api/voice/transcribe`, `POST /api/voice/tts`, `GET /api/voice/tts/health` |
| Auth | `POST /api/auth/token`, `POST /api/auth/forgot-password`, `POST /api/auth/reset-password` |
| Shops and queues | `GET /api/shops/`, `GET /api/shops/my-shops`, `GET /api/shops/s/{slug}`, `POST /api/queues/shop/{id}/join` |
| Payments | `POST /api/payments/...` |
| Payroll | `GET /api/payroll/...`, `POST /api/payroll/...` |
| POS | `GET /api/pos/...`, `POST /api/pos/...` |
| Telegram | `POST /api/telegram/webhook` |
| Inventory | `GET /api/inventory/...`, `POST /api/inventory/...` |

## Notes For Contributors

- Backend dependency source of truth: `backend/pyproject.toml` and `backend/uv.lock`
- Frontend runs against `/api` in containers and `http://localhost:8000/api` in source mode
- Do not use `localhost:5000` in any K8s manifest — GHCR only
- TTS service: Qwen3-TTS, voice `Vivian`, port `8880` — do not replace or remap
- LLM: `qwen3:14b-q4_K_M` via Ollama — do not change without explicit approval
- `backend/agent/` and `backend/agent_logic.py` are still active — do not delete until customer chat migrates to the LangGraph receptionist

## License

This project is licensed under the MIT License.
