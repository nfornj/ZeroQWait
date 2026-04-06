# Kubernetes Monitoring System - Complete Guide

## Overview
A complete monitoring stack for your **ZeroQwait Kubernetes cluster** deployed in the `monitoring` namespace.

**Components:**
- **Prometheus** (v2.x) — Metrics collection and time-series database
- **Grafana** (latest) — Visualization, dashboards, and alerting UI
- **kube-state-metrics** — Kubernetes object instrumentation (pod, deployment, stateful set metrics)
- **node-exporter** — System-level metrics (CPU, memory, disk, processes, network)

---

## Quick Start

### 1. Access Grafana Dashboard
**Remote Access (via Traefik ingress):**
```
http://grafana.192.168.2.88.nip.io
```

**Local Port-Forward:**
```bash
kubectl port-forward -n monitoring svc/grafana 3000:3000
# Then visit http://localhost:3000
```

**Credentials:**
- Username: `admin`
- Password: `admin`

### 2. Access Prometheus UI
**Query endpoint for debugging:**
```bash
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# Then visit http://localhost:9090
```

---

## Metrics Collected

### Node/System Metrics (node-exporter)
```
node_cpu_seconds_total         → CPU utilization
node_memory_MemTotal_bytes     → Total system memory
node_memory_MemAvailable_bytes → Available memory
node_disk_io_reads_completed_total      → Disk reads
node_disk_io_writes_completed_total     → Disk writes
node_network_receive_bytes_total        → Network RX bytes
node_network_transmit_bytes_total       → Network TX bytes
node_processes_running         → Number of running processes
node_load1 / load5 / load15    → System load average
```

### Kubernetes Metrics (kube-state-metrics)
```
kube_pod_status_phase          → Pod lifecycle status (Running, Pending, Failed)
kube_pod_container_status_ready → Container readiness
kube_deployment_status_replicas_available → Deployment replica count
kube_node_status_ready         → Node status
kube_namespace_status_phase    → Namespace status
kube_persistentvolumeclaim_status_phase → PVC status
kube_pod_resource_requests    → Resource requests (CPU, memory)
kube_pod_resource_limits       → Resource limits (CPU, memory)
```

### Application Metrics (Pod Annotations)
Pods annotated with these labels are auto-scraped:
```yaml
annotations:
  prometheus.io/scrape: "true"      # Enable scraping
  prometheus.io/port: "8080"        # Metrics port
  prometheus.io/path: "/metrics"    # Metrics endpoint
```

---

## Pre-Built Dashboards

### Kubernetes Cluster Monitoring Dashboard
Displays:
- **CPU Utilization %** across all nodes
- **Memory Usage** (bytes) per node
- **Running Processes** count
- **Load Average** (1-minute)
- **Network I/O** (bytes in/out)
- **Pod Status Distribution**
- **Deployment Replica Status**

**Access:** Grafana → Dashboards → Kubernetes Cluster Monitoring

---

## Key Prometheus Queries

### CPU Usage
```promql
# CPU utilization percentage (all nodes)
100 - (avg(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Per-node CPU
sum(rate(node_cpu_seconds_total[5m])) by (instance) / on(instance) group_left() count(node_cpu_seconds_total) by (instance)
```

### Memory Usage
```promql
# Total memory used
node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes

# Memory percentage
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# Per-pod memory usage
sum(container_memory_working_set_bytes) by (pod_name)
```

### Pod Metrics
```promql
# Pod status
count(kube_pod_status_phase{phase="Running"})

# Pod restarts
rate(kube_pod_container_status_restarts_total[5m])

# Pod CPU requests
sum(kube_pod_resource_requests{resource="cpu"}) by (namespace)

# Pod memory requests
sum(kube_pod_resource_requests{resource="memory"}) by (namespace)
```

### ZeroQwait App Metrics
```promql
# Backend replicas
count(kube_pod_status_phase{namespace="zeroqwait", pod=~"backend.*", phase="Running"})

# Frontend uptime
up{job="kubernetes-pods-zeroqwait", pod=~"frontend.*"}

# Database ready status
kube_pod_container_status_ready{namespace="zeroqwait", pod=~"postgres.*"}
```

---

## Scrape Targets

Prometheus auto-discovers targets in these categories:

### 1. Kubernetes API Server
- **Job:** `kubernetes-apiservers`
- **Endpoint:** K3s API server metrics

### 2. Kubernetes Nodes (kubelet)
- **Job:** `kubernetes-nodes`
- **Endpoint:** `/metrics` on each node's kubelet

### 3. kube-state-metrics
- **Job:** `kube-state-metrics`
- **Namespace:** monitoring
- **Port:** 8080
- **Metrics:** K8s object state

### 4. node-exporter
- **Job:** `node-exporter`
- **Namespace:** monitoring
- **Port:** 9100
- **Metrics:** System-level metrics (CPU, memory, disk, network, processes)

### 5. Application Pods (zeroqwait namespace)
- **Job:** `kubernetes-pods-zeroqwait`
- **Discovery:** Pod annotations `prometheus.io/scrape: "true"`
- **Ports:** Dynamically discovered from `prometheus.io/port` annotation

### 6. LLM Pods (Ollama, Whisper, Qwen TTS)
- **Job:** `kubernetes-pods-llm`
- **Namespace:** llm

### 7. Traefik Ingress
- **Job:** `traefik`
- **Endpoint:** localhost:8080
- **Metrics:** HTTP request counts, latencies, status codes

---

## Grafana Dashboard Management

### Add a New Dashboard

1. **Create via UI:**
   - Grafana → Create → Dashboard
   - Add panels with PromQL queries
   - Save with name tags

