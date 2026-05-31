# Aggressive Validation Report - 2026-05-31

## Scope
- Local validation stack: frontend, backend, PostgreSQL, Redis, SuperTokens, BookingMCP.
- Production safe probes: homepage, agent health, TTS health.
- Non-prod safe probes: documented `192.168.2.134.nip.io` homepage and agent health.
- Test data only: users/shops prefixed with `zqw-audit-*` and `ZQW UI Audit *`.

## Code Fixes Made
- `backend/modules/shops/router.py`: reloaded shop after tenant/module provisioning so `POST /api/shops/` responses include persisted `active_modules` and vertical metadata.
- `frontend/craco.config.js`: added Jest `@/*` module alias mapping to match webpack.
- `frontend/src/features/agent-inbox/AgentInbox.test.tsx`: updated test harness with production providers and current streaming approval API mock.

## Local Runtime
- Backend `http://localhost:8000/api/v2/agent/health`: `ok`.
- BookingMCP `http://127.0.0.1:8890/health`: `ok`.
- Frontend `http://localhost:3000/`: served by nginx, rendered landing page and ZeroQ chat.
- Startup warning remains: `notification_log` index migration references missing `sent_at`.

## Backend Tests
- Initial focused backend suite blocked on stale `backend/tests/test_multi_tenancy.py` import: `auth_utils` should be `shared.auth_utils` or test PYTHONPATH adjusted.
- Reduced focused suite: `64 passed`, `15 failed`, `6 errors`.
- Failure clusters:
  - `backend/tests/test_registration_flow.py` uses stale `/api/users` payload without required `username`.
  - `backend/tests/test_agent_v2.py` injects `shop_id=41` in auth context without a backing shop row; module skill lookup now correctly requires a real tenant.

## Frontend Checks
- `npm run typecheck`: passed.
- `CI=true npm test -- --watchAll=false`: `4 passed`, `18 tests passed`.
- `npm run build`: completed with warnings only.
- Existing build warnings include unused imports, hook dependency warnings, and a large bundle warning.

## Local API Security Smoke
- Created two isolated owners and shops through API.
- Auth checks passed:
  - unauthenticated protected endpoints return 401/403.
  - invalid token returns 401/403.
  - valid owner access returns 200.
  - cross-owner access returns 403/404.
  - malformed chat payload returns 400/422.
- Shop listing isolation passed: alpha owner cannot see beta shop and beta owner cannot see alpha shop.
- Fresh API create response after fix returned `active_modules: ["core", "salon"]`.

## Immersive UI Registration
- Live browser smoke opened `http://localhost:3000/`.
- ZeroQ chat opened from “Talk to ZeroQ”.
- Completed canonical immersive registration for `ZQW UI Audit Salon 1735`.
- Database verification: shop id `7`, vertical `salon`, active modules `["core", "salon"]`, tenant schema `tenant_7`.
- Repeated browser console warning: TTS endpoint returned 500 during spoken fallback attempts.

## Remote Safe Probes
- Production homepage `https://zeroqwait.com/`: HTTP 200.
- Production `/api/v2/agent/health`: `degraded`; Redis is `disabled (no connection)`, LLM/Postgres/graph/Temporal/Odoo OK.
- Production `/api/voice/tts/health`: `unavailable`; all connection attempts failed.
- Non-prod `http://192.168.2.134.nip.io/`: HTTP 200.
- Non-prod `/api/v2/agent/health`: same degraded Redis status as production.

## Dependency And Config Security
- Frontend `npm audit`: 49 total vulnerabilities: 9 low, 15 moderate, 25 high, 0 critical.
- Python dependency scan not completed: `pip-audit` is not installed in the local venv.
- Trivy config/container scan not completed: `trivy` is not installed on host.
- Workspace config scan findings:
  - mutable `latest` images in several Kubernetes manifests.
  - node-exporter uses `hostNetwork: true` and `privileged: true`.
  - committed `.env`-style secret material exists and should be rotated/moved out of repo history.
  - placeholder/default secrets remain in manifests/config examples.

## Priority Findings
1. Critical: committed secret material exists in `.env`-style files. Rotate affected keys and remove from tracked history.
2. High: production and non-prod agent health are degraded due Redis disabled/no connection.
3. High: production TTS health is unavailable.
4. High: frontend dependency audit reports 25 high vulnerabilities.
5. Medium: create-shop response previously returned stale `active_modules`; fixed and verified locally.
6. Medium: backend focused test suite has stale fixtures/imports that hide real regression signal.
7. Medium: Kubernetes manifests use mutable `latest` images and privileged node-exporter settings.
8. Low/Medium: frontend build warnings and bundle-size warning remain.

## Remediation Addendum - 2026-05-31

### Implemented Code And Manifest Fixes
- Backend test harness drift fixed:
  - `backend/tests/test_multi_tenancy.py` now imports auth helpers from `shared.auth_utils` and reflects current route/access behavior.
  - `backend/tests/test_registration_flow.py` now sends required `username` and full shop registration payload fields, and defaults to local backend port `8000`.
  - `backend/tests/test_agent_v2.py` now uses in-memory checkpointing and stubs tenant module skill lookup for router-level tests.
