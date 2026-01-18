# Deployment Monitoring Guide

## Overview

Monitoring is critical for production deployments. This guide covers recommended tools and setup for each deployment type.

---

## 🎯 Quick Recommendation Matrix

| Tool                     | Cost    | Setup Time | Best For                  | Learning Curve |
| ------------------------ | ------- | ---------- | ------------------------- | -------------- |
| **Prometheus + Grafana** | Free    | 30 min     | Self-hosted, full control | Medium         |
| **Docker Stats**         | Free    | 5 min      | Basic Docker monitoring   | Easy           |
| **cAdvisor**             | Free    | 15 min     | Container metrics         | Medium         |
| **DataDog**              | $$      | 10 min     | Cloud, scalable           | Easy           |
| **New Relic**            | $$$     | 10 min     | Full APM, enterprise      | Easy           |
| **ELK Stack**            | Free    | 1 hour     | Log aggregation           | Hard           |
| **Sentry**               | Free/$  | 10 min     | Error tracking            | Easy           |
| **Grafana Cloud**        | Free/$$ | 15 min     | Managed Prometheus        | Medium         |

---

## 🏆 Recommended Setup (For Your Use Case)

### Development/Testing (Local Docker)

```
✅ Docker Stats (built-in)
✅ Docker Dashboard
```

**Why:** Minimal overhead, see everything with `docker stats`

### Production (Kubernetes)

```
✅ Prometheus (metrics)
✅ Grafana (visualization)
✅ Sentry (error tracking)
```

**Why:** Industry standard, open-source, scalable, free

---

## 1️⃣ DOCKER STATS (Easiest - No Setup!)

Already built into Docker. Perfect for quick monitoring.

```bash
# See all containers
docker stats

# See specific container
docker stats zeroqwait-backend

# Export to CSV
docker stats --no-stream > stats.txt
```

**Metrics:**

- CPU usage
- Memory usage
- Network I/O
- Block I/O

**Pros:** ✅ Zero setup, ✅ Real-time, ✅ Built-in
**Cons:** ❌ No history, ❌ No alerting, ❌ No UI

---

## 2️⃣ PROMETHEUS + GRAFANA (Best for Self-Hosted)

### Why Prometheus?

- Lightweight metrics database
- Time-series data
- Powerful query language (PromQL)
- Free and open-source

### Why Grafana?

- Beautiful dashboards
- Alerting
- Multi-source support
- Community templates

### Setup (30 minutes)

#### For Docker:

```bash
# 1. Add Prometheus service to docker-compose.yml
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-storage:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-storage:/var/lib/grafana

volumes:
  prometheus-storage:
  grafana-storage:

# 2. Create prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'docker'
    static_configs:
      - targets: ['localhost:8000', 'localhost:3000']

# 3. Start
docker-compose up -d

# 4. Access
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3001 (admin/admin)
```

#### For Kubernetes:

```bash
# 1. Install via Helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack -n zeroqwait

# 2. Access Grafana
kubectl port-forward -n zeroqwait svc/prometheus-grafana 3000:80

# 3. Open http://localhost:3000
# Default: admin/prom-operator
```

### Key Metrics to Monitor

**Backend:**

- Request rate (req/sec)
- Response time (p50, p95, p99)
- Error rate
- Database connections
- CPU usage
- Memory usage

**Frontend:**

- Page load time
- Bundle size
- API call latency
- Errors/crashes

**Infrastructure:**

- CPU usage
- Memory usage
- Disk I/O
- Network I/O

---

## 3️⃣ SENTRY (Error Tracking - Easiest Setup!)

### Why Sentry?

- Automatic error tracking
- JavaScript/Python support
- Beautiful error reports
- Free tier available

### Setup (10 minutes)

#### Backend (Python/FastAPI):

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="https://your-dsn@sentry.io/your-project-id",
    integrations=[FastApiIntegration()],
    traces_sample_rate=1.0,
)
```

#### Frontend (React):

```javascript
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: "https://your-dsn@sentry.io/your-project-id",
  integrations: [
    new Sentry.Replay({
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],
  tracesSampleRate: 1.0,
});
```

### Access:

- https://sentry.io (free account)
- Dashboard shows all errors in real-time
- Integrates with Slack/Teams

---

## 4️⃣ DATADOG (Cloud-Based - Most Features)

### Why DataDog?

- APM (Application Performance Monitoring)
- Infrastructure monitoring
- Log management
- Alerting
- Beautiful dashboards

### Cost:

- Free tier: Up to 5 hosts
- Pro: $15/host/month

### Setup (10 minutes):

```bash
# 1. Sign up: https://www.datadoghq.com
# 2. Install agent on your machine/server
# 3. Docker integration:

# Add to docker-compose.yml:
services:
  datadog:
    image: datadog/agent:latest
    environment:
      - DD_API_KEY=your_api_key
      - DD_SITE=datadoghq.com
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /proc/:/host/proc/:ro
      - /sys/fs/cgroup/:/host/sys/fs/cgroup:ro