2. **Create via ConfigMap:**
   ```bash
   # Create dashboard JSON
   cat > my-dashboard.json << 'EOF'
   {
     "dashboard": {
       "title": "My Dashboard",
       "panels": [...]
     }
   }
   EOF

   # Add to monitoring-namespace
   kubectl create configmap my-dashboard --from-file=my-dashboard.json -n monitoring
   ```

### Export Dashboard
- Grafana → Dashboard → Settings → Export JSON
- Save for version control in `k8s-manifests/grafana-dashboards/`

---

## Creating Custom Alerts

Prometheus can evaluate alert rules and trigger webhooks. To add alerts:

1. Create AlertRule ConfigMap:
   ```yaml
   apiVersion: v1
   kind: ConfigMap
   metadata:
     name: prometheus-alerts
     namespace: monitoring
   data:
     alerts.yml: |
       groups:
         - name: zeroqwait
           interval: 30s
           rules:
             - alert: HighCPUUsage
               expr: 'node_cpu_seconds_total > 80'
               for: 5m
               annotations:
                 summary: "CPU usage above 80%"
   ```

2. Mount in Prometheus ConfigMap and reference:
   ```yaml
   rule_files:
     - /etc/prometheus/alerts.yml
   ```

---

## Retention Policy

**Current Settings:**
- **Metrics retention:** 30 days (`--storage.tsdb.retention.time=30d`)
- **Storage:** 20Gi PVC (`prometheus-pvc`)

**Modify retention:**
```bash
# Edit Prometheus deployment
kubectl edit deployment prometheus -n monitoring

# Change args:
# --storage.tsdb.retention.time=60d  # For 60 days
# --storage.tsdb.retention.size=10gb  # Or by storage size
```

---

## Grafana Datasource Configuration

**Pre-configured datasource:**
- **Name:** Prometheus
- **URL:** `http://prometheus:9090`
- **Access:** proxy
- **Default:** Yes

**Test connection:**
- Grafana → Configuration → Data sources → Prometheus → Test

---

## Storage & PVCs

```bash
# Check persistent volumes
kubectl get pvc -n monitoring

# Monitor storage usage
kubectl exec -n monitoring prometheus-<pod> -- df -h /prometheus
kubectl exec -n monitoring grafana-<pod> -- df -h /var/lib/grafana
```

**Cleanup old data** (if needed):
```bash
# Scale down Prometheus
kubectl scale deployment prometheus --replicas=0 -n monitoring

# Remove PVC
kubectl delete pvc prometheus-pvc -n monitoring

# Recreate PVC
kubectl apply -f k8s-manifests/monitoring-pvc.yaml

# Scale back up
kubectl scale deployment prometheus --replicas=1 -n monitoring
```

---

## Troubleshooting

### Prometheus not scraping targets
```bash
# Check Prometheus targets UI
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# Visit http://localhost:9090/targets

# Check RBAC permissions
kubectl describe clusterrole prometheus -n monitoring

# Check logs
kubectl logs -n monitoring deployment/prometheus | grep scrape
```

### Grafana can't connect to Prometheus
```bash
# Test connectivity from Grafana pod
kubectl exec -n monitoring grafana-<pod> -- \
  curl -v http://prometheus:9090/api/v1/query?query=up

# Check Prometheus service DNS
kubectl exec -n monitoring grafana-<pod> -- nslookup prometheus.monitoring.svc.cluster.local
```

### High memory usage
```bash
# Check retention settings
kubectl get deployment prometheus -n monitoring -o yaml | grep retention

# Reduce retention or increase memory limit
kubectl edit deployment prometheus -n monitoring
```

### Metrics missing from node-exporter
```bash
# Check node-exporter logs
kubectl logs -n monitoring daemonset/node-exporter

# Verify collectors are enabled
kubectl exec -n monitoring node-exporter-<pod> -- \
  /bin/node_exporter --help | grep collector
```

---

## Next Steps

1. **Add custom alerts** for ZeroQwait services (high CPU, OOM, pod crashes)
2. **Create service SLO dashboards** (TTFS, error rates, latency)
3. **Set up AlertManager** for slack/email notifications
4. **Integrate with external systems** (DataDog, New Relic, ELK stack)
5. **Add log aggregation** (Loki, ELK, Splunk)

---

## File References

```
k8s-manifests/
├── monitoring-namespace.yaml          # Monitoring namespace
├── monitoring-pvc.yaml                # Persistent volumes
├── prometheus-config.yaml             # Prometheus scrape config + rules
├── prometheus-deployment.yaml         # Prometheus deployment + RBAC
├── kube-state-metrics-deployment.yaml # K8s metrics exporter
├── node-exporter-daemonset.yaml       # System metrics exporter
├── grafana-config.yaml                # Grafana datasources + dashboards
└── grafana-deployment.yaml            # Grafana deployment + ingress
```

---

## Commands Reference

```bash
# Check monitoring namespace
kubectl get all -n monitoring

# Stream Prometheus logs
kubectl logs -f -n monitoring deployment/prometheus

# Port-forward to Grafana
kubectl port-forward -n monitoring svc/grafana 3000:3000

# Port-forward to Prometheus
kubectl port-forward -n monitoring svc/prometheus 9090:9090

# Execute PromQL from CLI
kubectl exec -n monitoring prometheus-<pod> -- \
  curl 'http://localhost:9090/api/v1/query?query=up[5m]'

# Delete entire monitoring stack
kubectl delete namespace monitoring
```

---

**Deployed:** April 6, 2026
**Last updated:** 2026-04-06
**Status:** ✓ All components running
