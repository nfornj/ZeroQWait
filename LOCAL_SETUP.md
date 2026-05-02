# ZeroQwait — Local Setup Guide

> **For LLMs**: Read this file top to bottom and execute each numbered step in sequence.
> Every command block is ready to copy-paste into a terminal.
> The whole stack runs inside Docker — no Python or Node.js installation required.

---

## What You Are Running

ZeroQwait is an AI-powered operations platform for service businesses (barbershops, salons, etc.).  
It includes:

| Service | What it does | Local URL |
|---|---|---|
| **Frontend** | React app (owner dashboard + customer chat) | http://localhost:3000 |
| **Backend** | FastAPI REST + agent endpoints | http://localhost:8000 |
| **API Docs** | Interactive Swagger UI | http://localhost:8000/docs |
| **Odoo ERP** | CRM / invoicing (optional) | http://localhost:8069 |
| **booking-mcp** | AI tool server — queue & appointments | (internal only) |
| **finance-mcp** | AI tool server — revenue & analytics | (internal only) |
| **hr-mcp** | AI tool server — employees & shifts | (internal only) |
| **simulation** | Fake customers + barbers for live demo | (background worker) |
| **PostgreSQL** | Main database | localhost:5432 |
| **Redis** | Cache & sessions | localhost:6379 |

---

## Prerequisites

Install these before starting. Check each one with the verification command.

### 1. Docker Desktop (or Docker Engine + Compose plugin)

- Download: https://www.docker.com/products/docker-desktop/
- Verify:
  ```bash
  docker --version
  docker compose version
  ```
  Both commands must succeed. You need Docker Compose v2 (the `docker compose` subcommand, not `docker-compose`).

### 2. Git

- Download: https://git-scm.com/downloads
- Verify:
  ```bash
  git --version
  ```

### 3. Disk space

At least **10 GB free** — Docker images are large (Python, Node, Postgres, etc.).

### 4. RAM

At least **8 GB** recommended. The AI model (if you enable it) needs more — see Step 3.

---

## Step 1 — Get the Code

```bash
git clone https://github.com/YOUR_USERNAME/FastCuts.git
cd FastCuts
```

> Replace `YOUR_USERNAME/FastCuts` with the actual repository URL.  
> Ask the person who shared this guide for the exact URL if you don't have it.

---

## Step 2 — Create the Backend Environment File

The backend needs a `.env` file. Create it now:

```bash
cat > backend/.env << 'EOF'
# ── Database (matches the postgres container in docker-compose.yml) ──────────
DB_HOST=db
DB_PORT=5432
DB_NAME=zeroqwait
DB_USER=postgres
DB_PASSWORD=zeroqwait_dev

# ── Redis ────────────────────────────────────────────────────────────────────
REDIS_HOST=redis
REDIS_PORT=6379

# ── JWT secret (change this to any long random string) ───────────────────────
SECRET_KEY=change-me-to-a-long-random-string-at-least-32-chars

# ── LLM — fill in ONE of the two options below (see Step 3) ─────────────────
LLM_PROVIDER=nvidia
NVIDIA_MODEL=meta/llama-3.1-8b-instruct
NVIDIA_API_KEY=YOUR_NVIDIA_API_KEY_HERE

# ── Ollama (only needed if you chose the Ollama option in Step 3) ────────────
OLLAMA_URL=http://host.docker.internal:11434
MODEL_NAME=qwen3:14b-q4_K_M

# ── Voice / TTS (optional — voice features will be disabled without this) ────
TTS_SERVICE_URL=http://localhost:8880

# ── Frontend origin for CORS ─────────────────────────────────────────────────
FRONTEND_URL=http://localhost:3000

# ── Odoo ERP (optional — CRM features need this) ─────────────────────────────
ODOO_URL=http://odoo:8069
ODOO_DB=odoo
ODOO_USER=admin
ODOO_PASSWORD=admin

# ── Stripe (optional — payment features need real keys) ──────────────────────
STRIPE_SECRET_KEY=sk_test_placeholder
STRIPE_PUBLISHABLE_KEY=pk_test_placeholder
STRIPE_WEBHOOK_SECRET=whsec_placeholder
EOF
```

> On **Windows** (PowerShell or CMD), you cannot use the `cat << 'EOF'` syntax.  
> Instead, open Notepad, paste the content above (without the `cat` line and `EOF` line),  
> and save the file as `backend\.env` (make sure it does not get a `.txt` extension).

