# ZeroQwait — Project Rules & Context

> **Last updated**: 2026-04-20
> **Live URL**: https://zeroqwait.com (test ingress: http://192.168.2.134.nip.io)
> **Product pivot (2026-04-10)**: Transitioning from queue-management SaaS → **Agent-as-a-Service (AaaS)** platform powered by LangGraph

---

## 0. AI Assistant Safety Rules (MANDATORY — Read First)

> **These rules apply to any AI assistant (GitHub Copilot, Claude, etc.) working on this codebase.**

### 0.1 No Unauthorized Model or Service Changes

**NEVER change the following without explicit user permission:**

| Protected Artefact | Current Value | Why It Matters |
| ---- | ---- | ---- |
| Agent framework | LangGraph (langgraph >= 0.4) on FastAPI | Core state machine for all agent graphs; changing breaks checkpoint compatibility |
| LLM model | `qwen3:14b-q4_K_M` via Ollama | Swapping models breaks agent behaviour and costs GPU re-pull time |
| TTS engine | Qwen3-TTS (`Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`) | Kokoro / Coqui incident on 2026-02-14 required emergency rollback |
| TTS voice | `Vivian` | Voice is a brand experience choice |
| TTS port | `8880` | Ingress and backend config hard-wired to this port |
| ASR engine | faster-whisper (`medium`) | GPU compute budget depends on this model size |
| Embedding model | `all-MiniLM-L6-v2` | Semantic cache keys are tied to these embeddings |
| Database engine | PostgreSQL 15 | Alembic migrations + LangGraph checkpoints target this version |
| Orchestration | K3s namespace `zeroqwait` | All K8s manifests target this namespace |

**Before swapping any model/engine/service**: stop, surface the proposal to the user, explain the tradeoffs, and wait for explicit approval.

### 0.2 No Silent Architectural Changes

The following changes require user approval before implementation:

- Replacing a service (e.g. switching from Qwen3-TTS → any other TTS)
- Changing default models in K8s ConfigMaps or Dockerfiles
- Adding new external service dependencies (new APIs, new LLM providers)
- Modifying authentication or authorization logic
- Changing database schema in ways that skip Alembic migrations
- Modifying LangGraph graph topology (adding/removing nodes, edges, or breakpoints)
- Changing the Supervisor → sub-agent routing logic in `backend/agents/supervisor.py`
- Adding or removing MCP server registrations
- Modifying `tenant_id` injection or multi-tenancy isolation logic

### 0.3 No Patches or Workarounds Without Approval

**The goal is correct design, not patchwork.**

A **patch** is any change that:
- Works around a root-cause problem instead of fixing it properly
- Adds a special-case condition or flag to compensate for a design flaw
- Hacks around a missing abstraction (e.g. monkey-patching, `try/except` swallowing real errors, ad-hoc state overrides)
- Adds inference/heuristic logic to compensate for a structural gap (e.g. inferring missing context from message history because state is improperly reset)

**Before implementing a patch**: stop, clearly describe:
1. What the root cause is
2. What the proper design fix would be
3. Why a patch is being proposed instead (e.g. time, scope, risk)

Then **wait for explicit user approval** before proceeding with the patch.

If the right fix requires a refactor, schema change, or architectural adjustment — propose it. Do not silently introduce workarounds to avoid that work.

### 0.5 Stabilization-First Policy (No Fallbacks Yet)

During the current stabilization phase, do **not** add fallback paths for failing core logic (classification, routing, tool execution, synthesis, persistence) unless the user explicitly approves.

Required behavior during stabilization:
- Let failures surface with clear logs and observable errors
- Fix root causes directly (code, state handling, schema, graph logic)
- Avoid masking failures with generic fallback responses

Fallback methods can be introduced later, after core flows are stable and validated.

### 0.6 Complexity And Product-Drift Guardrail

The current goal is to build **a vertical agent product for service businesses**, not a generic agent framework.

AI assistants working on this codebase must actively guard against unnecessary complexity and architecture drift.

Before implementing a design that appears significantly more complex than the current need, stop and explicitly tell the user if the work is drifting in any of these directions:

- Building generic agent infrastructure instead of product features
- Creating reusable framework abstractions before one concrete product flow is validated
- Adding orchestration layers, planners, memory systems, or tool registries that are broader than ZeroQwait's actual business needs
- Solving speculative future scale/problems before the current owner/customer workflows are working well
- Replacing simple shop-specific logic with abstract multi-agent/platform machinery that makes the system harder to reason about

When this risk appears, the assistant must explicitly state:

1. Why the proposal may be too complex for the current product stage
2. What the simpler product-focused version would be
3. Whether the work improves the owner experience, customer experience, or core agent operations in a directly testable way

Rule of thumb:
- Prefer the simplest design that improves the real shop-owner or customer workflow
- Reuse LangGraph, FastAPI, PostgreSQL, Redis, and current MCP patterns instead of inventing new platform layers
- Do not build generic framework capabilities unless the user explicitly asks for them or the current product cannot proceed without them

### 0.4 Allowed Without Approval

- Bug fixes that address the actual root cause with proper design
- Performance optimizations that keep the same service/model
- Creating new microservices that are additive (e.g. MCP wrapper)
- Updating timeouts, retry counts, connection pool sizes
- Adding logging, metrics, or health-check endpoints

---

## 1. What Is ZeroQwait

An **Agent-as-a-Service (AaaS) platform** where service businesses (barbers, salons, clinics, auto shops, etc.) each get their own **team of AI agents** — a Receptionist, Finance manager, and HR assistant — orchestrated by a Supervisor agent. Shop owners manage their entire business operations via natural-language chat with Human-in-the-Loop approval workflows. Customers interact with the shop's Receptionist agent to discover services, join queues, and get real-time updates.

### Current Product Goal

ZeroQwait's current product goal is to become **a practical AI operations system for one service business at a time** — not a generic agent framework.

The product should feel like:
- An **AI Receptionist** for customers that helps them discover services, ask questions, join queues, book appointments, and stay oriented without friction
- An **AI operations workspace** for shop owners that monitors the day, surfaces issues, proposes actions, requests approval for high-impact changes, and gradually takes over repeatable operational work
- A **supervised AI team** where the owner remains in control, but no longer has to manually run every queue, schedule, update, or follow-up

The intended end-state is:
- The customer feels like they are interacting with a smart front-desk receptionist, not a queue tool
- The owner feels like they are supervising an AI team, not operating a traditional dashboard with a chatbot attached
- The architecture serves real shop workflows first and should only become more complex when it directly improves owner experience, customer experience, or safe operational autonomy

### Product Vision

Every shop owner gets a personalized AI operations team that:
- **Automates** routine tasks (bookings, queue management, shift scheduling)
- **Reports** business metrics and financial summaries on demand
- **Asks for approval** before executing high-impact actions (e.g., changing schedules, processing refunds)
- **Learns** the shop's patterns and adapts over time

Near-term product focus:
- Make the owner experience feel like an operations cockpit, not just chat
- Make the customer experience feel like an AI receptionist, not just self-check-in
- Build event-driven, policy-aware agent behavior only where it improves real business outcomes
- Avoid generic platform abstractions unless they are required for a concrete ZeroQwait workflow

### Core User Flows

