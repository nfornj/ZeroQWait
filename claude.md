# ZeroQwait — Project Rules & Context

> **Last updated**: 2026-04-05
> **Live URL**: https://zeroqwait.com (self-hosted, also http://192.168.2.88.nip.io)

---

## 0. AI Assistant Safety Rules (MANDATORY — Read First)

> **These rules apply to any AI assistant (GitHub Copilot, Claude, etc.) working on this codebase.**

### 0.1 No Unauthorized Model or Service Changes

**NEVER change the following without explicit user permission:**

| Protected Artefact | Current Value | Why It Matters |
| ---- | ---- | ---- |
| LLM model | `gpt-oss:20b` via Ollama | Swapping models breaks agent behaviour and costs GPU re-pull time |
| TTS engine | Qwen3-TTS (`Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`) | Kokoro / Coqui incident on 2026-02-14 required emergency rollback |
| TTS voice | `Vivian` | Voice is a brand experience choice |
| TTS port | `8880` | Ingress and backend config hard-wired to this port |
| ASR engine | faster-whisper (`medium`) | GPU compute budget depends on this model size |
| Embedding model | `all-MiniLM-L6-v2` | Semantic cache keys are tied to these embeddings |
| Database engine | PostgreSQL 15 | Alembic migrations target this version |
| Orchestration | K3s namespace `zeroqwait` | All K8s manifests target this namespace |

**Before swapping any model/engine/service**: stop, surface the proposal to the user, explain the tradeoffs, and wait for explicit approval.

### 0.2 No Silent Architectural Changes

The following changes require user approval before implementation:

- Replacing a service (e.g. switching from Qwen3-TTS → any other TTS)
- Changing default models in K8s ConfigMaps or Dockerfiles
- Adding new external service dependencies (new APIs, new LLM providers)
- Modifying authentication or authorization logic
- Changing database schema in ways that skip Alembic migrations
- Modifying `backend/agent_logic.py` intent routing or tool definitions substantially

### 0.3 Allowed Without Approval

- Bug fixes that do not change model outputs (e.g. fixing a wrong env var default)
- Performance optimizations that keep the same service/model
- Creating new microservices that are additive (e.g. MCP wrapper)
- Updating timeouts, retry counts, connection pool sizes
- Adding logging, metrics, or health-check endpoints

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
| **Voice TTS**               | Qwen3-TTS 1.7B (via `tts_service/`)     | `/v1/audio/speech` OpenAI-compatible, voice: `Vivian`, port 8880 — **DO NOT REPLACE** (see §6) |
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
- Backend GREETING intent handler in `stream_chat()` and `chat()`
- Backend conversation agent fallback (`get_conversational_response()` exception handler)
- Backend conversation agent system prompt (rules section)

**Rule**: Never change the wording of these three features without updating all four locations.

### Overview

The AI agent (`agent_logic.py`) is powered by **pydantic-ai 0.8.1** and runs on a self-hosted **gpt-oss:20b** model via Ollama. It uses a structured output model (`MasterResponse`) to ensure reliable tool coordination.

### Key Components

| Component              | Purpose                                                                                      |
| ---------------------- | -------------------------------------------------------------------------------------------- |
| `UnifiedQueryAnalyzer` | Single-pass LLM intent classifier: 6 intents (GREETING/REGISTRATION/SEARCH/PLATFORM_INFO/CONVERSATION/UNCLEAR) with structured `IntentAnalysis` output |
| `IntentAnalysis`       | Pydantic model: intent, search_terms, city, near_me, specificity (VAGUE/SPECIFIC), platform_target, registration_type, context_updates |
| `SemanticCache`        | Sentence-transformer embeddings cache (all-MiniLM-L6-v2, cosine threshold 0.92)              |
| `CategoryManager`      | Dynamic category system — zero hardcoded categories, all database-driven with Redis cache    |
| `MasterAgent`          | Main orchestrator — routes queries by classified intent, invokes tools, manages context      |
| `MasterResponse`       | Pydantic output model with `reasoning` and `response` fields (used by master LLM fallback)  |

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

### Intent-Based Routing (Refactored 2026-03-08)

All intent detection is handled by a **single LLM intent classifier** (`UnifiedQueryAnalyzer.analyze()`) that returns an `IntentAnalysis` Pydantic model. No regex-based routing — the LLM classifies every message into one of 6 intents.

**Only exception**: `_CANCEL_REGISTRATION_RE` regex is kept inside the active-registration Redis block for low-latency cancel handling (user is frustrated mid-registration).

