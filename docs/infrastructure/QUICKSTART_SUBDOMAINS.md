# Quick Start: Current Subdomain Testing

This document reflects the current ZeroQwait subdomain story.

## Current Model

There are now three relevant environments:

- Local source-run and non-prod Docker Compose
  Canonical URLs are `http://localhost:3000` and `http://localhost:8000`
- K3s ingress test environment
  Base URL is `http://192.168.2.134.nip.io`
- Production
  Base URL is `https://zeroqwait.com`

Shop-specific subdomain behavior matters primarily in the K3s ingress and production environments, not in the standard local `localhost` workflow.

## Standard Local Development

For day-to-day development, do not start with wildcard subdomains. Use:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

This is the active non-prod development path.

## K3s Ingress Testing

Use this when you need to verify wildcard ingress or subdomain routing behavior.

### Base Endpoints

- Frontend root: `http://192.168.2.134.nip.io`
- Backend API: `http://192.168.2.134.nip.io/api`

### Wildcard Pattern

Expected shop subdomain format:

```text
http://<shop-slug>.192.168.2.134.nip.io
```

### Quick Verification

```bash
curl -sk http://192.168.2.134.nip.io/api/agent/health
curl -sk http://192.168.2.134.nip.io/api/voice/tts/health
```

Then open a known shop slug in the browser and verify that the request flow resolves through the wildcard ingress.

## Production Subdomains

Production is anchored on:

- Main site: `https://zeroqwait.com`
- Wildcard shop domains: `https://<shop-slug>.zeroqwait.com` when that flow is enabled and routed

If you are documenting customer-facing subdomain behavior, describe production in terms of `zeroqwait.com`.

## Troubleshooting

| Issue | Current check |
| --- | --- |
| `localhost` works but wildcard subdomain does not | Test against the K3s ingress host, not the Compose stack |
| K3s root host resolves but shop subdomain does not | Verify wildcard ingress and DNS pattern for `*.192.168.2.134.nip.io` |
| API calls fail from subdomain | Check ingress rules, backend CORS config, and frontend nginx proxy settings |
| Behavior differs from docs | Prefer `README.md`, `claude.md`, and `deployment/docs/README.md` |

## Status

This document replaces the older `192.168.2.88.nip.io` quickstart. The current test ingress host is `192.168.2.134.nip.io` and the standard local dev path is `localhost`.