1. **Shop Owner** → Signs up → Gets AI agent team → Manages the business through an AI operations workspace and chat inbox → Reviews agent proposals and approvals → Monitors outcomes instead of manually driving every workflow.
2. **Customer** → Lands on marketing page or shop page → Interacts with shop's Receptionist agent (text/voice) → Discovers services → Joins queue → Gets position updates.
3. **Employee** → Logs in → Receives shift assignments from HR agent → Manages individual queue from employee dashboard.

### Three Public-Facing Capabilities (Customer Side)

The customer-facing AI agent always presents **exactly three capabilities**:

1. **Register a Shop** — Set up your business and get your own AI agent team
2. **Search for Shops** — Find services nearby and join an AI-powered queue
3. **Ask about our Products** — Pricing, features, and how it all works

These three items must appear consistently across:

- Frontend welcome message (`MasterAIAgent.tsx` initial `chatHistory`)
- Backend GREETING intent handler in `stream_chat()` and `chat()`
- Backend conversation agent fallback (`get_conversational_response()` exception handler)
- Backend conversation agent system prompt (rules section)

**Rule**: Never change the wording of these three features without updating all four locations.

---

## 2. Tech Stack

| Layer                       | Technology                               | Details                                                             |
| --------------------------- | ---------------------------------------- | ------------------------------------------------------------------- |
| **Frontend**                | React 18 + TypeScript                    | MUI v7.3.7, react-router-dom v6, axios                              |
| **Backend**                 | FastAPI 0.128.0 (Python 3.9+)            | Uvicorn 0.39.0, SQLAlchemy 2.0.44                                   |
| **Agent Framework**         | LangGraph >= 0.4 on FastAPI              | Graph-based state machines, Human-in-the-Loop breakpoints, PostgreSQL checkpoints |
| **Agent Checkpoints**       | langgraph-checkpoint-postgres             | Persistent agent state per tenant in PostgreSQL                     |
| **Database**                | PostgreSQL 15                            | Via K8s StatefulSet (prod DB: `fastcuts_db`, user: `fastcuts_user`) |
| **Cache**                   | Redis 5.0.1                              | Session history, category cache, rate limiting, agent state cache   |
| **AI/LLM**                  | LangGraph + langchain-ollama + Ollama     | Model: `qwen3:14b-q4_K_M` (~8-9GB, Q4_K_M quantized, GPU-only)      |
| **Embeddings**              | sentence-transformers (all-MiniLM-L6-v2) | Semantic cache for query analysis                                   |
| **MCP Tooling**             | Model Context Protocol servers            | BookingMCP, FinanceMCP, HRMCP — tools decoupled from agents        |
| **Voice ASR**               | Whisper (via `asr_service/`)             | GPU-accelerated, separate K8s pod                                   |
| **Voice TTS**               | Qwen3-TTS 1.7B (via `tts_service/`)     | `/v1/audio/speech` OpenAI-compatible, voice: `Vivian`, port 8880 — **DO NOT REPLACE** (see §6) |
| **Container Orchestration** | K3s (lightweight K8s)                    | Namespace: `zeroqwait`, Traefik ingress                             |
| **Deployment**              | GitHub Actions + self-hosted runner      | Branch push triggers automatic deploy workflow                       |

### Key Dependencies (New for AaaS Pivot)

```
langgraph >= 0.4                       # Core graph-based agent framework
langgraph-checkpoint-postgres >= 2.0   # PostgreSQL checkpoint persistence
langchain-ollama >= 0.3                # Ollama LLM integration for LangGraph
langchain-core >= 0.3                  # Base abstractions (messages, tools)
```

> **Migration note**: `pydantic-ai 0.8.1` is being phased out. The existing `agent_logic.py` (pydantic-ai) continues to serve the **customer-facing landing page chat** during transition. New **owner-facing agent graphs** are built on LangGraph from the start.

---

## 3. Design System

- **Framework**: Google Material Design 3 (Material You).
- **Implementation**: MUI v7+ with rigid MD3 overrides (configured in `frontend/src/contexts/ThemeContext.tsx`).
- **Principles**:
  - **Simplicity**: Clean, uncluttered interface.
  - **Component Reuse**: Use existing MUI components; avoid custom CSS where an MUI component suffices.
  - **Styling**: Use the customized `ThemeContext` which provides MD3-compliant border radii (20px+), typography, and elevation. Do not revert to square corners or heavy drop shadows.
- **Theme Presets**: default, ocean, forest, sunset, midnight, corporate (user-selectable, persisted in localStorage).
- **Color Modes**: Light and dark (toggle via `useThemeContext().toggleMode()`).

---

## 4. Project Structure