---

## Step 3 — Choose Your LLM (AI Brain)

The AI agent features (owner chat, analytics summaries, HR suggestions) require a language model.  
Pick **one** option:

---

### Option A — NVIDIA NIM (recommended, cloud-based, free tier available)

This is the easiest option. You call NVIDIA's hosted models over the internet.  
No GPU required on your machine.

1. Go to https://build.nvidia.com and create a free account.
2. Click your profile → **API Keys** → **Generate API Key**.
3. Copy the key and paste it into `backend/.env`:
   ```
   LLM_PROVIDER=nvidia
   NVIDIA_MODEL=meta/llama-3.1-8b-instruct
   NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
4. Make sure the `OLLAMA_URL` line is still there but it will be ignored.

---

### Option B — Ollama (local, private, needs a good GPU)

This runs the AI model entirely on your machine. Requires ~8 GB VRAM (NVIDIA GPU).

1. Install Ollama: https://ollama.com/download
2. After installing, open a terminal and pull the model (this downloads ~5 GB):
   ```bash
   ollama pull qwen3:14b-q4_K_M
   ```
3. Make sure Ollama is running (it starts automatically on most systems after install).
4. In `backend/.env`, set:
   ```
   LLM_PROVIDER=ollama
   OLLAMA_URL=http://host.docker.internal:11434
   MODEL_NAME=qwen3:14b-q4_K_M
   ```
   And leave `NVIDIA_API_KEY` blank or remove that line.

---

### Option C — No AI (just the app, no AI responses)

If you only want to explore the UI and queue management without AI chat working:

- Leave `NVIDIA_API_KEY` blank in `backend/.env`.
- The app will start and the dashboard will work.
- AI chat responses will fail or return an error — everything else (queues, employees, services) works fine.

---

## Step 4 — Build and Start All Services

This step builds Docker images and starts all containers.  
**The first build takes 10–25 minutes** (it downloads base images and installs all Python/Node dependencies).  
Subsequent starts are fast (under 2 minutes).

```bash
docker compose up -d --build
```

Watch the build progress. When it finishes you will see output like:
```
 ✔ Container zeroqwait-db-1          Started
 ✔ Container zeroqwait-redis-1       Started
 ✔ Container zeroqwait-booking-mcp-1 Started
 ✔ Container zeroqwait-finance-mcp-1 Started
 ✔ Container zeroqwait-hr-mcp-1      Started
 ✔ Container zeroqwait-backend-1     Started
 ✔ Container zeroqwait-frontend-1    Started
 ✔ Container zeroqwait-odoo-1        Started
 ✔ Container zeroqwait-simulation-1  Started
```

---

## Step 5 — Verify All Containers Are Healthy

```bash
docker compose ps
```

Look at the **Status** column. All services should show `Up` or `Up (healthy)`.  
If any service shows `Exit` or `Restarting`, check Step 9 (Troubleshooting).

Also do a quick API health check:
```bash
curl http://localhost:8000/api/agent/health
```

Expected response (something like):
```json
{"status": "healthy", "model": "...", ...}
```

---

## Step 6 — Create Your Account and a Shop

The database starts empty. Create a user account through the app:

1. Open http://localhost:3000 in your browser.
2. Click **Sign Up** (or go to http://localhost:3000/signup).
3. Register with any email and password.
4. After logging in, go to **My Shops** and create a new shop.
5. Add some services to the shop.

That's it — you are now a shop owner in the system.

### (Optional) Create a Super Admin Account

If you want admin access to see all shops and users:

```bash
docker exec -it zeroqwait-backend-1 python create_super_admin.py
```

Follow the prompts to set email and password.

### (Optional) Load Sample / Test Data

To populate the database with fake shops, customers, and queue history:

```bash
docker exec -it zeroqwait-backend-1 python seed_data.py
```

This creates several test shop owners and customers you can log in with.  
Login credentials for seeded accounts are printed to the terminal after the script runs.

---

## Step 7 — Open the App

| What | URL |
|---|---|
| Main app | http://localhost:3000 |
| Backend API docs | http://localhost:8000/docs |
| Odoo ERP (CRM) | http://localhost:8069 — login: `admin` / `admin` |

---

## Step 8 — Watch the Live Simulation (Optional)

The `simulation` service automatically runs in the background.  
It creates a demo barbershop with two barbers and a stream of fake customers joining and leaving the queue.

Watch the live activity log:
```bash
docker compose logs -f simulation
```

You will see output like:
```
[09:15] 🟢 Amir Kim joined the queue  (position 3)
[09:17] ✂  Marcus called next customer
[09:23] 🚶 Amir Kim served — wait was 8 min
```

Open http://localhost:3000 and navigate to the shop to watch the queue update in real time.

Press `Ctrl+C` to stop following the logs (containers keep running).

---

## Stopping the Stack

To stop all containers without deleting data:
```bash
docker compose down
```

To stop and delete the database + all stored data (full reset):
```bash
docker compose down -v
```

> Warning: `down -v` deletes the PostgreSQL volume. All accounts, shops, and queue history will be gone.  
> Use this if you want a completely fresh start.

To restart after stopping:
```bash
docker compose up -d
```

(No `--build` needed on subsequent starts unless you change code.)

---

## Day-to-Day Commands

```bash
# Start everything
docker compose up -d

