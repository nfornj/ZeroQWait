# Root Directory Cleanup Guide

## Files to Remove (Safe to Delete)

These files are outdated or have been reorganized into the `/deployment` folder:

### Deployment Scripts (Now in `/deployment/scripts/`)

```
❌ deploy.sh              → See deployment/deploy.sh
❌ deploy-local.sh        → See deployment/scripts/deploy-local.sh
❌ deploy-k8s.sh          → See deployment/scripts/deploy-k8s.sh
❌ deploy-github.sh       → Legacy, use GitHub Actions instead
❌ deploy-pi.sh           → Legacy host-specific script
❌ deploy_to_pi.sh        → Legacy, replaced by deployment folder
❌ build-and-push.sh      → Legacy, use Docker directly
❌ complete-deployment.sh → Legacy, outdated
```

### Outdated Documentation (Now in `/deployment/docs/`)

```
❌ DEPLOYMENT.md                      → Consolidated into deployment/docs/
❌ DEPLOYMENT_REVIEW.md               → Consolidated into deployment/docs/
❌ DEPLOYMENT_STATUS.md               → Outdated
❌ DEPLOYMENT_STRATEGY.md             → Outdated
❌ DEPLOYMENT_CHECKLIST.md (root)     → New one in deployment/
❌ DEPLOYMENT_GUIDE_SUBDOMAINS.md     → Merged into deployment/docs/
❌ PHASE2_DEPLOYMENT_GUIDE.md         → Legacy
❌ RASPBERRY_PI_DEPLOYMENT.md         → Legacy
❌ PI_SETUP_CHECKLIST.md              → Legacy
❌ GITHUB_ACTIONS_SETUP.md            → Legacy (outdated setup)
❌ QUICK_GITHUB_ACTIONS_SETUP.md      → Legacy
❌ SELFHOSTED_RUNNER_SETUP.md         → Legacy
```

### Database/Setup Scripts (Keep only if actively using)

```
❌ setup-github-actions.sh  → GitHub Actions configured automatically
❌ create_supabase_tables.py → Use migrations instead
❌ create_tables_direct.py   → Use migrations instead
❌ verify_production_database.sql → Use for manual verification only
❌ setup_attendance_calendar.sql  → One-time setup, not needed after
❌ setup_password_reset.sql       → One-time setup, not needed after
```

### Test Scripts (Move to `/tests/`)

```
❌ test_api.sh        → Move to backend/tests/
❌ test_queue_serve.sh → Move to backend/tests/
```

### Config Files (Keep but Organize)

```
✅ docker-compose.yml (Keep in root)
✅ docker-compose.prod.yml (Keep in root or move to deployment/docker/)
⚠️  Dockerfile.combined → Move to deployment/docker/ or delete if not used
⚠️  nginx.combined.conf → Move to deployment/docker/ or use from image
⚠️  supervisord.conf → Not needed for Docker/K8s, delete
```

### Development Files

```
✅ .env.example (Keep - template)
✅ .env (Keep - but never commit)
✅ .env.local (If exists, keep - don't commit)
```

### Other Files

```
❌ widget-example.html → Move to docs/examples/
⚠️  WARP.md → Legacy/experimental, probably delete
❌ TEST_RESULTS_AND_CREDENTIALS.md → Security risk, delete
✅ README.md (Keep - main project readme)
✅ package.json (Keep - root dependencies)
✅ node_modules/ (Keep - but add to .gitignore)
```

---

## Cleanup Commands

### Step 1: Backup (Just in case)

```bash
tar -czf backup-root-files.tar.gz \
  deploy*.sh \
  build-and-push.sh \
  complete-deployment.sh \
  *.md \
  *.sql \
  setup-*.sh

# Save this file somewhere safe
```

### Step 2: Remove Deployment Scripts

```bash
rm -f \
  deploy.sh \
  deploy-local.sh \
  deploy-k8s.sh \
  deploy-github.sh \
  deploy-pi.sh \
  deploy_to_pi.sh \
  build-and-push.sh \
  complete-deployment.sh
```

### Step 3: Remove Old Documentation

```bash
rm -f \
  DEPLOYMENT.md \
  DEPLOYMENT_REVIEW.md \
  DEPLOYMENT_STATUS.md \
  DEPLOYMENT_STRATEGY.md \
  DEPLOYMENT_CHECKLIST.md \
  DEPLOYMENT_GUIDE_SUBDOMAINS.md \
  PHASE2_DEPLOYMENT_GUIDE.md \
  RASPBERRY_PI_DEPLOYMENT.md \
  PI_SETUP_CHECKLIST.md \
  GITHUB_ACTIONS_SETUP.md \
  QUICK_GITHUB_ACTIONS_SETUP.md \
  SELFHOSTED_RUNNER_SETUP.md
```

### Step 4: Remove Setup Scripts (If Not Needed)

```bash
rm -f \
  setup-github-actions.sh \
  create_supabase_tables.py \
  create_tables_direct.py \
  setup_attendance_calendar.sql \
  setup_password_reset.sql
```

### Step 5: Move Test Scripts