```
zeroqwait/
├── frontend/                         # React SPA
│   ├── src/
│   │   ├── App.tsx                   # Route definitions
│   │   ├── landing-page/             # Marketing homepage
│   │   │   ├── LandingPage.tsx       # Hero, Features, Pricing, FAQ, Testimonials
│   │   │   └── components/
│   │   │       └── MasterAIAgent.tsx  # AI chat bubble (SSE streaming + voice)
│   │   ├── components/
│   │   │   ├── Navbar.tsx
│   │   │   ├── ProtectedRoute.tsx
│   │   │   ├── SubdomainHandler.tsx
│   │   │   └── agent/               # CanvasOrb.tsx, ParticleSphere.tsx (visual effects)
│   │   ├── contexts/
│   │   │   ├── AuthContext.tsx       # JWT auth, token refresh, axios interceptors
│   │   │   ├── ShopContext.tsx       # Shop state management
│   │   │   └── ThemeContext.tsx      # MD3 theming, color modes, presets
│   │   ├── features/
│   │   │   ├── admin/               # Admin panel components
│   │   │   ├── auth/                # Sign-in/sign-up pages (Material template based)
│   │   │   ├── public-booking/      # Public shop view, queue joining
│   │   │   ├── shop-dashboard/      # Owner dashboard, analytics, queue management
│   │   │   └── agent-inbox/         # NEW: Owner agent inbox/feed (approvals, updates, chat)
│   │   │       ├── AgentInbox.tsx    # Main inbox view — agent updates + approval cards
│   │   │       ├── ApprovalCard.tsx  # Human-in-the-loop approval/reject widget
│   │   │       ├── AgentChat.tsx     # Owner ↔ Supervisor chat interface
│   │   │       └── AgentFeed.tsx     # Chronological feed of agent actions
│   │   ├── hooks/
│   │   │   ├── useAudioRecorder.tsx  # Records audio blobs (used by MasterAIAgent)
│   │   │   ├── useAudioVisualizer.ts # Audio waveform visualization
│   │   │   └── useVoiceInterface.tsx # Browser SpeechRecognition (alternate, not primary)
│   │   ├── services/api.ts          # Axios-based API service
│   │   └── layouts/                 # ShopLayout, PublicLayout
│   ├── Dockerfile / Dockerfile.prod  # Nginx-based production build
│   └── nginx.conf                   # Reverse proxy config
│
├── backend/                          # FastAPI application
│   ├── main.py                       # App entry, lifespan, CORS, router mounting
│   ├── agent_logic.py                # LEGACY: pydantic-ai customer-facing agent (kept during transition)
│   ├── agents/                       # NEW: LangGraph agent graphs
│   │   ├── __init__.py
│   │   ├── state.py                  # AgentState TypedDict (shared across all graphs)
│   │   ├── supervisor.py             # Supervisor agent graph (routes to sub-agents)
│   │   ├── receptionist.py           # Receptionist sub-agent (bookings, queue, customer care)
│   │   ├── finance.py                # Finance sub-agent (revenue, analytics, reporting)
│   │   ├── hr.py                     # HR sub-agent (employees, shifts, scheduling)
│   │   ├── checkpoints.py            # PostgreSQL checkpoint saver setup
│   │   └── tools/                    # LangGraph tool definitions (thin wrappers → MCP calls)
│   │       ├── booking_tools.py
│   │       ├── finance_tools.py
│   │       └── hr_tools.py
│   ├── db_interface.py               # Database abstraction layer (SQLAlchemy, 853 lines)
│   ├── database.py                   # Engine, SessionLocal, connection config
│   ├── models.py                     # Re-exports all SQLAlchemy models
│   ├── schemas.py                    # Re-exports all Pydantic schemas
│   ├── redis_client.py               # Redis wrapper (caching, sessions, rate limits)
│   ├── websocket_manager.py          # WebSocket connection manager for real-time updates
│   ├── scheduler.py                  # Background analytics scheduler
│   ├── permissions.py                # Authorization helpers
│   ├── tier_limits.py                # Subscription tier enforcement
│   ├── tenant_manager.py             # Multi-tenancy schema isolation
│   ├── registration_agent.py         # Registration state machine (Redis-backed)
│   ├── Dockerfile                    # Python 3.9-slim, uv sync, sentence-transformer pre-warm
│   ├── routers/                      # API routers
│   │   ├── agent.py                  # LEGACY: /api/agent/master/chat, /chat/stream
│   │   ├── agent_v2.py               # NEW: /api/v2/agent/ — LangGraph supervisor endpoints
│   │   ├── voice.py                  # /api/voice/transcribe, /tts, /tts/health
│   │   ├── analytics.py
│   │   ├── services.py
│   │   ├── subscriptions.py
│   │   ├── uploads.py
│   │   └── data_generation.py
│   ├── modules/                      # Modular domain routers
│   │   ├── auth/                     # /api/auth/token, /forgot-password
│   │   ├── users/                    # /api/users/me, CRUD
│   │   ├── shops/                    # /api/shops/, /my-shops, /s/{slug}, close-days
│   │   ├── employees/                # /api/employees, shifts
│   │   ├── queues/                   # /api/queues/shop/{id}/join, /call-next
│   │   ├── admin/                    # Admin endpoints
│   │   └── agent/                    # Agent-related models (ConversationHistory, etc.)
│   ├── shared/                       # Shared utilities (auth_utils, schemas)
│   └── test_live.py                  # End-to-end remote agent test script
│
├── mcps/                             # MCP servers (Model Context Protocol)
│   ├── booking/                      # NEW: BookingMCP — queue, appointments, wait times
│   │   ├── server.py
│   │   └── Dockerfile
│   ├── finance/                      # NEW: FinanceMCP — revenue, analytics, invoicing
│   │   ├── server.py
│   │   └── Dockerfile
│   ├── hr/                           # NEW: HRMCP — employees, shifts, scheduling
│   │   ├── server.py
│   │   └── Dockerfile
│   └── voice/                        # Existing: Voice MCP (TTS + ASR proxy)
│       ├── server.py
│       └── Dockerfile
│
├── voice_mcp/                        # Existing: Unified voice gateway (TTS + ASR + MCP)
│   ├── server.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── asr_service/                      # Whisper ASR microservice
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── tts_service/                      # Qwen3-TTS microservice
│   ├── main.py                       # FastAPI wrapper, /v1/audio/speech (OpenAI-compatible)
│   ├── Dockerfile                    # nvidia/cuda:12.8 based
│   └── requirements.txt              # qwen-tts, fastapi, uvicorn, soundfile
│
├── k8s-manifests/                    # Kubernetes deployment configs
│   ├── backend-deployment.yaml       # Backend pod (hostPath mount, init containers)
│   ├── backend-configmap.yaml        # Environment variables
│   ├── backend-secret.yaml           # DB password, JWT secret
│   ├── frontend-deployment.yaml
│   ├── postgres-statefulset.yaml     # PostgreSQL with PVC
│   ├── redis-statefulset.yaml        # Redis with PVC
│   ├── ingress-traefik.yaml          # Traefik ingress (wildcard TLS)
│   ├── asr-deployment.yaml           # ASR service
│   ├── tts-deployment.yaml           # Qwen3-TTS GPU pod + ClusterIP service
│   ├── tts-pvc.yaml                  # HuggingFace model cache (10Gi)
│   └── gpu-time-slicing.yaml         # NVIDIA GPU time-slicing config
│
├── deployment/
│   ├── scripts/
│   │   ├── deploy-k8s.sh            # Main K8s deployment script
│   │   └── deploy-and-sync.sh       # Legacy manual helper (not the default deploy path)
│   └── docker/                       # Docker build configs
│
├── docker-compose.yml                # Local dev (backend:8000, frontend:3000)
├── docker-compose.prod.yml           # Production (backend:8001, frontend:3001, postgres)
└── claude.md                         # THIS FILE — project context for AI assistants
```

---

## 5. AI Agent Architecture

### Overview (AaaS Pivot — 2026-04-10)

Each shop owner receives a **team of AI agents** powered by **LangGraph state machines**. A **Supervisor agent** acts as the central router, interpreting the owner's natural-language commands and delegating to specialized **sub-agents**: Receptionist, Finance, and HR. All agent state is checkpointed to PostgreSQL per tenant for persistence and Human-in-the-Loop approval workflows.

### Architecture Diagram

```
                    ┌─────────────────────────────────┐
                    │       Shop Owner (Chat)          │
                    │   Frontend Agent Inbox / Feed    │
                    └──────────────┬──────────────────┘
                                   │ SSE / WebSocket
                                   ▼
                    ┌─────────────────────────────────┐
                    │     POST /api/v2/agent/chat      │
                    │     (FastAPI + Auth + tenant_id)  │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │       SUPERVISOR AGENT            │
                    │   (LangGraph StateGraph)          │
                    │   ┌─────────────────────────┐    │
                    │   │ classify_intent (node)   │    │
                    │   │ route_to_agent (edges)   │    │
                    │   │ human_approval (break)   │    │
                    │   │ respond (node)           │    │
                    │   └─────────────────────────┘    │
                    └───┬───────────┬─────────────┬────┘
                        │           │             │
              ┌─────────┘  ┌────────┘ ┌──────────┘
              │ RECEPTIONIST│  │  FINANCE    │ │     HR      │
              │  Sub-Agent  │  │  Sub-Agent  │ │  Sub-Agent  │
              │ (StateGraph)│  │ (StateGraph)│ │ (StateGraph) │
              └──────┬──────┘  └─────┬───────┘ └──────┬──────┘
                     │               │                │
              ┌──────┘        ┌──────┘        ┌──────┘
              │ BookingMCP  │  │ FinanceMCP  │ │   HRMCP     │
              │  (tools)    │  │  (tools)    │ │  (tools)    │
              └─────────────┘  └─────────────┘ └─────────────┘
                     │               │                │
              ┌──────┘──────────────┘───────────────┘──────┐
              │          PostgreSQL (tenant-isolated)          │
              │   queues │ services │ analytics │ employees   │
              │          LangGraph checkpoints table           │
              └──────────────────────────────────────────────┘
```

### Agent Components

