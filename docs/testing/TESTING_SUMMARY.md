# Current Testing And Validation Paths

This document describes the current validation entry points for ZeroQwait.

## Current Validation Targets

The most important active test areas are:

- owner-facing agent v2 routing and approvals
- finance normalization and chartable summaries
- CRM integration through Odoo tools
- authentication and password reset
- employee, queue, and tenant-isolation behavior

Representative backend tests already in the repo include:

- `backend/tests/test_agent_v2.py`
- `backend/tests/test_finance_operation_normalization.py`
- `backend/tests/test_auth_reset_password.py`
- `backend/tests/test_crm_integration.py`
- `backend/tests/test_multi_tenancy.py`

## Local Backend Test Flow

### Preferred

```bash
cd backend
uv sync --dev
uv run pytest -q
```

### Focused Slice

```bash
cd backend
uv run pytest -q \
  tests/test_agent_v2.py \
  tests/test_finance_operation_normalization.py \
  tests/test_auth_reset_password.py \
  tests/test_crm_integration.py
```

If `uv` is not installed in the current shell, install it first or run the equivalent command inside the backend environment that matches `pyproject.toml` and `uv.lock`.

## Local App Smoke Test

### Source-Run Mode

Terminal 1:

```bash
docker compose up -d db redis booking-mcp finance-mcp hr-mcp odoo
```

Terminal 2:

```bash
cd backend
uv sync --dev
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 3:

```bash
cd frontend
REACT_APP_API_URL=http://localhost:8000/api npm start
```

Verify:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

### Non-Prod Deployment Smoke

```bash
bash deployment/scripts/deploy-test.sh
```

Then validate:

```bash
curl -fsS http://localhost:8000/api/agent/health
curl -fsS http://localhost:8000/api/v2/agent/health
curl -fsS http://localhost:8000/api/voice/tts/health
```

## Manual Functional Checks

### Auth

- create or use a test account
- log in through `/api/auth/token`
- confirm `/api/users/me` returns the current user
- verify password reset flow through `/api/auth/forgot-password` and `/api/auth/reset-password`

### Owner Agent Workspace

- sign in as a shop owner
- open the dashboard agent tab
- send a queue question
- send a finance trend question such as `Show revenue for the last 7 days`
- confirm streaming text, inline thinking, and inline chart rendering
- trigger an approval-gated action and verify the approval card flow

### CRM

- verify Odoo connection settings are present
- send a CRM-oriented owner message
- confirm the supervisor routes to CRM and returns a structured response

## Common Validation Problems

### `uv` not found

Install `uv` or use the repo-managed Python environment that contains the backend dev dependencies.

### Backend starts but tests fail to import dependencies

Resync the backend environment from `pyproject.toml` and `uv.lock`.

### Frontend cannot authenticate or fetch data

Verify the frontend is running with:

```bash
REACT_APP_API_URL=http://localhost:8000/api
```

### Docs look out of date

Use `README.md`, `docs/README.md`, and `claude.md` as the current reference set.
