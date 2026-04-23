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