| Component | File | Purpose |
| --------- | ---- | ------- |
| **AgentState** | `backend/agents/state.py` | Shared `TypedDict` state: messages, tenant_id, current_agent, pending_approval, tool_results |
| **Supervisor** | `backend/agents/supervisor.py` | Central router: classifies owner intent → routes to sub-agent → collects result → responds |
| **Receptionist** | `backend/agents/receptionist.py` | Customer-facing: bookings, queue join/leave, wait times, service discovery |
| **Finance** | `backend/agents/finance.py` | Owner-facing: revenue summaries, daily/weekly analytics, financial reports |
| **HR** | `backend/agents/hr.py` | Owner-facing: employee management, shift scheduling, availability |
| **Checkpoints** | `backend/agents/checkpoints.py` | PostgreSQL-backed `AsyncPostgresSaver` for persistent graph state |

### AgentState Schema

```python
from typing import TypedDict, Annotated, Sequence, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    tenant_id: int                        # Shop ID — injected at entry, never changeable by agent
    user_id: int                          # Authenticated owner's user ID
    current_agent: str                    # "supervisor" | "receptionist" | "finance" | "hr"
    pending_approval: Optional[dict]      # Action awaiting owner's approve/reject
    tool_results: Optional[dict]          # Latest tool execution results
    needs_human_input: bool               # True when at a Human-in-the-Loop breakpoint
```

### Supervisor Routing Logic

The Supervisor classifies the owner's message and routes to the appropriate sub-agent:

| Owner Intent | Target Agent | Example Commands |
| ------------ | ------------ | ---------------- |
| Booking / queue / appointment | Receptionist | "How many people are in the queue?", "Close the queue for today" |
| Revenue / analytics / reports | Finance | "What was yesterday's revenue?", "Show me this week's analytics" |
| Employees / shifts / schedule | HR | "Add a new employee", "Show me today's shift schedule" |
| General / unclear | Supervisor (self) | "Hello", "What can you do?", "Help me with my shop" |

### Human-in-the-Loop (HITL) Approval Flow

High-impact actions pause at a LangGraph `interrupt_before` breakpoint and wait for the owner's explicit approval:

```
Agent proposes action → State saved to checkpoint → SSE event: {type: 'approval_required', action, details}
     → Owner sees ApprovalCard in inbox → Clicks Approve/Reject
     → POST /api/v2/agent/approve → Graph resumes from checkpoint → Executes or cancels
```

**Actions requiring approval** (configurable per shop):
- Closing/opening the queue
- Modifying employee schedules
- Processing refunds or adjusting prices
- Sending bulk customer notifications
- Changing shop operating hours

### Multi-Tenancy in Agent Context

Every agent graph invocation is **strictly tenant-scoped**:

1. **Entry point** (`routers/agent_v2.py`): Extracts `tenant_id` (shop_id) from authenticated JWT + shop ownership check
2. **State injection**: `tenant_id` is set in `AgentState` at graph invocation — agents cannot modify it
3. **Tool execution**: Every MCP tool call includes `tenant_id` in its context → `tenant_manager.tenant_session(shop_id)` ensures DB queries hit the correct schema
4. **Checkpoint isolation**: Thread ID format: `tenant_{shop_id}_{user_id}` — ensures checkpoint data is tenant-scoped

### MCP Tool Servers

Tools are decoupled from agents via Model Context Protocol servers. Each MCP server exposes a set of tools that agents call through thin wrappers.

| MCP Server | Tools Exposed | Backing |
| ---------- | ------------- | ------- |
| **BookingMCP** | `list_queue`, `join_queue`, `call_next`, `get_wait_time`, `close_queue`, `search_services` | `db_interface.py` queue + service methods |
| **FinanceMCP** | `daily_revenue`, `weekly_summary`, `top_services`, `customer_metrics`, `export_report` | `db_interface.py` analytics methods + `daily_analytics` table |
| **HRMCP** | `list_employees`, `add_employee`, `remove_employee`, `get_shifts`, `assign_shift`, `clock_in_out` | `db_interface.py` employee/shift methods |
| **VoiceMCP** | `transcribe_audio`, `synthesize_speech` | Existing `voice_mcp/server.py` (TTS + ASR proxy) |

**MCP ↔ Agent binding**: Each sub-agent's LangGraph `ToolNode` calls the corresponding MCP server. This separation means:
- Tools can be tested independently of agents
- New tools can be added to an MCP server without modifying agent graph topology
- MCP servers can be deployed as separate K8s pods for scaling (future)

### Legacy Customer-Facing Agent (Transition Period)

During the AaaS transition, the existing **pydantic-ai agent** (`agent_logic.py`) continues to serve:
- Landing page chat (`MasterAIAgent.tsx`)
- Public shop discovery and queue joining
- Registration flow

The three customer-facing capabilities remain unchanged:
1. **Register a Shop** — Set up your business and get your own AI agent team
2. **Search for Shops** — Find services nearby and join an AI-powered queue
3. **Ask about our Products** — Pricing, features, and how it all works

These three items must appear consistently across:
- Frontend welcome message (`MasterAIAgent.tsx` initial `chatHistory`)
- Backend GREETING intent handler in `stream_chat()` and `chat()`
- Backend conversation agent fallback (`get_conversational_response()` exception handler)
- Backend conversation agent system prompt (rules section)

**Rule**: Never change the wording of these three features without updating all four locations.

### Owner-Facing Agent (New — LangGraph)

After a shop owner logs in and navigates to their dashboard, they interact with the **Supervisor agent** via the **Agent Inbox**:

| Feature | Implementation |
| ------- | -------------- |
| **Chat** | SSE streaming via `POST /api/v2/agent/chat/stream` |
| **Approvals** | `POST /api/v2/agent/approve` resumes checkpointed graph |
| **Feed** | WebSocket broadcast of agent actions (queue updates, shift changes, etc.) |
| **History** | LangGraph checkpoint + `conversation_history` table |
| **Voice** | Same voice pipeline (Qwen3-TTS Vivian), routed through owner chat |

### Chat Flow (Owner → Supervisor)

1. Owner sends message via Agent Inbox → `POST /api/v2/agent/chat/stream`
2. JWT auth → extract `user_id` + `shop_id` (tenant_id)
3. Load or create LangGraph checkpoint: `tenant_{shop_id}_{user_id}`
4. Supervisor graph invoked with `AgentState{messages, tenant_id, user_id}`
5. Supervisor classifies intent → routes to sub-agent (conditional edge)
6. Sub-agent executes tools via MCP → returns result to Supervisor
7. If HITL required → `interrupt_before` → SSE `approval_required` event → wait
8. If no HITL → Supervisor formats response → SSE stream to frontend
9. State checkpointed to PostgreSQL after each graph step

### Streaming (SSE) — Extended Events

- Endpoint: `POST /api/v2/agent/chat/stream`
- Events:
  - `{type: 'text', content}` — streaming text tokens
  - `{type: 'agent_switch', agent}` — sub-agent delegation indicator
  - `{type: 'tool_call', tool, args}` — tool execution started
  - `{type: 'tool_result', tool, result}` — tool execution completed
  - `{type: 'approval_required', action, details}` — HITL breakpoint
  - `{type: 'actions', actions}` — quick-action buttons
  - `{type: 'sentence', text, audio}` — paired text+TTS (voice mode)
  - `[DONE]` — stream complete

---

## 6. Voice Pipeline

```
[Browser Mic] → useAudioRecorder (blob) → POST /api/voice/transcribe → Whisper ASR pod
     → transcribed text → MasterAgent.chat() → response text
     → POST /api/voice/tts → Qwen3-TTS K8s pod (GPU) → WAV/MP3 audio → AudioContext playback
```