- Public shop queue response hardening:
  - `backend/modules/shops/router.py` now applies `sanitize_queue_data_for_public()` to both `GET /api/shops/{shop_id}` and `GET /api/shops/s/{slug}` queue payloads, preventing unauthenticated users from seeing employee assignment details.
  - `update_shop()` now preserves explicit `HTTPException` status codes instead of converting authorization failures into 500s.
- Agent routing hardening:
  - `backend/agents/supervisor.py` now routes refund requests through Finance before POS, preserving the finance approval/refund execution path.
- Kubernetes hardening:
  - `backend-deployment.yaml` now explicitly reads `REDIS_PASSWORD` from `redis-secret` and `ODOO_PASSWORD` from `odoo-secret`.
  - `backend-configmap.yaml` disables production `TELEGRAM_DEV_SHOP_ID` auto-linking and removes inline `ODOO_PASSWORD`.
  - `odoo-secret.yaml` includes an explicit `ODOO_PASSWORD` application credential placeholder.
  - `grafana-deployment.yaml` moves the admin password into `grafana-secret` and pins the Grafana image.
  - Prometheus, node-exporter, SuperTokens, Ollama, and Infisical images are pinned instead of using `latest`.
  - `node-exporter-daemonset.yaml` removes `privileged: true`, drops all capabilities, and uses a read-only root filesystem.
  - Staging secret placeholders no longer use `change-me` style literal passwords.
- Frontend dependency hardening:
  - `axios` upgraded to `1.16.1`.
  - Non-forced `npm audit fix --package-lock-only` applied safe transitive lockfile updates.
  - `.gitignore` now excludes credential markdown exports such as `CREDENTIALS_MASTER.md`.

### Live Infrastructure Fixes Applied
- Patched live `deployment/backend` in namespace `zeroqwait` to consume `REDIS_PASSWORD` from `redis-secret` and rolled out backend pods.
- Restored live `voice-mcp` from `0` replicas to `1` replica.
- Fixed live `voice-mcp` image drift by rolling it to the repo-pinned GHCR image `ghcr.io/nfornj/voice-mcp:v20260508024813-eea2f93`; the previous live tag no longer existed in GHCR.
- Aligned live `voice-mcp` environment to `TTS_DEFAULT_VOICE=Vivian` and the intended `zeroqwait-ai` upstream DNS names.

### Verification After Remediation
- Kustomize render: `kubectl kustomize k8s-manifests` passed.
- K8s mutable image scan: no remaining `image: ...latest` matches under `k8s-manifests/`.
- Focused backend tests: `63 passed`, `89 warnings`.
- Frontend validation:
  - `npm run typecheck`: passed.
  - `CI=true npm test -- --watchAll=false`: `4 passed`, `18 tests passed`.
  - `npm run build`: passed with existing warnings only.
- Frontend audit after safe fixes: `28 vulnerabilities` total (`9 low`, `6 moderate`, `13 high`). Remaining high findings are primarily CRA/react-scripts/Jest/build-tool transitive dependencies where `npm audit --force` proposes a breaking `react-scripts@0.0.0` path.
- Production agent health: `status: ok`; Redis now reports `ok`.
- Non-prod agent health: `status: ok`; Redis now reports `ok`.
- Production and non-prod `/api/voice/tts/health`: returned `status: ok` through `voice-mcp` after restoring the gateway.

### Remaining Blockers
- Actual TTS synthesis still fails with HTTP 502. A tiny production synthesis probe returned `http=502` even though `/tts/health` is green.
- Root cause is host/GPU runtime, not the Qwen/Vivian application config:
  - `nvidia-smi` fails on the host: cannot communicate with the NVIDIA driver.
  - Kubernetes node advertises `nvidia.com/gpu: 0` capacity/allocatable.
  - `nvidia-device-plugin-daemonset` is CrashLoopBackOff.
  - `zeroqwait-ai/asr-service` fails with NVML `Driver Not Loaded`.
  - `zeroqwait-ai/tts-service` is pending due insufficient `nvidia.com/gpu`.
- Operator action required: repair/reload the NVIDIA host driver/runtime and device plugin, then restart/roll out ASR/TTS pods. Do not change the approved TTS engine, model, voice, or port.
- Secret rotation/history purge remains operator-gated. The repo now ignores credential exports, but any previously exposed keys must still be rotated and, if committed historically, removed with a coordinated history rewrite.

## Artifact Index
Key logs live in this directory:
- `api-security-smoke-final.log`
- `create-shop-active-modules-response.log`
- `ui-registration-db-check.log`
- `frontend-typecheck-and-jest-passing.log`
- `frontend-build.log`
- `frontend-npm-audit.json`
- `prod-agent-health.log`
- `prod-tts-health.log`
- `nonprod-agent-health.log`
- `backend-focused-pytest-no-multitenancy.log`