# Stop everything
docker compose down

# View logs from a specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f simulation

# Restart one service
docker compose restart backend

# Rebuild one service after code changes
docker compose build backend && docker compose up -d backend

# Open a shell inside the backend container
docker exec -it zeroqwait-backend-1 bash

# Check database directly
docker exec -it zeroqwait-db-1 psql -U postgres -d zeroqwait
```

---

## Step 9 — Troubleshooting

### Backend container keeps restarting

Check its logs:
```bash
docker compose logs backend --tail=50
```

Common causes:
- **`backend/.env` not found** — make sure you completed Step 2 and the file exists at `backend/.env`.
- **Database not ready** — wait 30 seconds and try `docker compose restart backend`.
- **Port 8000 already in use** — something else is using port 8000. Stop that service or add `BACKEND_HOST_PORT=8001` to a `.env` file in the project root.

### Frontend shows blank page or "Cannot connect to API"

```bash
docker compose logs frontend --tail=30
```

Make sure the backend is healthy first:
```bash
curl http://localhost:8000/api/agent/health
```

If the backend is healthy but frontend fails, try a hard reload in the browser (`Ctrl+Shift+R`).

### AI chat returns an error

- For NVIDIA: make sure `NVIDIA_API_KEY` in `backend/.env` is a valid key (not the placeholder).
- For Ollama: make sure Ollama is running (`ollama list` should show the model).
- Restart backend after fixing the env: `docker compose restart backend`.

### Simulation stops producing customers

The simulation auto-recovers from most errors, but if it goes quiet for more than 5 minutes:
```bash
docker compose restart simulation
```

### Port conflicts (something already using 3000, 8000, 5432, etc.)

Add a `.env` file in the **project root** (not `backend/.env`) to override host ports:
```bash
cat > .env << 'EOF'
FRONTEND_HOST_PORT=3001
BACKEND_HOST_PORT=8001
DB_HOST_PORT=5433
REDIS_HOST_PORT=6380
ODOO_HOST_PORT=8070
EOF
```

Then restart: `docker compose down && docker compose up -d`

### Full reset (start completely fresh)

```bash
docker compose down -v
docker compose up -d --build
```

---

## Architecture Quick Reference

```
Browser (http://localhost:3000)
        │
        ▼
   [Frontend — React/Nginx on :80]
        │  /api/* → proxy to backend
        ▼
   [Backend — FastAPI on :8000]
        │
        ├── [PostgreSQL — port 5432]
        ├── [Redis — port 6379]
        ├── [booking-mcp — :8890]   ← AI queue tools
        ├── [finance-mcp — :8891]   ← AI finance tools
        ├── [hr-mcp     — :8892]    ← AI HR tools
        └── [NVIDIA NIM / Ollama]   ← LLM for agent brain

   [Simulation — background worker]
        └── hits backend API to simulate customers + barbers

   [Odoo — port 8069]   ← CRM (optional)
```

---

## Notes for Windows Users

- Use **PowerShell** or **Windows Terminal** for commands.
- Docker Desktop must be running before you run any `docker` commands.
- If `docker compose up` fails with a permission error on the backend, add this to the project-root `.env`:
  ```
  LOCAL_UID=1000
  LOCAL_GID=1000
  ```
- File paths use backslashes on Windows (`backend\.env`), but inside Docker everything is Linux.
- The `cat > file << 'EOF'` syntax does not work in CMD/PowerShell — use a text editor to create `backend/.env` manually.

---

*Generated: 2026-05-01*