- ASR: Whisper model in dedicated K8s pod (`asr-service`)
- TTS: Qwen3-TTS 1.7B CustomVoice running as K8s pod with GPU acceleration (voice: `Vivian` — warm, clear North American English accent)
- Frontend queues TTS sentences and plays them sequentially
- **Paired Streaming**: Backend splits LLM response into sentences, generates TTS audio concurrently per sentence, sends `{type: 'sentence', text, audio}` SSE events. Frontend plays audio + typewriter text simultaneously for synchronized output.

### TTS Configuration — DO NOT CHANGE

> **CRITICAL RULE**: Qwen3-TTS is the **only approved TTS service** for ZeroQwait. **Never** replace it with Kokoro TTS, Coqui, Piper, or any other TTS engine.

| Setting               | Value                                                          |
| --------------------- | -------------------------------------------------------------- |
| **Service**           | Qwen3-TTS (official backend)                                  |
| **Model**             | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`                       |
| **Voice**             | `Vivian` (warm, clear North American English accent)           |
| **Port**              | `8880` (ClusterIP service in `zeroqwait` namespace)            |
| **K8s Deployment**    | `tts-service` in namespace `zeroqwait`                         |
| **Docker Image**      | `localhost:5000/tts-service:latest` (local registry)           |
| **Dockerfile**        | `/home/neekrishrichu/apps/qwen3-tts/Dockerfile.blackwell`      |
| **Base Image**        | `nvidia/cuda:12.8.1-cudnn-devel-ubuntu22.04` (builder)         |
| **PyTorch**           | `2.10.0+cu128` (supports sm_120 Blackwell)                     |
| **GPU**               | RTX 5070 Ti via GPU time-slicing (shared with Ollama)          |
| **GPU Memory**        | ~4.4 GiB VRAM                                                  |
| **Model Cache PVC**   | `tts-model-cache` (10Gi, local-path)                           |
| **Startup Probe**     | 10-min allowance (model download on fresh PVC)                 |

**Voice name `Vivian` must appear in exactly these 3 files:**
1. `backend/routers/voice.py` — default voice parameter
2. `backend/agent_logic.py` — `_generate_tts_audio()` function (also uses `model: "tts-1-en"`, `language: "English"`, `instruct` for North American accent)
3. `frontend/src/landing-page/components/MasterAIAgent.tsx` — TTS fetch body

**Why this matters**: On 2026-02-14, Kokoro TTS was accidentally started on port 8880, displacing Qwen3-TTS. This required reverting voice names in 3 files and redeploying both backend and frontend. Prevent this by never running another TTS service on port 8880.

**Note (2026-03-13)**: Voice changed from `Serena` to `Vivian` for clearer North American English accent. Also switched to `tts-1-en` model with explicit `language: "English"` and `instruct` parameter across all 3 files + the voice.py TTS proxy endpoint.

**Note (2026-03-11)**: TTS migrated from Docker container to K8s pod with GPU acceleration. Built custom Blackwell image (`Dockerfile.blackwell`) with PyTorch 2.10.0+cu128 supporting sm_120. GPU shared with Ollama via NVIDIA time-slicing (2 virtual GPUs from 1 physical RTX 5070 Ti). K8s manifests: `tts-pvc.yaml`, `tts-deployment.yaml`, `gpu-time-slicing.yaml`.

### Voice Mode vs Chat Mode

Users toggle between **Voice Mode** and **Chat Mode** via a pill button in the top-right controls:

| Feature            | Voice Mode                                         | Chat Mode                                      |
| -------------------| -------------------------------------------------- | ---------------------------------------------- |
| **TTS Audio**      | Enabled — audio plays with each response sentence  | Disabled — text-only, silent                   |
| **Orb**            | Large, clickable for voice recording               | Small, decorative (no recording)               |
| **Text Input**     | Hidden during recording, visible otherwise         | Always visible                                 |
| **SSE `is_voice`** | `true` — backend may optimize for voice            | `false`                                        |
| **Registration**   | Form prompts spoken via TTS + inline form widgets  | Form displayed as text + inline form widgets   |

- Default: Voice Mode (TTS enabled)
- Switching to Chat Mode stops any active audio playback and recording
- State: `interactionMode` ("voice" | "chat") in `MasterAIAgent.tsx`
- Ref: `interactionModeRef` keeps callbacks in sync with React state

---

## 7. Authentication

- **Method**: JWT (python-jose) with OAuth2 password flow
- **Login**: `POST /api/auth/token` (form data) → returns `access_token` + sets cookie
- **Roles**: `customer`, `shop_owner`, `employee`, `manager`, `super_admin`
- **Frontend**: AuthContext with axios interceptors; token stored in localStorage; 60s expiry check
- **Protected Routes**: `ProtectedRoute` component wraps shop owner/admin pages

---

## 8. Database

- **Engine**: PostgreSQL 15 (K8s StatefulSet with PVC)
- **ORM**: SQLAlchemy 2.0.44 with Alembic migrations
- **Connection**: Constructed from `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` env vars
- **Prod credentials**: user=`fastcuts_user`, db=`fastcuts_db`
- **Pool**: 5 connections, 10 overflow, pre-ping enabled

### Key Tables

| Table                                   | Purpose                                  |
| --------------------------------------- | ---------------------------------------- |
| `users`                                 | All user accounts (42 rows)              |
| `shops`                                 | Registered businesses (58 rows)          |
| `queues` / `queue_items`                | Queue management                         |
| `shop_services`                         | Services offered by shops                |
| `shop_employees` / `employee_shifts`    | Staff management                         |
| `daily_analytics`                       | Per-shop daily metrics                   |
| `conversation_history`                  | AI chat history persistence (753+ rows)  |
| `category_aliases` / `learned_synonyms` | Dynamic category learning                |
| `agent_knowledge`                       | Knowledge base entries for agent prompts |

---

## 9. Infrastructure & Deployment

### Deployment Host (Runner Node)

- **Runner host IP**: `192.168.2.134` (Linux x86_64, Ubuntu 24.04)
- **K8s**: K3s v1.34.3 (lightweight Kubernetes)
- **Docker**: v29.2.0
- **KUBECONFIG**: `/etc/rancher/k3s/k3s.yaml`
- **App path**: `/home/neekrishrichu/apps/zeroqwait`
- **Deployment mode**: GitHub Actions self-hosted runner executes deploy scripts on push

### K8s Layout (namespace: `zeroqwait`)

| Pod             | Service Type         | Port Mapping              |
| --------------- | -------------------- | ------------------------- |
| `backend-*`     | NodePort             | 30000 → 8000              |
| `frontend-*`    | NodePort             | 30001 → 3000 (nginx → 80) |
| `postgres-0`    | ClusterIP (headless) | 5432                      |
| `redis-0`       | ClusterIP (headless) | 6379                      |
| `asr-service-*` | ClusterIP            | 8000                      |
| `tts-service-*` | ClusterIP            | 8880 (GPU-accelerated)    |
| `ollama-*`      | ClusterIP + NodePort | 11434 (ClusterIP), 30002 (NodePort) |

### Ingress (Traefik)

- Production: `zeroqwait.com` + `*.zeroqwait.com` (added 2026-03-06)
- Base: `192.168.2.134.nip.io` → `/api` → backend, `/` → frontend
- Wildcard: `*.192.168.2.134.nip.io` (shop subdomains)
- TLS: Self-signed wildcard cert in `zeroqwait-wildcard-tls` secret

### Deployment Flow (Authoritative)

```bash
# Non-prod branch auto-deploy (single local Compose stack)
git push origin <branch>

