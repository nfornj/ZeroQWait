# Deployment Documentation Index

## 📁 Folder Structure

```
deployment/
├── deploy.sh                           ← Main entry point (interactive menu)
├── scripts/                            ← All deployment scripts
│   ├── deploy-local.sh                 - Local Docker deployment
│   ├── deploy-k8s.sh                   - Kubernetes deployment
│   ├── deploy-compose.sh               - Production Docker Compose
│   ├── logs.sh                         - View logs
│   ├── cleanup.sh                      - Stop containers
│   └── setup-monitoring.sh             - Setup monitoring tools
├── kubernetes/                         ← K8s manifests
│   ├── backend-deployment.yaml
│   ├── frontend-deployment.yaml
│   ├── backend-configmap.yaml
│   ├── backend-secret.yaml
│   ├── postgres-*.yaml
│   ├── ingress-traefik.yaml
│   └── README.md
├── docker/                             ← Docker configs
│   ├── docker-compose.yml              - Development compose
│   ├── docker-compose.prod.yml         - Production compose
│   └── README.md
├── monitoring/                         ← Monitoring setup
│   ├── MONITORING_GUIDE.md             - All monitoring options
│   ├── prometheus-grafana.sh           - Prometheus setup
│   ├── elk-setup.sh                    - ELK Stack setup
│   ├── datadog-setup.md                - DataDog guide
│   └── newrelic-setup.md               - New Relic guide
└── docs/                               ← Documentation
    ├── README.md                       - Deployment overview
    ├── GETTING_STARTED.md              - Quick start
    ├── TROUBLESHOOTING.md              - Common issues
    ├── ARCHITECTURE.md                 - System architecture
    └── MONITORING.md                   - Monitoring setup
```

---

## 🚀 Quick Start

### 1. Choose Your Environment

```bash
cd deployment

# Interactive menu
./deploy.sh

# Or direct deployment
bash scripts/deploy-local.sh      # Local Docker
bash scripts/deploy-k8s.sh        # Kubernetes
bash scripts/deploy-compose.sh    # Production Compose
```

### 2. Monitor Your Deployment

```bash
# View logs
bash scripts/logs.sh

# Setup monitoring
bash scripts/setup-monitoring.sh
```

### 3. Stop/Cleanup

```bash
# Stop everything
bash scripts/cleanup.sh
```

---

## 📚 Documentation Files

### Essential Guides

- **GETTING_STARTED.md** - 5-minute quickstart
- **MONITORING_GUIDE.md** - All monitoring options
- **TROUBLESHOOTING.md** - Common issues & fixes

### Detailed References

- **ARCHITECTURE.md** - How the system works
- **K8s/README.md** - Kubernetes details
- **DOCKER/README.md** - Docker details

---

## 🎯 By Scenario

### I want to test locally

```bash
./deploy.sh
# Choose option 1: Local Docker
```

### I want production setup

```bash
./deploy.sh
# Choose option 2: Kubernetes
# Or option 3: Docker Compose
```

### I want monitoring

```bash
./deploy.sh
# Choose option 6: Monitoring
```

### I want to view logs

```bash
./deploy.sh
# Choose option 4: View Logs
```

### I want to stop everything

```bash
./deploy.sh
# Choose option 5: Cleanup
```

---

## 🔍 Monitoring Recommendation

**For your use case (local testing + future production):**

```
Phase 1 (Now):
✅ Docker Stats (built-in, free)
✅ Sentry (error tracking, free)

Phase 2 (Before production):
✅ Prometheus + Grafana (open-source)
✅ Keep Sentry

Phase 3 (At scale):
✅ Switch to DataDog or New Relic
✅ Keep Sentry
```

See: `monitoring/MONITORING_GUIDE.md` for full details

---

## 🛠️ Deployment Scripts

### deploy-local.sh

Deploys to Docker on your local machine.

```bash
bash scripts/deploy-local.sh
```

- Good for: Development, testing
- Time: ~15 seconds
- Access: http://192.168.2.88.nip.io:3000 & :8000

