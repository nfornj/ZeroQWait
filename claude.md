# ZeroQwait — Project Rules & Context

> **Last updated**: 2026-03-06
> **Live URL**: https://zeroqwait.com (self-hosted, also http://192.168.2.88.nip.io)

---

## 1. What Is ZeroQwait

A **universal queue management platform** where service businesses (barbers, salons, clinics, auto shops, etc.) register, and customers can discover them, join queues remotely, and view real-time wait times — all powered by an AI agent assistant.

### Core User Flows

1. **Customer** → Lands on marketing page → Interacts with AI agent (text/voice) → Finds shops → Joins queue → Gets position updates.
2. **Shop Owner** → Signs up → Registers shop → Manages queue dashboard → Views analytics.
3. **Employee** → Logs in → Manages individual queue from employee dashboard.

---

## 2. Tech Stack

| Layer                       | Technology                               | Details                                                             |
| --------------------------- | ---------------------------------------- | ------------------------------------------------------------------- |
| **Frontend**                | React 18 + TypeScript                    | MUI v7.3.7, react-router-dom v6, axios                              |
| **Backend**                 | FastAPI 0.128.0 (Python 3.9+)            | Uvicorn 0.39.0, SQLAlchemy 2.0.44                                   |
| **Database**                | PostgreSQL 15                            | Via K8s StatefulSet (prod DB: `fastcuts_db`, user: `fastcuts_user`) |
| **Cache**                   | Redis 5.0.1                              | Session history, category cache, rate limiting                      |
| **AI/LLM**                  | pydantic-ai 0.8.1 + Ollama               | Model: `gpt-oss:20b` (13.8GB, MXFP4 quantized)                      |
| **Embeddings**              | sentence-transformers (all-MiniLM-L6-v2) | Semantic cache for query analysis                                   |
| **Voice ASR**               | Whisper (via `asr_service/`)             | GPU-accelerated, separate K8s pod                                   |
| **Voice TTS**               | Qwen TTS at `192.168.2.88:8880`          | `/v1/audio/speech` endpoint, voice: `serena`                        |
| **Container Orchestration** | K3s (lightweight K8s)                    | Namespace: `zeroqwait`, Traefik ingress                             |
| **Deployment**              | Self-hosted Linux server                 | `neekrishrichu@192.168.2.88`                                        |

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
│   │   │   └── shop-dashboard/      # Owner dashboard, analytics, queue management
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
│   ├── agent_logic.py                # AI agent: MasterAgent, tools, query analysis (1314 lines)
│   ├── db_interface.py               # Database abstraction layer (SQLAlchemy, 853 lines)
│   ├── database.py                   # Engine, SessionLocal, connection config
│   ├── models.py                     # Re-exports all SQLAlchemy models
│   ├── schemas.py                    # Re-exports all Pydantic schemas
│   ├── redis_client.py               # Redis wrapper (caching, sessions, rate limits)
│   ├── websocket_manager.py          # WebSocket connection manager for real-time updates
│   ├── scheduler.py                  # Background analytics scheduler
│   ├── permissions.py                # Authorization helpers
│   ├── tier_limits.py                # Subscription tier enforcement
│   ├── Dockerfile                    # Python 3.9-slim, uv sync, sentence-transformer pre-warm
│   ├── routers/                      # Legacy/shared API routers
│   │   ├── agent.py                  # /api/agent/master/chat, /chat/stream
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
├── asr_service/                      # Whisper ASR microservice
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── k8s-manifests/                    # Kubernetes deployment configs
│   ├── backend-deployment.yaml       # Backend pod (hostPath mount, init containers)
│   ├── backend-configmap.yaml        # Environment variables
│   ├── backend-secret.yaml           # DB password, JWT secret
│   ├── frontend-deployment.yaml
│   ├── postgres-statefulset.yaml     # PostgreSQL with PVC
│   ├── redis-statefulset.yaml        # Redis with PVC
│   ├── ingress-traefik.yaml          # Traefik ingress (wildcard TLS)
│   └── asr-deployment.yaml           # ASR service
│
├── deployment/
│   ├── scripts/
│   │   ├── deploy-k8s.sh            # Main K8s deployment script
│   │   └── deploy-and-sync.sh       # Git push + SSH sync + deploy (uses llama3 for commit msgs)
│   └── docker/                       # Docker build configs
│
├── docker-compose.yml                # Local dev (backend:8000, frontend:3000)
├── docker-compose.prod.yml           # Production (backend:8001, frontend:3001, postgres)
└── claude.md                         # THIS FILE — project context for AI assistants
```

---

## 5. AI Agent Architecture

### Three Core Features (User-Facing)

The AI agent (ZeroQ) always presents **exactly three capabilities** to users:

1. **Register a Shop** — Set up your business on our platform
2. **Search for Shops** — Find services nearby and join an AI-powered queue
3. **Ask about our Products** — Pricing, features, and how it all works

These three items must appear consistently across:
- Frontend welcome message (`MasterAIAgent.tsx` initial `chatHistory`)
- Backend greeting prefilter (`agent_logic.py` `_GREETING_RE` handler in `stream_chat()`)
- Backend conversation agent fallback (`get_conversational_response()` exception handler)
- Backend conversation agent system prompt (rules section)

**Rule**: Never change the wording of these three features without updating all four locations.

### Overview

The AI agent (`agent_logic.py`) is powered by **pydantic-ai 0.8.1** and runs on a self-hosted **gpt-oss:20b** model via Ollama. It uses a structured output model (`MasterResponse`) to ensure reliable tool coordination.

### Key Components

| Component              | Purpose                                                                                      |
| ---------------------- | -------------------------------------------------------------------------------------------- |
| `UnifiedQueryAnalyzer` | Single-pass LLM extractor: intent (CONVERSATION/ACTION/UNCLEAR), search terms, city, near_me |
| `SemanticCache`        | Sentence-transformer embeddings cache (all-MiniLM-L6-v2, cosine threshold 0.92)              |
| `CategoryManager`      | Dynamic category system — zero hardcoded categories, all database-driven with Redis cache    |
| `MasterAgent`          | Main orchestrator — routes queries, invokes tools, manages context                           |
| `MasterResponse`       | Pydantic output model with `reasoning` and `response` fields                                 |

### Agent Tools

| Tool                 | Function                                             |
| -------------------- | ---------------------------------------------------- |
| `search_shops`       | Search businesses by category/city/coordinates/query |
| `join_queue`         | Add customer to a shop's queue                       |
| `get_wait_time`      | Check queue length and estimated wait                |
| `check_queue_status` | Check position by ticket ID                          |
| `check_pricing`      | Navigate UI to pricing section                       |
| `see_features`       | Navigate UI to features section                      |
| `see_faq`            | Navigate UI to FAQ section                           |
| `see_testimonials`   | Navigate UI to testimonials                          |
| `start_registration` | Trigger sign-up wizard (shop_owner or customer)      |

### Direct Search Bypass

The agent has a **direct search bypass** — if the `UnifiedQueryAnalyzer` detects search terms, `near_me`, or a city, it calls `search_shops` directly without waiting for the LLM to decide. This overcomes local LLMs refusing to invoke tools when they feel they lack GPS data.

### Chat Flow

1. User message → Redis rate limit check (20/min per IP)
2. Server-side history loaded from Redis (last 10 messages)
3. `UnifiedQueryAnalyzer.analyze()` — single-pass intent/terms extraction
4. If search intent → direct bypass to `search_shops` tool
5. Otherwise → `pydantic-ai Agent.run()` with 300s timeout
6. Response + actions returned; history persisted to Redis + PostgreSQL
7. On validation/timeout errors → fallback to conversational response

### Streaming (SSE)

- Endpoint: `POST /api/agent/master/chat/stream`
- Events: `{type: 'text', content}`, `{type: 'actions', actions}`, `[DONE]`
- Frontend parses SSE via `ReadableStream` API and renders token-by-token

---

## 6. Voice Pipeline

```
[Browser Mic] → useAudioRecorder (blob) → POST /api/voice/transcribe → Whisper ASR pod
     → transcribed text → MasterAgent.chat() → response text
     → POST /api/voice/tts → Qwen TTS (192.168.2.88:8880) → MP3 audio → AudioContext playback
