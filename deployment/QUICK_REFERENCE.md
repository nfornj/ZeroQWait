# Deployment Quick Reference Card

## 🚀 One Command Deployments

```bash
# Local Docker (development)
cd deployment && bash scripts/deploy-local.sh

# Kubernetes (production)
cd deployment && bash scripts/deploy-k8s.sh

# Production Docker Compose (staging)
cd deployment && bash scripts/deploy-compose.sh

# Interactive menu
cd deployment && ./deploy.sh
```

---

## 📊 Monitoring

```bash
# Docker stats (real-time)
docker stats

# View deployment logs
cd deployment && bash scripts/logs.sh

# Setup monitoring tools
cd deployment && bash scripts/setup-monitoring.sh
```

**Quick Recommendation:**

1. Start with: Docker Stats (free, built-in)
2. Add: Sentry (error tracking, free tier)
3. Then: Prometheus + Grafana (self-hosted)

---

## 🔍 Debugging

```bash
# Check containers
docker-compose ps
docker-compose logs -f backend

# Check Kubernetes
kubectl get pods -n zeroqwait
kubectl logs -n zeroqwait -l app=backend

# Check health
curl http://192.168.2.88.nip.io:8000/docs
```

---

## 🗑️ Cleanup

```bash
# Stop containers
cd deployment && bash scripts/cleanup.sh

# Or manual
docker-compose down
docker system prune -f
```

---

## 📁 New Directory Structure

```
deployment/
├── deploy.sh                 ← Start here
├── scripts/                  ← All scripts
├── kubernetes/               ← K8s manifests
├── docker/                   ← Docker configs
├── monitoring/               ← Monitoring setup
└── docs/                     ← Documentation
```

---

## 🎯 Access URLs

### Local Docker

- Frontend: http://192.168.2.88.nip.io:3000
- Backend: http://192.168.2.88.nip.io:8000
- Swagger: http://192.168.2.88.nip.io:8000/docs

### Kubernetes

- Frontend: http://192.168.2.88.nip.io
- Backend: http://192.168.2.88.nip.io/api
- Swagger: http://192.168.2.88.nip.io/api/docs

### After Login (Subdomain)

- Shop 1: http://pizza-palace.192.168.2.88.nip.io
- Shop 2: http://coffee-shop.192.168.2.88.nip.io

---

## 📚 Documentation

- `deployment/docs/README.md` - Overview
- `deployment/monitoring/MONITORING_GUIDE.md` - All monitoring options
- `deployment/CLEANUP_GUIDE.md` - Remove old files

---

## ⚠️ Common Issues

| Issue                            | Fix                                                 |
| -------------------------------- | --------------------------------------------------- |
| Can't access 192.168.2.88.nip.io | Check IP, verify DNS: `ping 192.168.2.88.nip.io`    |
| API calls fail                   | Check CORS: `docker-compose logs backend`           |
| Pod won't start                  | Check logs: `kubectl logs -n zeroqwait pod/backend` |
| Port 3000 in use                 | Change port: `docker-compose up -p 8080:3000`       |

---

## 🔄 Common Workflows

### Deploy to local & test

```bash
cd deployment
bash scripts/deploy-local.sh
# Test at: http://192.168.2.88.nip.io:3000
bash scripts/cleanup.sh
```

### Deploy to K8s & monitor

```bash
cd deployment
bash scripts/deploy-k8s.sh
bash scripts/setup-monitoring.sh
bash scripts/logs.sh
```

### Quick health check

```bash
docker stats                    # See resource usage
docker-compose logs --tail=20   # See recent logs
curl http://192.168.2.88.nip.io:8000/docs  # API health
```

---

## 💡 Pro Tips

1. **Monitor from start**: Setup monitoring before issues happen
2. **Check logs first**: 90% of issues are in logs
3. **Use Docker stats**: Quick way to see what's running
4. **Test locally first**: Always test changes locally before production
5. **Keep backups**: Backup before major changes

---

## 📞 Support

1. Check logs: `bash scripts/logs.sh`
2. Read docs: `deployment/docs/`
3. Search issues: GitHub Issues
4. Ask team: Slack/Discord

---

**Status:** ✅ Ready to deploy!

**Next step:** `cd deployment && ./deploy.sh`