```bash
mkdir -p backend/tests
mv test_api.sh backend/tests/
mv test_queue_serve.sh backend/tests/
```

### Step 6: Clean Config Files

```bash
# If using Docker/K8s, these aren't needed:
rm -f supervisord.conf Dockerfile.combined nginx.combined.conf
```

---

## New Root Directory Structure

After cleanup:

```
zeroqwait/
├── README.md                    ✅ Keep
├── package.json                 ✅ Keep
├── .env.example                 ✅ Keep
├── .env                         ✅ Keep (don't commit)
├── .gitignore                   ✅ Keep
├── docker-compose.yml           ✅ Keep
├── docker-compose.prod.yml      ✅ Keep
│
├── backend/                     ✅ Keep
│   ├── models.py
│   ├── main.py
│   ├── requirements.txt
│   ├── tests/
│   │   ├── test_api.sh
│   │   └── test_queue_serve.sh
│   └── ...
│
├── frontend/                    ✅ Keep
│   └── ...
│
├── deployment/                  ✅ NEW - Central hub
│   ├── deploy.sh                   - Main entry point
│   ├── scripts/
│   │   ├── deploy-local.sh
│   │   ├── deploy-k8s.sh
│   │   ├── deploy-compose.sh
│   │   ├── logs.sh
│   │   ├── cleanup.sh
│   │   └── setup-monitoring.sh
│   ├── kubernetes/
│   │   ├── backend-deployment.yaml
│   │   ├── frontend-deployment.yaml
│   │   └── ...
│   ├── docker/
│   │   ├── docker-compose.yml
│   │   └── docker-compose.prod.yml
│   ├── monitoring/
│   │   ├── MONITORING_GUIDE.md
│   │   ├── prometheus-grafana.sh
│   │   └── ...
│   └── docs/
│       ├── README.md
│       ├── GETTING_STARTED.md
│       ├── TROUBLESHOOTING.md
│       └── ...
│
├── docs/                        (Keep if exists)
│   └── ...
│
├── k8s-manifests/               ⚠️  Move to deployment/kubernetes/
│   └── ...
│
└── .git/                        ✅ Keep
```

---

## Safe to Delete Files Summary

**100% Safe to Delete:**

```bash
deploy.sh
deploy-local.sh
deploy-k8s.sh
deploy-github.sh
deploy-pi.sh
deploy_to_pi.sh
build-and-push.sh
complete-deployment.sh
setup-github-actions.sh
DEPLOYMENT*.md
PHASE2_*.md
RASPBERRY_PI_*.md
PI_SETUP_*.md
GITHUB_*.md
QUICK_GITHUB_*.md
SELFHOSTED_*.md
supervisord.conf
Dockerfile.combined
nginx.combined.conf
TEST_RESULTS_AND_CREDENTIALS.md
WARP.md
```

**Keep:**

```
README.md
.env, .env.example
docker-compose.yml, docker-compose.prod.yml
backend/, frontend/, deployment/
.git/, .gitignore
```

---

## One-Line Cleanup Command

```bash
# Remove all outdated files (CAREFUL!)
rm -f deploy*.sh build-and-push.sh complete-deployment.sh \
  setup-github-actions.sh create_supabase_tables.py create_tables_direct.py \
  DEPLOYMENT*.md PHASE2_*.md RASPBERRY_PI_*.md PI_SETUP_*.md \
  GITHUB_*.md QUICK_GITHUB_*.md SELFHOSTED_*.md \
  supervisord.conf Dockerfile.combined nginx.combined.conf \
  TEST_RESULTS_AND_CREDENTIALS.md WARP.md \
  setup_attendance_calendar.sql setup_password_reset.sql \
  verify_production_database.sql

# Then move test scripts
mkdir -p backend/tests
mv test_api.sh backend/tests/ 2>/dev/null || true
mv test_queue_serve.sh backend/tests/ 2>/dev/null || true
```

---

## After Cleanup: Update Workflows

### Update Git

```bash
git add -A
git commit -m "refactor: reorganize deployment files and cleanup root directory"
```

### Update README

Add to main README.md:

````markdown
## Deployment

For deployment instructions, see: `deployment/docs/README.md`

### Quick Start

```bash
cd deployment
./deploy.sh
```
````

````

### Update CI/CD
If using GitHub Actions, update workflows to use:
```yaml
- name: Deploy
  run: bash deployment/scripts/deploy-k8s.sh
````

---

## Keeping Your Backups

Before deleting anything important:

```bash
# Create a backup branch
git checkout -b backup/original-structure
git push origin backup/original-structure

# Then proceed with cleanup on main branch
git checkout main
# ... perform cleanup ...
git commit -m "refactor: organize deployment"
git push origin main
```

This way, you can always revert if needed!

---

## Summary

✅ **New Structure Benefits:**

- Centralized deployment logic
- Organized documentation
- Easy to navigate
- Professional organization
- Scales with new features

✅ **After Cleanup:**

- Root directory is clean
- All deployment scripts in one place
- All documentation organized
- Easier for new team members
- Git history is cleaner

---

Start with: `bash cleanup-commands.sh` (review carefully!)