```

- ASR: Whisper model in dedicated K8s pod (`asr-service`)
- TTS: Qwen TTS running as host service on port 8880 (voice: `serena`)
- Frontend queues TTS sentences and plays them sequentially

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

### Remote Server

- **Host**: `neekrishrichu@192.168.2.88` (Linux x86_64, Ubuntu 24.04)
- **K8s**: K3s v1.34.3 (lightweight Kubernetes)
- **Docker**: v29.2.0
- **KUBECONFIG**: `/etc/rancher/k3s/k3s.yaml`
- **App path**: `/home/neekrishrichu/apps/zeroqwait`
- **Code deployment**: hostPath mount (backend code mounted directly from server filesystem)

### K8s Layout (namespace: `zeroqwait`)

| Pod             | Service Type         | Port Mapping              |
| --------------- | -------------------- | ------------------------- |
| `backend-*`     | NodePort             | 30000 → 8000              |
| `frontend-*`    | NodePort             | 30001 → 3000 (nginx → 80) |
| `postgres-0`    | ClusterIP (headless) | 5432                      |
| `redis-0`       | ClusterIP (headless) | 6379                      |
| `asr-service-*` | ClusterIP            | 8000                      |

### Ingress (Traefik)

- Base: `192.168.2.88.nip.io` → `/api` → backend, `/` → frontend
- Wildcard: `*.192.168.2.88.nip.io` (shop subdomains)
- TLS: Self-signed wildcard cert in `zeroqwait-wildcard-tls` secret

### Deployment Commands

```bash
# Full deploy from local machine (git push + sync + K8s deploy)
./deployment/scripts/deploy-and-sync.sh