### deploy-k8s.sh

Deploys to Kubernetes cluster.

```bash
bash scripts/deploy-k8s.sh
```

- Good for: Production, scalability
- Time: ~2-3 minutes
- Requirements: kubectl, K8s cluster
- Access: http://192.168.2.88.nip.io/api

### deploy-compose.sh

Production-like Docker Compose setup.

```bash
bash scripts/deploy-compose.sh
```

- Good for: Staging, testing production setup
- Time: ~30 seconds
- Access: http://192.168.2.88.nip.io

### logs.sh

View logs from running services.

```bash
bash scripts/logs.sh
```

- Options for Docker and Kubernetes
- Real-time log streaming

### cleanup.sh

Stop and remove all containers.

```bash
bash scripts/cleanup.sh
```

- ⚠️ Removes containers (data in volumes persists)
- Use before redeploying

### setup-monitoring.sh

Install monitoring tools.

```bash
bash scripts/setup-monitoring.sh
```

- Options: Prometheus, DataDog, New Relic, ELK
- See MONITORING_GUIDE.md first

---

## 🐳 What Gets Deployed

### Backend (FastAPI)

- Python 3.11
- FastAPI framework
- PostgreSQL connection
- Port: 8000

### Frontend (React)

- Node.js
- React application
- Served via nginx
- Port: 3000 (local) / 80 (K8s)

### Database (PostgreSQL)

- Local development: Docker container
- Production: Can use managed database
- Port: 5432

### Ingress (K8s only)

- Traefik load balancer
- Handles subdomain routing
- TLS termination ready

---

## 📊 Monitoring Tools

| Tool         | Setup    | Cost | Best For             |
| ------------ | -------- | ---- | -------------------- |
| Docker Stats | Built-in | Free | Quick checks         |
| Sentry       | 10 min   | Free | Error tracking       |
| Prometheus   | 30 min   | Free | Metrics & history    |
| Grafana      | 30 min   | Free | Beautiful dashboards |
| DataDog      | 15 min   | $$   | Cloud solution       |
| New Relic    | 15 min   | $$$  | Enterprise APM       |

**Recommended:** Start with Docker Stats + Sentry, upgrade to Prometheus + Grafana

---

## 🔐 Environment Variables

Key files to check/update:

- `.env` - Backend configuration
- `.env.example` - Template
- `backend/.env` - Backend secrets

Required variables:

```
SUPABASE_URL=...
SUPABASE_KEY=...
SECRET_KEY=...
FRONTEND_URL=http://192.168.2.88.nip.io
```

---

## 📱 Accessing Your App

### Local Docker

```
Frontend:  http://192.168.2.88.nip.io:3000
Backend:   http://192.168.2.88.nip.io:8000
Swagger:   http://192.168.2.88.nip.io:8000/docs
```

### Kubernetes

```
Frontend:  http://192.168.2.88.nip.io/
Backend:   http://192.168.2.88.nip.io/api
Swagger:   http://192.168.2.88.nip.io/api/docs
```

### After Login

```
Shop 1:    http://shopname1.192.168.2.88.nip.io/
Shop 2:    http://shopname2.192.168.2.88.nip.io/
```

---

## 🆘 Need Help?

1. **Check logs:** `bash scripts/logs.sh`
2. **Read troubleshooting:** See `TROUBLESHOOTING.md`
3. **Review architecture:** See `ARCHITECTURE.md`
4. **Check monitoring:** See `MONITORING_GUIDE.md`

---

## ✅ Deployment Checklist

Before deploying to production:

- [ ] All environment variables set
- [ ] Database backups configured
- [ ] Monitoring set up
- [ ] Alerting rules defined
- [ ] SSL certificates ready
- [ ] Domain configured
- [ ] DNS records updated
- [ ] Disaster recovery plan
- [ ] Team trained on runbooks
- [ ] Load tested

---

**Last Updated:** January 18, 2026  
**Status:** Ready for deployment  
**Questions?** Check the documentation or run `./deploy.sh`
