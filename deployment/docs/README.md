# Deployment Documentation

This directory documents the current deployment model for ZeroQwait.

The active story is:

- Local and non-prod testing use a single Docker Compose project named `zeroqwait`
- Canonical local URLs are `http://localhost:3000` and `http://localhost:8000`
- Production runs on K3s in the `zeroqwait` namespace
- GitHub Actions on a self-hosted runner drive non-prod and prod deployment flows

The authoritative deployment paths are listed below.

## Authoritative Deployment Paths

### Non-Prod Branch Deploy

Primary path:

```bash
bash deployment/scripts/deploy-test.sh
```

What it does:

- Uses the root `docker-compose.yml`
- Forces a single Compose project name: `zeroqwait`
- Publishes the canonical local URLs
- Builds and starts the app stack
- Initializes the database and seed data

Published URLs:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000

### Production Deploy

Primary path:

- GitHub Actions production workflow on `prod` branch
- Supporting scripts include `deployment/scripts/deploy-prod.sh` and `deployment/scripts/deploy-k8s.sh`

Production target:

- K3s cluster
- Namespace: `zeroqwait`
- Ingress: `https://zeroqwait.com`

### Local Image Pipeline

Primary path:

```bash
bash deployment/scripts/run-local-pipeline.sh
```

Use this when you need:

- local registry publishing
- versioned image tags
- manifest tag updates
- optional Argo CD sync

## Current Stack Topology

The root `docker-compose.yml` defines the active local stack:

- `db`: PostgreSQL 15
- `redis`: Redis 7
- `backend`: FastAPI backend
- `booking-mcp`: booking MCP server
- `finance-mcp`: finance MCP server
- `hr-mcp`: HR MCP server
- `frontend`: React app served through nginx
- `odoo`: Odoo 17 for CRM and ERP flows

This is the stack that local development and non-prod deployment docs should describe.

## Script Guide

### Primary

- `scripts/deploy-test.sh`: authoritative non-prod single-stack deploy
- `scripts/deploy-prod.sh`: production deployment entry point
- `scripts/deploy-k8s.sh`: K3s deployment helper
- `scripts/run-local-pipeline.sh`: versioned local image build and registry flow

### Operational Utilities

- `scripts/logs.sh`: inspect logs
- `scripts/cleanup.sh`: stop and clean local deployment artifacts
- `scripts/setup-local-registry.sh`: configure the local Docker registry
- `scripts/setup-argocd-gitops.sh`: initialize Argo CD integration
- `scripts/prune-registry-tags.sh`: retain the last configured image tags

### Manual Or Legacy Helpers

These scripts still exist, but they are not the primary deployment story:

- `scripts/deploy-local.sh`
- `scripts/deploy-compose.sh`
- `deploy.sh`
- `scripts/deploy-and-sync.sh`

Use them only when you explicitly need a manual flow that differs from the standard test or prod pipelines.

## Access Patterns

### Local / Non-Prod

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Swagger UI: http://localhost:8000/docs

### Production

- App: https://zeroqwait.com
- Backend API: https://zeroqwait.com/api

## Environment And Secrets

Current deployment docs should describe these sources:

- `backend/.env`
- root `docker-compose.yml`
- K8s manifests under `k8s-manifests/`

Common runtime variables include:

- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `REDIS_HOST`, `REDIS_PORT`
- `OLLAMA_URL`, `MODEL_NAME`
- `TTS_SERVICE_URL`
- `BOOKING_MCP_URL`, `FINANCE_MCP_URL`, `HR_MCP_URL`
- `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, `ODOO_PASSWORD`
- `FRONTEND_URL`

## Deployment Standards

When updating deployment docs, keep these rules aligned with the repo:

- Document the single-stack Compose project as `zeroqwait`
- Use `localhost:3000` and `localhost:8000` as canonical non-prod URLs
- Describe K3s as the active production platform
- Keep deployment notes aligned to the current Compose and K3s flows

## Need Help

- Check `scripts/logs.sh`
- Read `../README.md` for the repo-wide story
- Read `../claude.md` for architecture and infra context
- Inspect `deployment/scripts/` and `k8s-manifests/` if a doc appears stale

## Public Docs UI Release Steps

When frontend routes such as `/docs` or `/docs/architecture` are added or changed, use this exact path to make them live on `https://zeroqwait.com`.

### 1. Validate The Frontend Change Locally

```bash
cd frontend
npm run typecheck
```

If you want a full local smoke test:

```bash
cd /home/neekrishrichu/projects/FastCuts
bash deployment/scripts/deploy-test.sh
```

Then verify:

- `http://localhost:3000/docs`
- `http://localhost:3000/docs/architecture`

### 2. Push The Tested Change

Non-prod validation path:

```bash
git push origin <branch>
```

Production release path:

```bash
git push origin prod
```

### 3. What The Production Workflow Does

The `deploy-prod.yml` GitHub Actions workflow:

- runs on push to the `prod` branch
- checks out the repo on the self-hosted runner
- logs in to `ghcr.io`
- applies the Kubernetes backend secret from GitHub Secrets
- runs `deployment/scripts/deploy-prod.sh`
- builds and pushes versioned images through `deployment/scripts/run-local-pipeline.sh`
- applies the K3s manifests in the `zeroqwait` namespace
- waits for frontend, backend, and worker rollouts
- purges Cloudflare cache

### 4. Post-Deploy Verification

Use these checks after the workflow completes:

```bash
gh run list --workflow deploy-prod.yml
curl -I https://zeroqwait.com/docs
curl -I https://zeroqwait.com/docs/architecture
curl -fsS https://zeroqwait.com/api/agent/health
```

### 5. Important Note For SPA Routes

`/docs` and `/docs/architecture` are frontend routes served by the React app. They become live when the updated frontend image is rolled out successfully behind the production ingress. No separate backend route is required for these pages.