# Rebuild backend image on remote
ssh neekrishrichu@192.168.2.88 "cd /home/neekrishrichu/apps/zeroqwait && docker build --no-cache -t zeroqwait-backend ./backend"

# Check pod status
ssh neekrishrichu@192.168.2.88 "sudo kubectl get pods -n zeroqwait"

# View backend logs
ssh neekrishrichu@192.168.2.88 "sudo kubectl logs -f deployment/backend -n zeroqwait"

# Restart backend
ssh neekrishrichu@192.168.2.88 "sudo kubectl rollout restart deployment/backend -n zeroqwait"
```

### LLM Setup (Ollama)

- Ollama exposed at `http://192.168.2.88:30002/v1` (OpenAI-compatible)
- Models: `gpt-oss:20b` (13.8GB, primary), `llama3.2:latest` (2.0GB, fallback/commit messages)
- Config: `OLLAMA_URL` and `MODEL_NAME` in backend-configmap

---

## 10. Stabilization Fixes Applied (2026-02-24)

### Fix 1: pydantic-ai API Compatibility

- **Issue**: `AttributeError: 'AgentRunResult' has no attribute 'data'`
- **Root Cause**: pydantic-ai 0.8.1 changed `result.data` → `result.output`
- **Fix**: Updated `agent_logic.py` to use `result.output.response`

### Fix 2: LLM Response Timeout

- **Issue**: `asyncio.TimeoutError` on first query
- **Root Cause**: gpt-oss:20b takes ~120-150s for initial inference
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
  3. Ask about our Products
- **Files changed**: `MasterAIAgent.tsx` (initial chatHistory), `agent_logic.py` (greeting prefilter, conversation fallback, conversation agent system prompt)

---

## 11. Known Issues & Next Steps

### Active Issues

1. **Semantic cache `__version__` errors**: `SemanticCache.set()` and `.get()` still throw `Failed to set cache: '__version__'` because the `json.load` monkey-patch only covers model initialization, not subsequent `encode()` calls. The semantic cache effectively doesn't work, but the agent functions normally without it. Fix: extend the monkey-patch scope or upgrade sentence-transformers.
2. **Duplicate `except` block**: `SemanticCache.set()` (around line 97-109 in `agent_logic.py`) has two `except Exception` clauses — the second is dead code.

### Recommended Next Steps

1. **Fix semantic cache**: Either permanently patch `json.load` for the sentence-transformers `__version__` bug, or pin a version that doesn't have this issue.
2. **Frontend streaming polish**: Monitor SSE responsiveness now that backend is stable.
3. **Extended tool testing**: Verify `join_queue` and `search_shops` correctly update UI state in real-time via SSE stream.
4. **Reset password endpoint**: Currently returns 501 (not implemented).
5. **Shop subdomain routing**: Verify `*.192.168.2.88.nip.io` subdomains correctly resolve to individual shop pages.

---

## 12. Key API Endpoints

### Agent

| Method | Path                            | Description        |
| ------ | ------------------------------- | ------------------ |
| POST   | `/api/agent/master/chat`        | Synchronous chat   |
| POST   | `/api/agent/master/chat/stream` | SSE streaming chat |
| GET    | `/api/agent/health`             | Agent health check |

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
| `ASR_SERVICE_URL` | `http://asr-service.zeroqwait.svc.cluster.local:8000/transcribe` | Whisper ASR         |
| `TTS_SERVICE_URL` | `http://192.168.2.88:8880`                                       | Qwen TTS            |
| `JWT_SECRET_KEY`  | —                                                                | JWT signing key     |
| `COOKIE_DOMAIN`   | —                                                                | Auth cookie domain  |

---

## 14. Testing

```bash
# Remote end-to-end agent test
cd backend && python test_live.py

# Quick health checks from remote
curl -sk https://192.168.2.88.nip.io/api/agent/health
curl -sk https://192.168.2.88.nip.io/api/voice/tts/health

# Manual agent chat test
curl -sk -X POST https://192.168.2.88.nip.io/api/agent/master/chat \
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