# 4. Access dashboard: https://app.datadoghq.com
```

---

## 5️⃣ NEW RELIC (Enterprise APM)

### Why New Relic?

- Full Application Performance Monitoring
- Infrastructure monitoring
- Real user monitoring
- Powerful alerting

### Cost:

- Free tier: 100GB/month
- Standard: $0.30/GB

### Setup (15 minutes):

```bash
# 1. Sign up: https://newrelic.com
# 2. Get license key
# 3. Python agent:

pip install newrelic

# 4. FastAPI:
NEW_RELIC_CONFIG_FILE=newrelic.ini newrelic-admin run-program uvicorn main:app

# 5. React:
# Import the browser agent in index.html before React app

# 6. View APM: https://one.newrelic.com
```

---

## 6️⃣ ELK STACK (For Log Aggregation)

### Why ELK?

- Elasticsearch: Store and search logs
- Logstash: Process and transform logs
- Kibana: Visualization

### When to use:

- Large-scale deployments
- Complex log analysis
- Long-term log retention

### Setup (1 hour):

```bash
# Use docker-compose with ELK services
docker-compose -f docker-compose.elk.yml up -d

# Access Kibana: http://localhost:5601
```

---

## 📊 My Recommendation for Your Setup

### Phase 1 (Now) - Get Started Fast

```
✅ Docker Stats (free, built-in)
✅ Sentry (free tier, easy setup)
```

**Why:** Zero cost, minimal setup, covers errors + basic metrics

### Phase 2 (Before Production) - Full Monitoring

```
✅ Prometheus + Grafana (self-hosted)
✅ Sentry (error tracking)
✅ Docker compose health checks
```

**Why:** Production-ready, no cost, full visibility

### Phase 3 (At Scale) - Professional Monitoring

```
✅ DataDog or New Relic (choose 1)
✅ Managed logs (DataDog Logs or New Relic)
```

**Why:** Less maintenance, better support, enterprise features

---

## 🚨 Critical Metrics to Monitor

### Always Monitor:

1. **Error Rate** - % of failed requests
2. **Response Time** - API latency
3. **Uptime** - Service availability
4. **CPU Usage** - Resource utilization
5. **Memory Usage** - Memory leaks detection
6. **Disk Space** - Storage issues

### Alert Thresholds:

```
Error Rate > 5% → ALERT
Response Time > 1s → WARNING
CPU > 80% → WARNING, CPU > 95% → ALERT
Memory > 85% → WARNING, Memory > 95% → ALERT
Disk > 90% → WARNING, Disk > 95% → ALERT
Uptime < 99% → ALERT
```

---

## 🔔 Alerting Setup

### Sentry Alerts:

- All errors automatically create alerts
- Integrates with Slack
- Custom rules available

### Prometheus + Grafana:

```yaml
# prometheus.yml
alert_rules:
  - alert: HighErrorRate
    expr: rate(requests_failed[5m]) > 0.05
    for: 5m
    annotations:
      summary: "High error rate detected"

  - alert: HighLatency
    expr: response_time_p95 > 1000
    for: 5m
    annotations:
      summary: "High response latency"
```

### With Slack Integration:

```
Grafana → Notification Channel → Slack
```

---

## 💡 Best Practices

1. **Monitor what matters**
   - Business metrics (revenue, conversions)
   - User experience (latency, errors)
   - System health (CPU, memory, disk)

2. **Set meaningful alerts**
   - Alert on symptoms, not metrics
   - Avoid alert fatigue
   - Clear escalation paths

3. **Keep history**
   - Retention: 30+ days for metrics
   - Retention: 1+ year for logs
   - Helps with troubleshooting

4. **Test your alerts**
   - Fire test alerts
   - Verify notifications work
   - Document runbooks for responses

5. **Dashboard design**
   - One dashboard per role
   - High-level metrics first
   - Drill-down capability

---

## 🎯 Monitoring Commands Reference

### Docker Stats

```bash
docker stats                    # All containers
docker stats --no-stream        # One-time snapshot
```

### Docker Events

```bash
docker events --filter 'type=container'
```

### Container Health

```bash
docker inspect <container> | grep -A 5 '"Health"'
```

### Kubernetes Monitoring

```bash
kubectl top nodes               # Node metrics
kubectl top pods -n zeroqwait   # Pod metrics
kubectl get events -n zeroqwait # Recent events
```

---

## 📝 Setup Checklist

- [ ] Choose monitoring tool(s)
- [ ] Create monitoring account/credentials
- [ ] Install agent/exporter
- [ ] Configure dashboards
- [ ] Set up alerts
- [ ] Test alerting channels
- [ ] Document dashboards
- [ ] Train team on dashboards
- [ ] Set up on-call rotation
- [ ] Regular alert review

---

## Summary

| Environment | Recommended          | Cost   | Setup Time |
| ----------- | -------------------- | ------ | ---------- |
| Local Dev   | Docker Stats         | Free   | 5 min      |
| Testing     | Prometheus + Grafana | Free   | 30 min     |
| Production  | DataDog or New Relic | $$     | 15 min     |
| Logs        | ELK or Grafana Loki  | Free/$ | 1 hour     |

**Start with:** Docker Stats + Sentry  
**Graduate to:** Prometheus + Grafana + Sentry  
**Enterprise:** DataDog or New Relic

---

Next: Run `bash scripts/setup-monitoring.sh` to get started!