# Production auto-deploy
git push origin prod

# Optional: monitor workflow state
gh run list --workflow deploy-test.yml
gh run list --workflow deploy-prod.yml
```

Implementation details:
- `deploy-test.yml` (branches-ignore: `prod`) deploys using Docker Compose via `deployment/scripts/deploy-test.sh`.
  - Strictly one Compose project: `zeroqwait`.
  - Strict frontend endpoint: `http://localhost:3000` (no random/ephemeral frontend host ports).
- `deploy-prod.yml` (branch: `prod`) runs local image pipeline + applies K8s manifests + rollout checks in `zeroqwait`.

### LLM Setup (Ollama)

- Ollama runs in K8s namespace `llm` via Helm chart (ollama-1.38.0, image `ollama/ollama:latest`)
- **GPU**: NVIDIA GeForce RTX 5070 Ti (16GB VRAM), CUDA 13.0, Driver 580.126.09
- **Persistent storage**: 50Gi PVC (`ollama-data-pvc`, local-path) mounted at `/root/.ollama`
- Internal URL: `http://ollama.llm.svc.cluster.local:11434/v1` (ClusterIP, used by backend)
- External URL: `http://192.168.2.134:30002/v1` (NodePort, for debugging only)
- Models: `qwen3:14b-q4_K_M` (~8-9GB, Q4_K_M quantized, GPU-only via `num_gpu=-1`, primary)
- Config: `OLLAMA_URL` and `MODEL_NAME` in backend-configmap
- **Model repull required** after PVC data loss: `sudo kubectl exec deployment/ollama -n llm -- ollama pull qwen3:14b-q4_K_M`

---

## 10. Stabilization Fixes Applied (2026-02-24)

### Fix 1: pydantic-ai API Compatibility

- **Issue**: `AttributeError: 'AgentRunResult' has no attribute 'data'`
- **Root Cause**: pydantic-ai 0.8.1 changed `result.data` → `result.output`
- **Fix**: Updated `agent_logic.py` to use `result.output.response`

### Fix 2: LLM Response Timeout

- **Issue**: `asyncio.TimeoutError` on first query
- **Root Cause**: gpt-oss:20b (now replaced by qwen3:14b-q4_K_M) took ~120-150s for initial inference
- **Fix**: Increased `asyncio.wait_for` timeout from 90s to 300s

### Fix 3: Database Serialization

- **Issue**: `ProgrammingError` saving chat history
- **Root Cause**: SQLAlchemy tried to save complex `MasterResponse` Pydantic objects
- **Fix**: `db_interface.add_message_to_history` now coerces to string, extracting `.response` if available

### Fix 4: Model Pre-warming

- **Issue**: ~90s stall on first request (downloading all-MiniLM-L6-v2)
- **Fixes**:
  - Dockerfile: `RUN` step bakes model into image
  - `main.py`: eager `import agent_logic` at top level
  - `agent_logic.py`: monkey-patch `json.load` during init to handle `KeyError: '__version__'` in sentence-transformers v0.2.5.1

### Fix 5: Clean Rebuild

- `docker build --no-cache` to purge `__pycache__` artifacts

### Fix 6: AI Agent Greeting Consistency (2026-03-06)

- **Issue**: Agent returned generic greeting ("Hello! I'm ZeroQ. How can I help you today?") instead of presenting the three core features
- **Root Cause**: All four greeting locations (frontend welcome, backend prefilter, backend fallback, backend conversation agent) had inconsistent/vague messages
- **Fix**: Standardized all four locations to present the exact same three features:
  1. Register a Shop
  2. Search for Shops (AI-powered queue)

### Fix 7: Ollama Model Persistence & K8s Optimizations (2026-03-06)

- **Issue**: `gpt-oss:20b` model returned 404 (not found on Ollama), AI agent fell back to generic responses
- **Root Cause**: Ollama Helm deployment used `emptyDir` volume for `/root/.ollama`; pod restart ~8 days prior wiped the 13.8GB model
- **Fixes**:
  1. Created 50Gi PVC (`ollama-data-pvc`, local-path StorageClass) in `llm` namespace
  2. Patched Ollama deployment to mount PVC instead of `emptyDir` at `/root/.ollama`
  3. Re-pulled `gpt-oss:20b` model into persistent storage (later replaced by `qwen3:14b-q4_K_M`)
  4. Cleaned up 3 stale Ollama pods (UnexpectedAdmissionError, ContainerStatusUnknown)
  5. Changed `OLLAMA_URL` from NodePort (`http://<runner-host-ip>:30002/v1`) to cluster-internal DNS (`http://ollama.llm.svc.cluster.local:11434/v1`) for lower latency
  6. Added backend health probes (liveness + readiness on `/api/agent/health`)
  7. Bumped backend resources to 2Gi/1CPU request, 4Gi/2CPU limit
  8. Added ASR service resource limits (2Gi/1CPU request, 4Gi/2CPU limit)
  9. Added `storageClassName: local-path` to Redis PVC, increased to 5Gi
  10. Added `zeroqwait.com` + `*.zeroqwait.com` to Traefik ingress TLS
- **Files changed**: `k8s-manifests/ollama-pvc.yaml` (new), `k8s-manifests/backend-deployment.yaml`, `k8s-manifests/backend-configmap.yaml`, `k8s-manifests/ingress-traefik.yaml`, `k8s-manifests/redis-pvc.yaml`, `k8s-manifests/asr-deployment.yaml`
- **Key lesson**: Ollama Helm default uses `emptyDir` — always patch to PVC for model persistence
  3. Ask about our Products
6. **Backend Docker image**: Replace hostPath + `pip install uv && uv sync` on every restart with a pre-built Docker image (current startup ~10min).
7. **Image versioning**: Replace `latest` tags on frontend/ASR with semver tags for reproducibility.
8. **Static uploads persistence**: Backend `/app/static/uploads` uses `emptyDir` — should use PVC to survive pod restarts.
- **Files changed**: `MasterAIAgent.tsx` (initial chatHistory), `agent_logic.py` (greeting prefilter, conversation fallback, conversation agent system prompt)

### Fix 8: Voice Consistency + Streaming Latency (2026-04-06)

- **Issue**: Users heard inconsistent voices across responses and noticed slow voice response progression.
- **Root Causes**:
  1. Multiple voice synthesis paths existed in frontend (`speechSynthesis` in `useVoiceInterface` vs backend Qwen TTS in master agent flow), creating inconsistent voice output across app surfaces.
  2. Conversation streaming synthesized every sentence independently, increasing per-turn TTS round trips and making timbre/prosody vary between short segments.
- **Fixes**:
  1. Unified frontend TTS path by routing `useVoiceInterface` speech output through backend `/api/voice/tts` (Qwen3-TTS, voice `Vivian`) instead of browser `speechSynthesis`.
  2. Added lightweight backend TTS response cache (in-memory, SHA-256 keyed) in `agent_logic.py` to reuse repeated sentence audio.
  3. Updated conversation paired-streaming to emit the first sentence quickly, then coalesce subsequent sentences into larger voice chunks before TTS to reduce request count and stabilize perceived voice consistency.
  4. Added fast regex search intent prefilter (obvious `find/search/near me` queries) to reduce unnecessary analyzer LLM calls and improve response start time.
- **Files changed**: `backend/agent_logic.py`, `frontend/src/hooks/useVoiceInterface.tsx`