**Flow** (both `stream_chat()` and `chat()`):
1. **Active registration check** (Redis state) → if active, remind or cancel. Return early.
2. **LLM Intent Classification** → `UnifiedQueryAnalyzer.analyze()` returns `IntentAnalysis`
3. **Route by intent**:
   - `GREETING` → Canned greeting with 3 core features
   - `REGISTRATION` → Start `registration_agent` session, emit form_step
   - `SEARCH + VAGUE` → Ask "What type of service?" (no service type specified)
   - `SEARCH + SPECIFIC` → Direct `search_shops()` call with extracted terms/city
   - `PLATFORM_INFO` → Navigate to section (pricing/features/faq/testimonials) with `platform_target` normalization
   - `CONVERSATION` → Stream via `conversation_agent` (token-by-token with TTS)
   - `UNCLEAR` → Ask user for clarification, present 3 core features
   - Fallback → Master LLM agent run with tools (300s timeout)

**Active registration protection**: Before any processing, `stream_chat()` checks if a registration session exists in Redis. If so:
- Normal messages → Reminder to complete the form + re-emit form_step
- Cancel keywords (`_CANCEL_REGISTRATION_RE`) → Clears the session

**Registration state machine** (`registration_agent.py`):
- Steps (shop_owner): `account_type → email → username → password → shop_name → shop_type → shop_address → confirm → done`
- Steps (customer): `account_type → email → username → password → confirm → done`
- State persisted in Redis with 30-min TTL
- Each step validated server-side before advancing
- Frontend renders forms via `InlineRegistrationForm` component in chat bubbles

### Chat Flow

1. User message → Redis rate limit check (20/min per IP)
2. Server-side history loaded from Redis (last 10 messages)
3. **Active registration check** → if session exists, remind or cancel
4. **LLM intent classification** → `UnifiedQueryAnalyzer.analyze()` returns `IntentAnalysis`
5. **Intent-based routing** → GREETING/REGISTRATION/SEARCH/PLATFORM_INFO/CONVERSATION/UNCLEAR
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
| `tts-service-*` | ClusterIP            | 8880 (GPU-accelerated)    |
| `ollama-*`      | ClusterIP + NodePort | 11434 (ClusterIP), 30002 (NodePort) |

### Ingress (Traefik)

- Production: `zeroqwait.com` + `*.zeroqwait.com` (added 2026-03-06)
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

- Ollama runs in K8s namespace `llm` via Helm chart (ollama-1.38.0, image `ollama/ollama:latest`)
- **GPU**: NVIDIA GeForce RTX 5070 Ti (16GB VRAM), CUDA 13.0, Driver 580.126.09
- **Persistent storage**: 50Gi PVC (`ollama-data-pvc`, local-path) mounted at `/root/.ollama`
- Internal URL: `http://ollama.llm.svc.cluster.local:11434/v1` (ClusterIP, used by backend)
- External URL: `http://192.168.2.88:30002/v1` (NodePort, for debugging only)
- Models: `gpt-oss:20b` (13.8GB, MXFP4 quantized, primary)
- Config: `OLLAMA_URL` and `MODEL_NAME` in backend-configmap
- **Model repull required** after PVC data loss: `sudo kubectl exec deployment/ollama -n llm -- ollama pull gpt-oss:20b`

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

### Fix 7: Ollama Model Persistence & K8s Optimizations (2026-03-06)

- **Issue**: `gpt-oss:20b` model returned 404 (not found on Ollama), AI agent fell back to generic responses
- **Root Cause**: Ollama Helm deployment used `emptyDir` volume for `/root/.ollama`; pod restart ~8 days prior wiped the 13.8GB model
- **Fixes**:
  1. Created 50Gi PVC (`ollama-data-pvc`, local-path StorageClass) in `llm` namespace
  2. Patched Ollama deployment to mount PVC instead of `emptyDir` at `/root/.ollama`
  3. Re-pulled `gpt-oss:20b` model into persistent storage
  4. Cleaned up 3 stale Ollama pods (UnexpectedAdmissionError, ContainerStatusUnknown)
  5. Changed `OLLAMA_URL` from NodePort (`http://192.168.2.88:30002/v1`) to cluster-internal DNS (`http://ollama.llm.svc.cluster.local:11434/v1`) for lower latency
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
| `TTS_SERVICE_URL` | `http://192.168.2.88:8880`                                       | Qwen3-TTS            |
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
