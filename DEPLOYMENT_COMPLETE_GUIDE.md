# ZeroQwait Complete Deployment & Operations Guide

**A comprehensive guide covering deployment, monitoring, troubleshooting, and operations.**

---

## Table of Contents

1. [Introduction](#introduction)
2. [Quick Start (5 Minutes)](#quick-start-5-minutes)
3. [Deployment Options](#deployment-options)
4. [Monitoring & Observability](#monitoring--observability)
5. [Accessing Your Application](#accessing-your-application)
6. [Directory Structure](#directory-structure)
7. [Common Commands Reference](#common-commands-reference)
8. [Troubleshooting](#troubleshooting)
9. [Cleanup & Maintenance](#cleanup--maintenance)
10. [Advanced Topics](#advanced-topics)
11. [Cost & Tool Comparison](#cost--tool-comparison)

---

## Introduction

ZeroQwait is a multi-tenant queue management system with shop-based subdomains. This guide covers:

- **Deployment:** Local Docker, Docker Compose, Kubernetes
- **Monitoring:** Docker Stats, Prometheus, Grafana, Sentry, DataDog
- **Maintenance:** Logs, cleanup, troubleshooting
- **Operations:** Day-to-day management tasks

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Browser                             │
│          (192.168.2.88.nip.io or shopname.*)               │
└────────┬────────────────────────────────────────────────────┘
         │
┌────────▼─────────────────────────────────────────────────────┐
│              Traefik/Ingress (K8s) or nginx                  │
│                 Routes by subdomain                          │
└────────┬────────────────────────────────────────────────────┘
         │
         ├─► Frontend (React, Port 3000/80)
         │   ├─ Handles UI
         │   ├─ Makes API calls to /api
         │   └─ Auto-redirects to shop subdomain
         │
         └─► Backend (FastAPI, Port 8000)
             ├─ REST API
             ├─ Database (PostgreSQL)
             └─ Business logic

Databases:
├─ PostgreSQL (Local or Supabase)
└─ Optional: Redis for caching
```

### Key Features

✅ Multi-shop support with subdomains  
✅ Automatic login redirect to shop domain  
✅ Docker & Kubernetes ready  
✅ Built-in monitoring integration  
✅ Free open-source tools

---

## Quick Start (5 Minutes)

### Prerequisites

- Docker & Docker Compose installed
- For Kubernetes: kubectl configured
- 192.168.2.88 reachable (or update IP in scripts)

### Deployment in 3 Steps

**Step 1: Navigate to deployment folder**

```bash
cd /Users/neekrish/zeroqwait/deployment
```

**Step 2: Choose your deployment**

```bash
# Interactive menu (recommended for first time)
./deploy.sh

# Or direct deployment
bash scripts/deploy-local.sh      # Local Docker (15 sec)
bash scripts/deploy-k8s.sh        # Kubernetes (2-3 min)
bash scripts/deploy-compose.sh    # Production Compose (30 sec)
```

**Step 3: Access your app**

```
Local Docker: http://192.168.2.88.nip.io:3000
Kubernetes:   http://192.168.2.88.nip.io/
API Docs:     http://192.168.2.88.nip.io:8000/docs
```

### Testing the Subdomain Feature

1. Register as shop owner
2. Create a shop (e.g., "Pizza Palace")
3. Logout
4. Login again
5. Should redirect to: `pizza-palace.192.168.2.88.nip.io`

---

## Deployment Options

### Option 1: Local Docker (Development)

**Best for:** Development, testing, learning

**Time:** ~15 seconds

**Command:**

```bash
cd deployment
bash scripts/deploy-local.sh
```

**Access:**

```
Frontend: http://192.168.2.88.nip.io:3000
Backend:  http://192.168.2.88.nip.io:8000
Docs:     http://192.168.2.88.nip.io:8000/docs
```

**Features:**

- All containers on your machine
- Easy to stop/start
- Perfect for development
- Good for testing changes locally

**Stop it:**

```bash
docker-compose down
```

---

### Option 2: Docker Compose Production

**Best for:** Staging, production-like testing

**Time:** ~30 seconds

**Command:**

```bash
cd deployment
bash scripts/deploy-compose.sh
```

**Uses:**

- docker-compose.prod.yml
- Health checks enabled
- Proper resource limits
- Good for pre-production testing

**Access:**

```
Main: http://192.168.2.88.nip.io
```

---

### Option 3: Kubernetes (Production)

**Best for:** Production, scalability, high availability

**Time:** ~2-3 minutes

**Requirements:**

- Kubernetes cluster (minikube, Kind, or cloud)
- kubectl configured
- Traefik ingress controller installed

**Command:**

```bash
cd deployment
bash scripts/deploy-k8s.sh
```

**What it deploys:**

- PostgreSQL StatefulSet
- Backend Deployment
- Frontend Deployment
- Traefik Ingress (wildcard subdomains)
- ConfigMaps & Secrets

**Access:**

```
Main: http://192.168.2.88.nip.io
API:  http://192.168.2.88.nip.io/api
```

**Check status:**

```bash
kubectl get pods -n zeroqwait
kubectl logs -n zeroqwait -l app=backend
```

---

## Monitoring & Observability

### Phase 1: Development Monitoring (Start Here)

**Cost:** $0  
**Setup:** 5 minutes

#### Docker Stats

```bash
# Real-time container stats
docker stats

# Specific container
docker stats zeroqwait-backend
```

**Shows:**

- CPU usage %
- Memory usage
- Network I/O
- Block I/O

#### Portainer (Visual UI) ⭐ Recommended

```bash
# Install (one command)
docker run -d -p 9000:9000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  portainer/portainer-ce

# Access at http://localhost:9000
# Default: admin/admin12345
```

**Features:**

- Web-based UI
- Real-time graphs
- Container management
- Log viewer
- Free forever

#### Sentry (Error Tracking)

```bash
# Free tier: https://sentry.io
# Sign up → Create project
# Get DSN → Add to backend/main.py

# Python backend integration:
pip install sentry-sdk
```

**Features:**

- Automatic error tracking
- Alerts on errors
- Integration with Slack
- Free tier: 5,000 errors/month

---

### Phase 2: Production Monitoring

**Cost:** $0 (self-hosted)  
**Setup:** 30-45 minutes

#### Prometheus + Grafana

**Install:**

```bash
cd deployment
bash scripts/setup-monitoring.sh
# Choose: Prometheus + Grafana option
```

**What you get:**

- Prometheus: Metrics database
- Grafana: Beautiful dashboards
- Alerting: Rules & notifications
- Historical data: Months of history

**Access:**

```
Prometheus: http://localhost:9090
Grafana:    http://localhost:3001 (admin/prom-operator)
```

**Key metrics to monitor:**

- Request rate (req/sec)
- Error rate (%)
- Response time (p50, p95, p99)
- CPU usage (%)
- Memory usage (%)
- Disk space (%)

**Alerting thresholds:**

```
Error rate > 5% → ALERT
Response time > 1s → WARNING
CPU > 80% → WARNING
CPU > 95% → ALERT
Memory > 90% → ALERT
```

---

### Phase 3: Enterprise Monitoring

**Cost:** $15-100/month  
**Setup:** 15 minutes

#### DataDog (Recommended for Growth)

```bash
# Sign up: https://www.datadoghq.com
# Install DataDog agent
# Add to docker-compose.yml

services:
  datadog:
    image: datadog/agent:latest
    environment:
      - DD_API_KEY=your_api_key
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

**Features:**

- Full APM (Application Performance Monitoring)
- Infrastructure monitoring
- Log management
- Real user monitoring
- Free tier: 5 hosts

#### New Relic

```bash
# Sign up: https://newrelic.com
# Install agent
# Deploy & monitor

# Python: pip install newrelic
# React: Browser agent in index.html
```

**Features:**

- Full-stack observability
- Infrastructure monitoring
- APM & tracing
- Log management
- Free tier: 100GB/month

---

### Monitoring Tool Comparison

| Tool         | Cost   | Setup  | Best For          | Visual    |
| ------------ | ------ | ------ | ----------------- | --------- |
| Docker Stats | Free   | 0 min  | Quick checks      | CLI       |
| Portainer    | Free   | 2 min  | Visual monitoring | Web UI ⭐ |
| Sentry       | Free/$ | 10 min | Error tracking    | Web UI    |
| Prometheus   | Free   | 30 min | Metrics storage   | CLI       |
| Grafana      | Free   | 30 min | Dashboards        | Web UI ⭐ |
| DataDog      | $$     | 15 min | Cloud APM         | Web UI ⭐ |
| New Relic    | $$$    | 15 min | Enterprise        | Web UI ⭐ |

**Recommended Path:**

1. **Start:** Docker Stats (free, built-in)
2. **Add:** Sentry (error tracking, free)
3. **Grow:** Prometheus + Grafana (free, self-hosted)
4. **Scale:** DataDog or New Relic (professional)

---

## Accessing Your Application

### URLs for Different Environments

#### Local Docker

```
Frontend:  http://192.168.2.88.nip.io:3000
Backend:   http://192.168.2.88.nip.io:8000
Swagger:   http://192.168.2.88.nip.io:8000/docs
```

#### Docker Compose

```
Frontend:  http://192.168.2.88.nip.io
Backend:   http://192.168.2.88.nip.io/api
Swagger:   http://192.168.2.88.nip.io/api/docs
```

#### Kubernetes

```
Frontend:  http://192.168.2.88.nip.io
Backend:   http://192.168.2.88.nip.io/api
Swagger:   http://192.168.2.88.nip.io/api/docs
```

### After Login (Subdomain Redirect)

When you login as a shop owner, you're automatically redirected to your shop's subdomain:

```
Shop 1: http://pizza-palace.192.168.2.88.nip.io
Shop 2: http://coffee-shop.192.168.2.88.nip.io
Shop N: http://shopname.192.168.2.88.nip.io
```

### What is nip.io?

**nip.io** is a free wildcard DNS service:

- `192.168.2.88.nip.io` → resolves to `192.168.2.88`
- `shop1.192.168.2.88.nip.io` → also resolves to `192.168.2.88`
- No DNS configuration needed
- Works everywhere (local, office, cloud)

For production, replace with your real domain.

---

## Directory Structure

```
/Users/neekrish/zeroqwait/
├── deployment/                          ← START HERE
│   ├── deploy.sh                        Main entry point (interactive menu)
│   ├── scripts/
│   │   ├── deploy-local.sh              Local Docker deployment
│   │   ├── deploy-k8s.sh                Kubernetes deployment
│   │   ├── deploy-compose.sh            Production Compose
│   │   ├── logs.sh                      View logs
│   │   ├── cleanup.sh                   Stop containers
│   │   └── setup-monitoring.sh          Setup monitoring
│   ├── kubernetes/                      K8s manifests
│   │   ├── backend-deployment.yaml
│   │   ├── frontend-deployment.yaml
│   │   ├── ingress-traefik.yaml
│   │   └── ...
│   ├── monitoring/                      Monitoring setup
│   │   ├── MONITORING_GUIDE.md
│   │   ├── prometheus-grafana.sh
│   │   └── ...
│   └── docs/                            Documentation (THIS FILE)
│
├── backend/                             Python/FastAPI backend
│   ├── main.py                          Main application
│   ├── models.py                        Database models
│   ├── requirements.txt                 Python dependencies
│   ├── tests/
│   ├── routers/                         API endpoints
│   └── ...
│
├── frontend/                            React frontend
│   ├── src/
│   ├── public/
│   ├── package.json                     Node dependencies
│   └── ...
│
├── docker-compose.yml                   Development compose
├── docker-compose.prod.yml              Production compose
├── README.md                            Main project README
├── .env.example                         Environment template
└── .env                                 Environment variables (don't commit)
```

---

## Common Commands Reference

### Deployment Commands

```bash
# Enter deployment folder
cd deployment

# Interactive menu
./deploy.sh

# Direct deployments
bash scripts/deploy-local.sh      # Local Docker
bash scripts/deploy-k8s.sh        # Kubernetes
bash scripts/deploy-compose.sh    # Production Compose
```

### Log & Monitoring Commands

```bash
# View logs
bash scripts/logs.sh              # Interactive log viewer

# Docker logs directly
docker-compose logs -f            # All containers
docker-compose logs -f backend    # Backend only
docker-compose logs -f frontend   # Frontend only

# Kubernetes logs
kubectl logs -n zeroqwait -l app=backend -f
kubectl logs -n zeroqwait -l app=frontend -f

# Real-time stats
docker stats
docker stats --no-stream

# Portainer UI
docker run -d -p 9000:9000 -v /var/run/docker.sock:/var/run/docker.sock portainer/portainer-ce
# Access: http://localhost:9000
```

### Container Management

```bash
# Check status
docker-compose ps
docker-compose ps --services
docker ps

# Stop containers
bash scripts/cleanup.sh            # Interactive cleanup
docker-compose down                # Manual stop

# Restart containers
docker-compose restart
docker-compose restart backend

# Rebuild containers
docker-compose build --no-cache
```

### Kubernetes Commands

```bash
# Check pods
kubectl get pods -n zeroqwait
kubectl get pods -n zeroqwait -o wide

# Check services
kubectl get svc -n zeroqwait

# Check ingress
kubectl get ingress -n zeroqwait

# Describe resources
kubectl describe pod <pod-name> -n zeroqwait
kubectl describe deployment backend -n zeroqwait

# Delete deployment
kubectl delete namespace zeroqwait
```

### Health Checks

```bash
# API health
curl http://192.168.2.88.nip.io:8000/
curl http://192.168.2.88.nip.io:8000/docs

# Database connection
docker-compose exec backend psql -U postgres -d fastcuts_db -c "SELECT 1"

# Frontend health
curl http://192.168.2.88.nip.io:3000/
curl http://192.168.2.88.nip.io/api/
```

### Environment Variables

```bash
# View environment variables
cat .env
cat backend/.env

# Set temporary variable
export REACT_APP_API_URL=/api
docker-compose up

# Check what's set
env | grep REACT
env | grep API
```

---

## Troubleshooting

### Common Issues & Solutions

#### Issue: Can't access 192.168.2.88.nip.io

**Symptoms:**

- "This site can't be reached"
- DNS timeout

**Solutions:**

1. **Verify IP:**

   ```bash
   ifconfig | grep "192.168"  # Check your actual IP
   ```

2. **Verify DNS resolution:**

   ```bash
   ping 192.168.2.88.nip.io
   nslookup 192.168.2.88.nip.io
   ```

3. **Check if containers are running:**

   ```bash
   docker-compose ps
   docker stats
   ```

4. **Update IP in scripts:**
   - Edit `deployment/scripts/deploy-local.sh`
   - Change `CLUSTER_IP="192.168.2.88"` to your IP
   - Also update `.env` and docker-compose files

---

#### Issue: Frontend loads but API calls fail (CORS error)

**Symptoms:**

- "Access to XMLHttpRequest has been blocked by CORS policy"
- Network tab shows red X on API calls

**Solutions:**

1. **Check backend logs:**

   ```bash
   docker-compose logs -f backend | grep -i cors
   ```

2. **Verify FRONTEND_URL:**

   ```bash
   grep FRONTEND_URL backend/.env
   # Should be: FRONTEND_URL=http://192.168.2.88.nip.io
   ```

3. **Check CORS configuration:**
   - File: `backend/main.py`
   - Should include all shop subdomains
   - Look for: `"http://*.192.168.2.88.nip.io"`

4. **Restart backend:**
   ```bash
   docker-compose restart backend
   docker-compose logs -f backend
   ```

---

#### Issue: Login redirect not working (stays on base URL)

**Symptoms:**

- After login, redirects to /dashboard instead of shopname.nip.io
- Or redirects to wrong subdomain

**Solutions:**

1. **Verify shop was created with slug:**

   ```bash
   docker-compose exec backend psql -U postgres -d fastcuts_db \
     -c "SELECT id, name, slug FROM shops;"
   ```

2. **Check browser console:**
   - Open DevTools (F12)
   - Check Console tab for errors
   - Check Network tab for redirect

3. **Check frontend redirect logic:**
   - File: `frontend/src/pages/LoginPage.tsx`
   - Look for `redirectToShopDashboard()` function
   - Should fetch shop info and build correct URL

4. **Check localStorage:**
   - DevTools → Application → LocalStorage
   - Verify token exists
   - Verify it's valid JWT

---

#### Issue: Database connection error

**Symptoms:**

- "Cannot connect to database"
- Backend won't start

**Solutions:**

1. **Check PostgreSQL container:**

   ```bash
   docker-compose ps
   docker logs postgres
   ```

2. **Verify DB environment variables:**

   ```bash
   cat backend/.env | grep DB_
   # Should have: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
   ```

3. **Check if volume exists:**

   ```bash
   docker volume ls | grep postgres
   ```

4. **Rebuild database:**
   ```bash
   docker-compose down -v          # Remove volume
   docker-compose up -d postgres   # Start fresh
   sleep 5                         # Wait for startup
   docker-compose up -d            # Start all services
   ```

---

#### Issue: Port already in use

**Symptoms:**

- "Address already in use"
- "Error: listen EADDRINUSE :::3000"

**Solutions:**

1. **Find process using port:**

   ```bash
   lsof -i :3000  # Frontend port
   lsof -i :8000  # Backend port
   ```

2. **Kill process:**

   ```bash
   kill -9 <PID>
   ```

3. **Or use different port:**

   ```bash
   docker-compose up -p 8080:3000   # Use port 8080 instead
   ```

4. **Or stop all Docker containers:**
   ```bash
   docker-compose down
   docker kill $(docker ps -q)      # Nuclear option
   ```

---

#### Issue: K8s pod stuck in pending or CrashLoopBackOff

**Symptoms:**

- `kubectl get pods` shows pod not starting
- Status: Pending or CrashLoopBackOff

**Solutions:**

1. **Check pod status:**

   ```bash
   kubectl describe pod <pod-name> -n zeroqwait
   ```

2. **Check logs:**

   ```bash
   kubectl logs <pod-name> -n zeroqwait
   kubectl logs <pod-name> -n zeroqwait --previous  # Previous run
   ```

3. **Check resources:**

   ```bash
   kubectl top nodes
   kubectl top pods -n zeroqwait
   ```

4. **Check events:**

   ```bash
   kubectl get events -n zeroqwait
   kubectl describe node <node-name>
   ```

5. **Redeploy:**
   ```bash
   kubectl delete deployment backend -n zeroqwait
   bash scripts/deploy-k8s.sh
   ```

---

### Debugging Steps (General)

1. **Check logs first:**

   ```bash
   docker-compose logs -f  # or kubectl logs -f
   ```

2. **Check health:**

   ```bash
   docker stats               # Container resources
   curl http://localhost:8000/  # API health
   ```

3. **Check configuration:**

   ```bash
   cat .env
   cat backend/.env
   grep FRONTEND_URL docker-compose.yml
   ```

4. **Test connectivity:**

   ```bash
   curl http://192.168.2.88.nip.io:8000/docs
   ping 192.168.2.88.nip.io
   ```

5. **Check browser:**
   - DevTools → Console (errors?)
   - DevTools → Network (request failures?)
   - DevTools → Application → LocalStorage (token?)

---

## Cleanup & Maintenance

### Regular Cleanup

```bash
# Stop all containers
bash scripts/cleanup.sh

# Or manual
docker-compose down

# Clean up unused images
docker system prune -f

# Clean up unused volumes
docker volume prune -f
```

### Backup Before Cleanup

```bash
# Backup database
docker-compose exec postgres pg_dump -U postgres fastcuts_db > backup.sql

# Backup Docker volumes
docker run --rm -v zeroqwait_postgres:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres-backup.tar.gz /data
```

### Root Directory Cleanup (Optional)

The `/deployment` folder is now your main deployment hub. Old files in root can be removed:

**Safe to delete:**

- `deploy.sh`, `deploy-local.sh`, `deploy-k8s.sh` (now in deployment/)
- `DEPLOYMENT*.md`, `PHASE2_*.md` (consolidated)
- `setup-github-actions.sh`, `build-and-push.sh` (legacy)
- `TEST_RESULTS_AND_CREDENTIALS.md` (security risk)

**See:** `deployment/CLEANUP_GUIDE.md` for detailed list

**Safe to keep:**

- `docker-compose.yml`, `docker-compose.prod.yml`
- `README.md`, `.env`, `.env.example`
- `backend/`, `frontend/`, `deployment/`

---

### Log Rotation

**For Docker:**

```bash
# Add to docker-compose.yml
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**For Kubernetes:**

```bash
# Automatic log rotation
# Check: /var/log/containers/
```

---

## Advanced Topics

### Multi-Shop Setup

Shops are automatically created by shop owners:

1. User registers as shop owner
2. Creates shop (name becomes slug)
3. Slug used as subdomain: `slug.192.168.2.88.nip.io`

**Database structure:**

```sql
users:
  - id
  - email
  - role (shop_owner, employee, customer)
  - subscription_tier

shops:
  - id
  - owner_id (foreign key to users)
  - name (e.g., "Pizza Palace")
  - slug (e.g., "pizza-palace") ← Used for subdomain
  - ...other fields

Other tables:
  - queues
  - employees
  - queue_items
  - All have shop_id for isolation
```

### Custom Domain Setup (Production)

1. **Replace nip.io:**

   ```bash
   # Update .env
   FRONTEND_URL=https://yourdomain.com

   # Update docker-compose.yml
   FRONTEND_URL=https://yourdomain.com

   # Update K8s ConfigMap
   FRONTEND_URL=https://yourdomain.com
   ```

2. **Setup SSL/TLS:**

   ```bash
   # For K8s with cert-manager
   kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/...

   # Add to ingress
   spec:
     tls:
     - hosts:
       - yourdomain.com
       - "*.yourdomain.com"
       secretName: tls-secret
   ```

3. **Update DNS:**
   ```
   yourdomain.com      A  your-ip
   *.yourdomain.com    A  your-ip
   ```

---

### Scaling Considerations

**For small deployment (< 100 shops):**

- Docker Compose on single machine is fine
- Docker Stats + Sentry monitoring sufficient

**For medium deployment (100-1000 shops):**

- Switch to Kubernetes
- Add Prometheus + Grafana for monitoring
- Consider database scaling (managed PostgreSQL)

**For large deployment (1000+ shops):**

- Kubernetes with auto-scaling
- Load balancing across multiple backend pods
- Separate read/write database replicas
- CDN for static assets
- Redis for caching
- DataDog or New Relic for full observability

---

### Environment Variables Reference

**Backend (.env):**

```env
# Database
DB_HOST=postgres           # or your database host
DB_PORT=5432
DB_NAME=fastcuts_db
DB_USER=postgres
DB_PASSWORD=your_password

# JWT
SECRET_KEY=your_secret_key_here

# Frontend (for CORS & emails)
FRONTEND_URL=http://192.168.2.88.nip.io

# Supabase (optional, if using cloud DB)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_key

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_password
```

**Frontend (.env):**

```env
REACT_APP_API_URL=/api    # Relative path (works with subdomains)
```

---

### GitHub Actions (Free CI/CD)

GitHub Actions is completely free and already available in your repo!

**Create `.github/workflows/deploy.yml`:**

```yaml
name: Deploy ZeroQwait

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy
        run: bash deployment/scripts/deploy-k8s.sh
```

**Free limits:**

- Unlimited actions for public repos
- 2,000 minutes/month for private repos
- 20 concurrent jobs

---

## Cost & Tool Comparison

### Monitoring Cost Summary

| Tool         | Monthly Cost | Setup  | Best For            |
| ------------ | ------------ | ------ | ------------------- |
| Docker Stats | $0           | 0 min  | Quick checks        |
| Portainer    | $0           | 2 min  | Visual UI ⭐        |
| Sentry       | $0-99        | 10 min | Error tracking      |
| Prometheus   | $0           | 30 min | Self-hosted metrics |
| Grafana      | $0-99        | 30 min | Dashboards          |
| DataDog      | $15-100      | 15 min | Cloud APM           |
| New Relic    | $50-500      | 15 min | Enterprise          |

**Total free solution:** Docker Stats + Sentry + Prometheus + Grafana = $0  
**Professional solution:** DataDog ($15-100) + Sentry (free)

---

### Deployment Infrastructure Cost

| Type                     | Cost        | Setup   | Best For          |
| ------------------------ | ----------- | ------- | ----------------- |
| Local Docker             | $0          | 15 sec  | Development       |
| Docker Compose           | $0          | 30 sec  | Testing           |
| Kubernetes (self-hosted) | $0-50/month | 2-3 min | Production        |
| Kubernetes (managed)     | $50-300     | varies  | Enterprise        |
| Database (PostgreSQL)    | $0-50/month | -       | Depends on volume |

---

### Free Tools Included

✅ **Docker & Docker Compose** - Container orchestration  
✅ **PostgreSQL** - Database  
✅ **FastAPI** - Backend framework  
✅ **React** - Frontend framework  
✅ **Traefik** - Load balancer/Ingress  
✅ **Prometheus** - Metrics  
✅ **Grafana** - Dashboards  
✅ **GitHub Actions** - CI/CD  
✅ **Sentry** - Error tracking (free tier)

**Total cost for complete setup:** $0

---

## Summary & Next Steps

### What You Have Now

✅ Multi-tenant queue management system  
✅ Shop-based subdomains  
✅ Docker & Kubernetes deployment  
✅ Built-in monitoring support  
✅ Complete documentation  
✅ Organized folder structure

### Recommended Implementation Path

**Phase 1 (This Week):**

1. Deploy locally with `bash scripts/deploy-local.sh`
2. Test subdomain redirect
3. Verify CORS for API calls
4. Check logs with `bash scripts/logs.sh`

**Phase 2 (Before Production):**

1. Setup Docker Stats + Sentry
2. Or install Portainer for visual UI
3. Test production Docker Compose setup
4. Prepare Kubernetes cluster

**Phase 3 (Production Ready):**

1. Deploy to Kubernetes
2. Setup Prometheus + Grafana
3. Configure alerting rules
4. Setup backups & disaster recovery

**Phase 4 (At Scale):**

1. Consider DataDog or New Relic
2. Setup auto-scaling
3. Implement caching (Redis)
4. Optimize database

---

### Key Commands to Remember

```bash
# Deployment
cd deployment && ./deploy.sh

# Monitoring
docker stats                        # Quick stats
docker run -d -p 9000:9000 -v /var/run/docker.sock:/var/run/docker.sock portainer/portainer-ce  # Visual UI
bash scripts/setup-monitoring.sh   # Full monitoring

# Logs
bash scripts/logs.sh
docker-compose logs -f

# Cleanup
bash scripts/cleanup.sh
```

---

### Getting Help

1. **Check logs first:** `bash scripts/logs.sh`
2. **Search issues:** GitHub Issues
3. **Read documentation:** This file has all sections
4. **Troubleshooting section:** Covers 90% of issues

---

**Version:** January 2026  
**Status:** ✅ Production Ready  
**Last Updated:** January 18, 2026

---

## Appendix: Quick Reference Card

### One-Liners

```bash
# Deploy locally in one command
cd deployment && bash scripts/deploy-local.sh

# See everything with one command
docker stats

# Get visual UI for Docker
docker run -d -p 9000:9000 -v /var/run/docker.sock:/var/run/docker.sock portainer/portainer-ce

# View all logs in one place
bash scripts/logs.sh

# Stop everything
bash scripts/cleanup.sh

# Check if API is responding
curl http://192.168.2.88.nip.io:8000/docs
```

### Access URLs

```
Local Docker Frontend:  http://192.168.2.88.nip.io:3000
Local Docker Backend:   http://192.168.2.88.nip.io:8000
Local Docker Docs:      http://192.168.2.88.nip.io:8000/docs

K8s Frontend:           http://192.168.2.88.nip.io
K8s Backend:            http://192.168.2.88.nip.io/api
K8s Docs:               http://192.168.2.88.nip.io/api/docs

Portainer UI:           http://localhost:9000
Prometheus:             http://localhost:9090
Grafana:                http://localhost:3001
```

### File Locations

```
Main deployment:    /deployment/deploy.sh
Scripts:            /deployment/scripts/*.sh
K8s manifests:      /deployment/kubernetes/*.yaml
Monitoring:         /deployment/monitoring/
Backend code:       /backend/
Frontend code:      /frontend/
```

---

**End of Documentation**

This comprehensive guide covers everything from quick start to enterprise monitoring. Start with Phase 1, expand as needed!