---

## 11. Known Issues & Next Steps

### Active Issues

1. **Semantic cache `__version__` errors**: `SemanticCache.set()` and `.get()` still throw `Failed to set cache: '__version__'` because the `json.load` monkey-patch only covers model initialization, not subsequent `encode()` calls. The semantic cache effectively doesn't work, but the agent functions normally without it. Fix: extend the monkey-patch scope or upgrade sentence-transformers.
2. **Duplicate `except` block**: `SemanticCache.set()` (around line 97-109 in `agent_logic.py`) has two `except Exception` clauses — the second is dead code.

### AaaS Transition Roadmap (2026-04-10)

> **Deployment policy**: All phases are validated via the single local Docker Compose deployment path (`deploy-test.yml` / `deployment/scripts/deploy-test.sh`) first. Production deployment to `zeroqwait.com` only after explicit approval.

#### Phase 1: LangGraph Foundation (Current)
- [ ] Add `langgraph`, `langgraph-checkpoint-postgres`, `langchain-ollama`, `langchain-core` to `pyproject.toml`
- [ ] Create `backend/agents/` package: `state.py`, `checkpoints.py`
- [ ] Implement `AgentState` TypedDict with `tenant_id`, `user_id`, message history
- [ ] Set up `AsyncPostgresSaver` checkpoint persistence
- [ ] Create basic Supervisor graph (classify intent → respond) — no sub-agents yet
- [ ] Add `routers/agent_v2.py` with `/api/v2/agent/chat` and `/api/v2/agent/chat/stream`
- [ ] Verify LangGraph ↔ Ollama integration (qwen3:14b-q4_K_M via langchain-ollama)
- [ ] **Test**: End-to-end owner chat → Supervisor responds via LangGraph

#### Phase 2: Sub-Agent Graphs
- [ ] Implement Receptionist sub-agent graph (queue tools, service discovery)
- [ ] Implement Finance sub-agent graph (analytics, revenue reports)
- [ ] Implement HR sub-agent graph (employees, shifts, scheduling)
- [ ] Wire Supervisor → sub-agent routing via conditional edges
- [ ] Add `tenant_id` injection + validation (agents cannot cross tenant boundaries)
- [ ] **Test**: Owner commands route correctly to sub-agents and return results

#### Phase 3: MCP Tool Servers
- [ ] Create `mcps/booking/server.py` — wraps `db_interface` queue/service methods
- [ ] Create `mcps/finance/server.py` — wraps analytics/revenue methods
- [ ] Create `mcps/hr/server.py` — wraps employee/shift methods
- [ ] Wire sub-agent `ToolNode`s to call MCP servers instead of direct DB calls
- [ ] Add Dockerfiles + K8s manifests for MCP pods (optional — can run in-process initially)
- [ ] **Test**: Tool calls flow through MCP layer correctly

#### Phase 4: Human-in-the-Loop Approvals
- [ ] Define HITL action categories (queue close, schedule change, refund, etc.)
- [ ] Add `interrupt_before` breakpoints to sub-agent graphs for high-impact actions
- [ ] Implement `POST /api/v2/agent/approve` endpoint (resume graph from checkpoint)
- [ ] SSE event: `{type: 'approval_required', action, details}`
- [ ] **Test**: Agent pauses at breakpoint → owner approves → action executes

#### Phase 5: Frontend Agent Inbox
- [ ] Create `features/agent-inbox/` directory: `AgentInbox.tsx`, `AgentChat.tsx`, `AgentFeed.tsx`, `ApprovalCard.tsx`
- [ ] Implement owner ↔ Supervisor SSE chat interface
- [ ] Implement approval card UI (approve/reject buttons + action summary)
- [ ] Implement chronological agent activity feed (WebSocket updates)
- [ ] Wire into existing shop dashboard navigation
- [ ] **Test**: Full end-to-end owner experience in test environment

#### Phase 6: Migration & Cutover
- [ ] Migrate customer-facing chat from pydantic-ai → LangGraph Receptionist (optional — can keep dual-stack)
- [ ] Update landing page `MasterAIAgent.tsx` to use v2 endpoints
- [ ] Performance testing: checkpoint latency, concurrent tenants, GPU utilization
- [ ] **Production deploy** after test environment validation + explicit approval

### Recommended Near-Term Fixes (Carry-Over)
1. **Fix semantic cache**: Upgrade sentence-transformers or extend monkey-patch
2. **Reset password endpoint**: Currently returns 501 (not implemented)
3. **Shop subdomain routing**: Verify `*.192.168.2.134.nip.io` resolution

---

## 12. Key API Endpoints

### Agent (Legacy — Customer-Facing)

| Method | Path                            | Description        |
| ------ | ------------------------------- | ------------------ |
| POST   | `/api/agent/master/chat`        | Synchronous chat   |
| POST   | `/api/agent/master/chat/stream` | SSE streaming chat |
| GET    | `/api/agent/health`             | Agent health check |

### Agent v2 (New — Owner-Facing, LangGraph)

| Method | Path                               | Description                              |
| ------ | ---------------------------------- | ---------------------------------------- |
| POST   | `/api/v2/agent/chat`               | Synchronous owner chat                   |
| POST   | `/api/v2/agent/chat/stream`        | SSE streaming owner chat                 |
| POST   | `/api/v2/agent/approve`            | Approve/reject HITL action               |
| GET    | `/api/v2/agent/history`            | Get agent conversation history           |
| GET    | `/api/v2/agent/pending`            | Get pending approval actions             |
| GET    | `/api/v2/agent/health`             | LangGraph agent health check             |

### Voice

| Method | Path                    | Description                   |
| ------ | ----------------------- | ----------------------------- |
| POST   | `/api/voice/transcribe` | Whisper ASR (multipart audio) |
| POST   | `/api/voice/tts`        | Qwen TTS (returns MP3)        |
| GET    | `/api/voice/tts/health` | TTS health check              |

### Auth

| Method | Path                        | Description             |
| ------ | --------------------------- | ----------------------- |
| POST   | `/api/auth/token`           | Login (OAuth2 password) |
| POST   | `/api/auth/forgot-password` | Password reset email    |

### Shops & Queues

| Method | Path                           | Description          |
| ------ | ------------------------------ | -------------------- |
| GET    | `/api/shops/`                  | List all shops       |
| GET    | `/api/shops/my-shops`          | Current user's shops |
| GET    | `/api/shops/s/{slug}`          | Shop by vanity URL   |
| POST   | `/api/queues/shop/{id}/join`   | Join queue           |
| GET    | `/api/queues/shop/{id}/active` | Active queue         |
| POST   | `/api/queues/{id}/call-next`   | Call next customer   |

---

## 13. Environment Variables (Backend)

| Variable          | Default                                                          | Description         |
| ----------------- | ---------------------------------------------------------------- | ------------------- |
| `OLLAMA_URL`      | `http://localhost:11434/v1`                                      | Ollama API endpoint |
| `MODEL_NAME`      | `llama3.2:latest`                                                | LLM model name      |
| `DB_HOST`         | `localhost`                                                      | PostgreSQL host     |
| `DB_PORT`         | `5432`                                                           | PostgreSQL port     |
| `DB_NAME`         | `zeroqwait`                                                      | Database name       |
| `DB_USER`         | `postgres`                                                       | Database user       |
| `DB_PASSWORD`     | `password`                                                       | Database password   |
| `REDIS_HOST`      | `localhost`                                                      | Redis host          |
| `REDIS_PORT`      | `6379`                                                           | Redis port          |
| `FRONTEND_URL`    | —                                                                | CORS allowed origin |
| `ASR_SERVICE_URL` | `http://voice-mcp.zeroqwait.svc.cluster.local:8881/transcribe`   | Whisper ASR via voice-mcp |
| `TTS_SERVICE_URL` | `http://voice-mcp.zeroqwait.svc.cluster.local:8881`              | Qwen3-TTS via voice-mcp   |
| `JWT_SECRET_KEY`  | —                                                                | JWT signing key     |
| `COOKIE_DOMAIN`   | —                                                                | Auth cookie domain  |

