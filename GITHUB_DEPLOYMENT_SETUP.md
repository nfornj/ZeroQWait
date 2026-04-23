# GitHub Deployment Setup

This guide describes the current GitHub-driven deployment model for ZeroQwait.

## Current Model

The active deployment flow is based on GitHub Actions running on a self-hosted runner.

- Non-`prod` branch pushes trigger the non-production Compose deployment flow
- `prod` branch pushes trigger the production K3s deployment flow
- Local image and manifest work can be driven through the local pipeline scripts under `deployment/scripts/`

This document replaces the older SSH-to-Raspberry-Pi workflow.

## Active Branch Behavior

### Non-Production

- Workflow: `deploy-test.yml`
- Trigger: any push to a branch other than `prod`
- Deployment target: the single local Docker Compose stack named `zeroqwait`
- Published URLs:
   - `http://localhost:3000`
   - `http://localhost:8000`

### Production

- Workflow: `deploy-prod.yml`
- Trigger: push to `prod`
- Deployment target: K3s in the `zeroqwait` namespace
- Published URL:
   - `https://zeroqwait.com`

## Runner Expectations

The self-hosted runner is the authoritative execution environment for deployment automation.

Current repo assumptions:

- the runner has Docker available for the Compose and image pipeline flows
- the runner has K3s access for production deploys
- deployment scripts under `deployment/scripts/` are the source of truth for operational steps

## Standard Developer Workflow

1. Make and verify changes locally.
2. Commit to the working branch.
3. Push the branch to GitHub.
4. Let the appropriate workflow execute based on branch name.
5. Verify the resulting environment with the relevant health checks.

## Core Scripts

### Non-Prod Compose Deploy

```bash
bash deployment/scripts/deploy-test.sh
```

### Production Deploy Support

```bash
bash deployment/scripts/deploy-prod.sh
```

### Local Image Pipeline

```bash
bash deployment/scripts/run-local-pipeline.sh
```

Use the local image pipeline when you need versioned images, local registry updates, or manifest tag changes beyond the basic test deployment flow.

## Health Checks

### Non-Prod / Local

```bash
curl -fsS http://localhost:8000/api/agent/health
curl -fsS http://localhost:8000/api/v2/agent/health
curl -fsS http://localhost:8000/api/voice/tts/health
```

### Production

```bash
curl -sk https://zeroqwait.com/api/agent/health
curl -sk https://zeroqwait.com/api/v2/agent/health
curl -sk https://zeroqwait.com/api/voice/tts/health
```

## Secrets And Configuration

Do not commit live secrets.

Current deployment paths rely on:

- `backend/.env` for local source-run work
- deployment-managed environment variables for Compose and K3s
- K8s manifests and secrets under `k8s-manifests/` for production

Common runtime values include:

- PostgreSQL connection settings
- Redis connection settings
- `OLLAMA_URL` and `MODEL_NAME`
- `TTS_SERVICE_URL`
- MCP service URLs
- Odoo connection settings
- `FRONTEND_URL`

## Troubleshooting

### Non-Prod workflow ran but app is not reachable

- inspect the Compose stack logs
- confirm the stack is still named `zeroqwait`
- confirm ports `3000` and `8000` are free and mapped correctly

### Production workflow succeeded but the site is unhealthy

- inspect pod status in the `zeroqwait` namespace
- check Traefik ingress and backend rollout status
- verify service URLs and secrets used by the production backend

### Need a manual deployment check

Use the underlying deployment scripts directly instead of reviving older manual host-specific instructions.

## Related Docs

- `README.md`
- `deployment/docs/README.md`
- `claude.md`