---

## 14. Testing

```bash
# Remote end-to-end agent test
cd backend && python test_live.py

# Quick health checks
curl -sk https://zeroqwait.com/api/agent/health
curl -sk https://zeroqwait.com/api/voice/tts/health

# Test ingress checks
curl -sk http://192.168.2.134.nip.io/api/agent/health
curl -sk http://192.168.2.134.nip.io/api/voice/tts/health

# Manual agent chat test
curl -sk -X POST https://zeroqwait.com/api/agent/master/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Hello", "session_id": "test_1"}'
```

---

## 15. Coding Conventions

- **Backend**: Python 3.9+, type hints, async/await, Pydantic models for validation
- **Frontend**: TypeScript strict, functional components, React hooks, MUI v7
- **State**: React Context (AuthContext, ShopContext, ThemeContext) — no Redux
- **API calls**: axios with interceptors (frontend), httpx (backend-to-service)
- **Naming**: snake_case (Python), camelCase (TypeScript), kebab-case (file names in frontend components)
- **Dependency management**: `uv` (Python, via pyproject.toml + uv.lock), `npm` (frontend)

---

## 16. DevOps Pipeline (Local-Only Registry + Argo CD)

### Goal

Use a **local Docker registry only** (no cloud image registry), persist image blobs on SSD, and keep a complete, visual GitOps deployment history.

### Standard Stack

- **Registry**: local Docker Registry v2 on `localhost:5000`
- **Registry storage path**: `/media/neekrishrichu/One Touch/projects/zeroqwait` (SSD)
- **Registry UI**: `http://localhost:5080` (joxit/docker-registry-ui, visual tag browser + delete)
- **GitOps**: Argo CD v3.3.6 in `argocd` namespace
- **Argo CD UI**: `https://localhost:8443` (port-forward: `sudo kubectl port-forward svc/argocd-server -n argocd 8443:443`)
- **Argo CD login**: user `admin`, initial password in `argocd-initial-admin-secret` K8s secret
- **Manifest source**: `k8s-manifests` (Kustomize root)
- **Version policy**: keep only **last 10 tags** per service in registry

### Pipeline Scripts (authoritative)

- `deployment/scripts/setup-local-registry.sh`
  - Starts/recreates registry container with delete API enabled
  - Uses `deployment/registry/config.yml`
  - Mounts SSD path for image storage
- `deployment/scripts/setup-argocd-gitops.sh`
  - Installs Argo CD and creates `zeroqwait` Application
- `deployment/scripts/run-local-pipeline.sh`
  - Runs backend + frontend tests for each run
  - Builds/pushes versioned images (`vYYYYMMDDHHMMSS-<sha>`)
  - Updates image tags in K8s deployment manifests
  - Optionally commits manifest updates
  - Optionally triggers Argo sync
- `deployment/scripts/prune-registry-tags.sh`
  - Enforces retention: keeps only latest 10 tags per repo

### Services under versioned image pipeline

- `backend`
- `frontend`
- `asr-service`
- `tts-service`
- `voice-mcp`

### Visual operations

- **Argo CD UI** is the source of truth for visual deployment tracking:
  - Sync status, health, drift detection, revision history, rollback points
- Local CI runner can be used with `.github/workflows/local-devops-pipeline.yml`

### Safety constraints

- Do not replace protected AI/TTS models while introducing pipeline changes.
- Keep TTS voice `Vivian`, service port `8880`, and Qwen3-TTS engine unchanged.
- Do not switch registry to cloud unless explicitly approved.

### Branch-Based Deployment Policy

- `prod` branch push → **Production deploy** to `https://zeroqwait.com` via `.github/workflows/deploy-prod.yml`
- Any non-`prod` branch push → **Local compose deploy** to `http://localhost:3000` via `.github/workflows/deploy-test.yml`
- Legacy auto-deploy workflows are manual-only (`workflow_dispatch`) to avoid conflicts.

### Assistant Execution Rules (Mandatory)

- **Single stack rule**: Use only one Docker Compose project for local/non-prod work: `zeroqwait`. Do not create `zeroqwait-test` (or any other parallel project) unless explicitly approved by the user.
- **Strict localhost port rule**: Frontend must remain on `http://localhost:3000` for local/non-prod Compose deployment. Do not switch to random or ephemeral frontend host ports.
- **Commit and push rule**: After completing code changes and verification, always create a commit and push to the active branch so test deployment workflows can run.

---

## CRM Integration (Odoo ERP)

### Architecture
- Odoo 17 runs as a Docker service (`odoo`) on port 8069
- FastCuts communicates via XML-RPC at `http://odoo:8069/xmlrpc/2/object`
- Auth: Single service credential (admin/admin) — users never log into Odoo directly
- CRM tools live in: `backend/agents/tools/odoo_tools.py`
- XML-RPC client: `backend/integrations/odoo_client.py`
- Multi-tenancy: Each shop maps to a unique `res.company` in Odoo via `shops.odoo_company_id`

### CRM Capabilities
**Read operations:**
- Contacts (list, search)
- Companies/organizations
- Leads/opportunities (list, filter by stage)
- Pipeline summary (grouped by stage with revenue)
- Invoices, payments, products, revenue summary
- Account balances, journal entries
- Pipeline stages list

**Write operations:**
- Create contact (with optional company, email, phone)
- Update contact (email, phone, city, name)
- Create lead/opportunity (with revenue, description)
- Move lead to different pipeline stage
- Add notes to leads
- Create/confirm invoices
- Register payments

### Routing
- Owner messages with CRM intent are classified as `"crm"` by `classify_intent()`
- CRM keywords: leads, contacts, clients, companies, pipeline, deals, opportunities, notes, tasks, accounting, journal, ledger, product, catalog, odoo
- The `execute_plan()` node calls `_run_crm_agent()` for CRM-classified intent
- CRM responses go through the same `synthesize_response()` passthrough as other specialists

### Environment variables required
- `ODOO_URL` — defaults to `http://odoo:8069`
- `ODOO_DB` — defaults to `odoo`
- `ODOO_USER` — defaults to `admin`
- `ODOO_PASSWORD` — defaults to `admin`

### Adding new CRM tool functions
1. Add method to `backend/integrations/odoo_client.py` (OdooClient class)
2. Add async wrapper to `backend/agents/tools/odoo_tools.py`
3. Add keyword detection in `_run_crm_agent()` in `supervisor.py`
4. No LangChain wrappers needed — plain async Python functions only

### What is NOT in this project
- No Supabase — database is plain SQLAlchemy + PostgreSQL
- No OpenAI — LLM is local Ollama (qwen3:14b-q4_K_M)
- No Twenty CRM — fully removed, Odoo handles all CRM
- No LangChain Tool/StructuredTool wrappers anywhere in agents/tools/
