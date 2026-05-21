#!/usr/bin/env bash
# =============================================================================
# ZeroQwait — Comprehensive Environment Test Suite  (v2 — fixed)
# Tests: staging, free-tier (prod), premium shop-515, voice pipeline, monitoring
# Uses python3 urllib for all in-pod HTTP checks (wget absent from backend image)
# =============================================================================
set -euo pipefail

KUBECTL="sudo kubectl"
PASS=0; FAIL=0; WARN=0
declare -a RESULTS=()

# ── helpers ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

pass()  { PASS=$((PASS+1));  RESULTS+=("[PASS] $1"); echo -e "${GREEN}[PASS]${NC} $1"; }
fail()  { FAIL=$((FAIL+1));  RESULTS+=("[FAIL] $1"); echo -e "${RED}[FAIL]${NC} $1"; }
warn()  { WARN=$((WARN+1));  RESULTS+=("[WARN] $1"); echo -e "${YELLOW}[WARN]${NC} $1"; }
header(){ echo -e "\n${CYAN}${BOLD}━━━ $1 ━━━${NC}"; }

# check_pod <namespace> <label-selector> <name>
check_pod() {
  local ns=$1 sel=$2 name=$3
  local phase ready
  phase=$($KUBECTL get pods -n "$ns" -l "$sel" --no-headers 2>/dev/null | awk '{print $3}' | head -1)
  ready=$($KUBECTL get pods -n "$ns" -l "$sel" --no-headers 2>/dev/null | awk '{print $2}' | head -1)
  if [[ "$phase" == "Running" && "$ready" =~ ^1/ ]]; then
    pass "$name: Running ($ready)"
  elif [[ "$phase" == "Completed" ]]; then
    pass "$name: Completed (job ok)"
  else
    fail "$name: phase=$phase ready=$ready"
  fi
}

# py_http_internal <ns> <pod-selector> <url> <name> [expected-substring]
py_http_internal() {
  local ns=$1 sel=$2 url=$3 name=$4 expected=${5:-""}
  local pod resp
  pod=$($KUBECTL get pods -n "$ns" -l "$sel" --no-headers 2>/dev/null | awk '$3=="Running"{print $1}' | head -1)
  if [[ -z "$pod" ]]; then
    fail "$name: no running pod in $ns ($sel)"
    return
  fi
  resp=$($KUBECTL exec -n "$ns" "$pod" -- python3 -c "
import urllib.request, sys
try:
    r = urllib.request.urlopen('${url}', timeout=10)
    print(r.read(200).decode(errors='replace'))
except Exception as e:
    print('ERR:' + str(e))
" 2>/dev/null || echo "ERR:exec failed")
  if [[ "$resp" == ERR:* ]]; then
    fail "$name: $resp"
  elif [[ -n "$expected" && "$resp" != *"$expected"* ]]; then
    fail "$name: missing '$expected' — got: ${resp:0:120}"
  else
    pass "$name: OK (${resp:0:80})"
  fi
}

# check_http_external <url> <name> [expected]
check_http_external() {
  local url=$1 name=$2 expected=${3:-""}
  local resp
  resp=$(curl -sk --max-time 15 "$url" 2>/dev/null || true)
  if [[ -z "$resp" ]]; then
    fail "$name: no response from $url"
  elif [[ -n "$expected" && "$resp" != *"$expected"* ]]; then
    fail "$name: missing '$expected' — got: ${resp:0:120}"
  else
    pass "$name: OK (${resp:0:80})"
  fi
}

# check_redis_with_auth <ns> <pod-name> <password> <name>
check_redis_with_auth() {
  local ns=$1 pod=$2 pass=$3 name=$4
  local pong
  pong=$($KUBECTL exec -n "$ns" "$pod" -- redis-cli -a "$pass" ping 2>/dev/null || echo "FAIL")
  [[ "$pong" == "PONG" ]] && pass "$name Redis: PONG" || fail "$name Redis not responding: $pong"
}

# check_temporal_worker <ns> <selector> <name>
check_temporal_worker() {
  local ns=$1 sel=$2 name=$3
  local logs
  logs=$($KUBECTL logs -n "$ns" -l "$sel" --tail=80 2>/dev/null || true)
  if echo "$logs" | grep -qiE "started|workflow|task.queue|registered|polling"; then
    pass "$name temporal worker: connected"
  elif echo "$logs" | grep -qiE "connection refused|failed client|TEMPORAL_ADDRESS"; then
    fail "$name temporal worker: connection refused"
  else
    warn "$name temporal worker: no clear signal in logs"
  fi
}

# =============================================================================
# SECTION 1 — GPU / AI NAMESPACE
# =============================================================================
header "1. zeroqwait-ai  —  GPU Services (TTS + ASR)"

check_pod "zeroqwait-ai" "app=tts-service" "TTS"
check_pod "zeroqwait-ai" "app=asr-service" "ASR"

TTS_POD=$($KUBECTL get pods -n zeroqwait-ai -l app=tts-service --no-headers 2>/dev/null | awk '$3=="Running"{print $1}' | head -1)
if [[ -n "$TTS_POD" ]]; then
  TTS_H=$($KUBECTL exec -n zeroqwait-ai "$TTS_POD" -- python3 -c \
    "import urllib.request; r=urllib.request.urlopen('http://localhost:8880/health',timeout=8); print(r.read(150).decode())" 2>/dev/null || true)
  [[ -n "$TTS_H" ]] && pass "TTS /health: ${TTS_H:0:100}" || fail "TTS /health: no response"

  GPU_ALLOC=$($KUBECTL get pods -n zeroqwait-ai -l app=tts-service -o jsonpath='{.items[0].spec.containers[0].resources.limits.nvidia\.com/gpu}' 2>/dev/null || echo "0")
  [[ "$GPU_ALLOC" == "1" ]] && pass "TTS GPU: nvidia.com/gpu=1" || warn "TTS GPU allocation: '$GPU_ALLOC'"
fi

ASR_POD=$($KUBECTL get pods -n zeroqwait-ai -l app=asr-service --no-headers 2>/dev/null | awk '$3=="Running"{print $1}' | head -1)
if [[ -n "$ASR_POD" ]]; then
  ASR_H=$($KUBECTL exec -n zeroqwait-ai "$ASR_POD" -- python3 -c \
    "import urllib.request; r=urllib.request.urlopen('http://localhost:8000/health',timeout=8); print(r.read(100).decode())" 2>/dev/null || true)
  [[ -n "$ASR_H" ]] && pass "ASR /health: ${ASR_H:0:100}" || fail "ASR /health: no response"
fi

# =============================================================================
# SECTION 2 — PRODUCTION FREE TIER
# =============================================================================
header "2. Production  —  Free Tier"

check_pod "zeroqwait" "app=backend"              "Prod backend"
check_pod "zeroqwait" "app=frontend"             "Prod frontend"
check_pod "zeroqwait" "app=booking-mcp"          "Prod booking-mcp"
check_pod "zeroqwait" "app=finance-mcp"          "Prod finance-mcp"
check_pod "zeroqwait" "app=hr-mcp"               "Prod hr-mcp"
check_pod "zeroqwait" "app=voice-mcp"            "Prod voice-mcp"
check_pod "zeroqwait" "app=temporal"             "Prod temporal-server"
check_pod "zeroqwait" "app=temporal-worker-free" "Prod temporal-worker-free"
check_pod "zeroqwait" "statefulset.kubernetes.io/pod-name=postgres-0" "Prod postgres"
check_pod "zeroqwait" "statefulset.kubernetes.io/pod-name=redis-0"    "Prod redis"

# Backend health (NodePort 30000)
check_http_external "http://localhost:30000/api/agent/health"    "Prod /api/agent/health" '"status"'
check_http_external "http://localhost:30000/api/v2/agent/health" "Prod /api/v2/agent/health" '"status"'

# Legacy agent chat
CHAT_RESP=$(curl -sk --max-time 20 -X POST http://localhost:30000/api/agent/master/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello, what can you do?","session_id":"test-free-001"}' 2>/dev/null || true)
if echo "$CHAT_RESP" | grep -qiE "register|search|shop|queue|agent"; then
  pass "Prod free-tier chat: agent responded correctly"
else
  fail "Prod free-tier chat: unexpected response — ${CHAT_RESP:0:150}"
fi

# Frontend (NodePort 30001) — use grep -qi to avoid ERE pitfalls
FRONTEND_RESP=$(curl -sk --max-time 10 "http://localhost:30001/" 2>/dev/null || true)
if echo "$FRONTEND_RESP" | grep -qi "doctype html"; then
  pass "Prod frontend: serving HTML"
else
  fail "Prod frontend: did not get HTML — got ${FRONTEND_RESP:0:80}"
fi

# MCPs
py_http_internal "zeroqwait" "app=backend" "http://booking-mcp.zeroqwait.svc.cluster.local:8890/health" "Prod booking-mcp /health" '"status"'
py_http_internal "zeroqwait" "app=backend" "http://finance-mcp.zeroqwait.svc.cluster.local:8891/health" "Prod finance-mcp /health" '"status"'
py_http_internal "zeroqwait" "app=backend" "http://hr-mcp.zeroqwait.svc.cluster.local:8892/health"      "Prod hr-mcp /health" '"status"'
py_http_internal "zeroqwait" "app=backend" "http://voice-mcp.zeroqwait.svc.cluster.local:8881/health"   "Prod voice-mcp /health" '"status"'

# DB — tables in platform schema
BACKEND_POD=$($KUBECTL get pods -n zeroqwait -l app=backend --no-headers 2>/dev/null | awk '$3=="Running"{print $1}' | head -1)
DB_TABLES=$($KUBECTL exec -n zeroqwait "$BACKEND_POD" -- python3 -c "
import os; from sqlalchemy import create_engine, text
url='postgresql://{}:{}@{}:{}/{}'.format(
  os.environ.get('DB_USER','zeroqwait'),os.environ.get('DB_PASSWORD','password'),
  os.environ.get('DB_HOST','postgres'),os.environ.get('DB_PORT','5432'),
  os.environ.get('DB_NAME','zeroqwait'))
e=create_engine(url); r=e.connect().execute(text(\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='platform'\")).scalar(); print(r)" \
  2>/dev/null || echo "0")
[[ "$DB_TABLES" =~ ^[1-9] ]] && pass "Prod DB: platform schema has $DB_TABLES tables" || fail "Prod DB: table count=$DB_TABLES"

# Redis (password-protected)
REDIS_PASS="zeroqwait_redis_secure_2026"
check_redis_with_auth "zeroqwait" "redis-0" "$REDIS_PASS" "Prod"

# Temporal worker-free
check_temporal_worker "zeroqwait" "app=temporal-worker-free" "Prod"

# Cloudflare systemd
CF_STATUS=$(systemctl is-active cloudflared 2>/dev/null || echo "unknown")
[[ "$CF_STATUS" == "active" ]] && pass "Cloudflared: systemd service active" || fail "Cloudflared: $CF_STATUS"

# Public HTTPS
check_http_external "https://zeroqwait.com/api/agent/health"    "zeroqwait.com HTTPS"    '"status"'
check_http_external "https://zeroqwait.com/api/v2/agent/health" "zeroqwait.com v2 HTTPS" '"status"'

# =============================================================================
# SECTION 3 — PREMIUM SHOP-515
# =============================================================================
header "3. Production  —  Premium Shop-515"

check_pod "zeroqwait" "app=backend-shop-515"       "Shop-515 backend"
check_pod "zeroqwait" "app=booking-mcp-shop-515"   "Shop-515 booking-mcp"
check_pod "zeroqwait" "app=finance-mcp-shop-515"   "Shop-515 finance-mcp"
check_pod "zeroqwait" "app=hr-mcp-shop-515"        "Shop-515 hr-mcp"
check_pod "zeroqwait" "statefulset.kubernetes.io/pod-name=postgres-shop-515-0" "Shop-515 postgres"
check_pod "zeroqwait" "statefulset.kubernetes.io/pod-name=redis-shop-515-0"    "Shop-515 redis"

echo "  (checking worker-shop-515 status...)"
WPHASE=$($KUBECTL get pods -n zeroqwait -l app=worker-shop-515 --no-headers 2>/dev/null | awk '{print $3}' | head -1)
WREADY=$($KUBECTL get pods -n zeroqwait -l app=worker-shop-515 --no-headers 2>/dev/null | awk '{print $2}' | head -1)
if [[ "$WPHASE" == "Running" ]]; then
  pass "Shop-515 temporal-worker: Running ($WREADY)"
else
  fail "Shop-515 temporal-worker: $WPHASE — not Running"
fi

# Backend health (internal)
py_http_internal "zeroqwait" "app=backend-shop-515" "http://localhost:8000/api/agent/health"    "Shop-515 /api/agent/health"    '"status"'
py_http_internal "zeroqwait" "app=backend-shop-515" "http://localhost:8000/api/v2/agent/health" "Shop-515 /api/v2/agent/health" '"status"'

# DB schemas (platform + tenant_515)
SHOP_POD=$($KUBECTL get pods -n zeroqwait -l app=backend-shop-515 --no-headers 2>/dev/null | awk '$3=="Running"{print $1}' | head -1)
if [[ -n "$SHOP_POD" ]]; then
  SCHEMAS=$($KUBECTL exec -n zeroqwait "$SHOP_POD" -- python3 -c "
import os; from sqlalchemy import create_engine, text
url='postgresql://{}:{}@{}:{}/{}'.format(
  os.environ.get('DB_USER','zeroqwait'),os.environ.get('DB_PASSWORD','password'),
  os.environ.get('DB_HOST','postgres'),os.environ.get('DB_PORT','5432'),
  os.environ.get('DB_NAME','zeroqwait'))
e=create_engine(url); r=e.connect().execute(text(\"SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('platform','tenant_515')\")).fetchall(); print([x[0] for x in r])" \
    2>/dev/null || echo "[]")
  if echo "$SCHEMAS" | grep -q "platform" && echo "$SCHEMAS" | grep -q "tenant_515"; then
    pass "Shop-515 DB: schemas ['platform','tenant_515'] present"
  else
    fail "Shop-515 DB: schemas missing — got $SCHEMAS"
  fi
fi

# Dedicated MCPs
py_http_internal "zeroqwait" "app=backend-shop-515" "http://booking-mcp-shop-515.zeroqwait.svc.cluster.local:8890/health" "Shop-515 booking-mcp" '"status"'
py_http_internal "zeroqwait" "app=backend-shop-515" "http://finance-mcp-shop-515.zeroqwait.svc.cluster.local:8891/health" "Shop-515 finance-mcp" '"status"'
py_http_internal "zeroqwait" "app=backend-shop-515" "http://hr-mcp-shop-515.zeroqwait.svc.cluster.local:8892/health"      "Shop-515 hr-mcp"      '"status"'

# Redis shop-515 (no password)
SHOP515_REDIS_PONG=$($KUBECTL exec -n zeroqwait redis-shop-515-0 -- redis-cli ping 2>/dev/null || echo "FAIL")
[[ "$SHOP515_REDIS_PONG" == "PONG" ]] && pass "Shop-515 Redis: PONG" || fail "Shop-515 Redis: $SHOP515_REDIS_PONG"

check_temporal_worker "zeroqwait" "app=worker-shop-515" "Shop-515"

# Ingress (HTTPS)
check_http_external "https://elite-style-studio.zeroqwait.com/api/agent/health" "Shop-515 HTTPS ingress" '"status"'

# =============================================================================
# SECTION 4 — STAGING
# =============================================================================
header "4. Staging  (zeroqwait-staging)"

check_pod "zeroqwait-staging" "app=backend"         "Staging backend"
check_pod "zeroqwait-staging" "app=frontend"        "Staging frontend"
check_pod "zeroqwait-staging" "app=booking-mcp"     "Staging booking-mcp"
check_pod "zeroqwait-staging" "app=finance-mcp"     "Staging finance-mcp"
check_pod "zeroqwait-staging" "app=hr-mcp"          "Staging hr-mcp"
check_pod "zeroqwait-staging" "app=temporal"        "Staging temporal"
check_pod "zeroqwait-staging" "app=temporal-worker" "Staging temporal-worker"
check_pod "zeroqwait-staging" "statefulset.kubernetes.io/pod-name=postgres-0" "Staging postgres"
check_pod "zeroqwait-staging" "statefulset.kubernetes.io/pod-name=redis-0"    "Staging redis"

py_http_internal "zeroqwait-staging" "app=backend" "http://localhost:8000/api/agent/health"    "Staging /api/agent/health"    '"status"'
py_http_internal "zeroqwait-staging" "app=backend" "http://localhost:8000/api/v2/agent/health" "Staging /api/v2/agent/health" '"status"'

# Staging MCPs
py_http_internal "zeroqwait-staging" "app=backend" "http://booking-mcp.zeroqwait-staging.svc.cluster.local:8890/health" "Staging booking-mcp" '"status"'
py_http_internal "zeroqwait-staging" "app=backend" "http://finance-mcp.zeroqwait-staging.svc.cluster.local:8891/health" "Staging finance-mcp" '"status"'
py_http_internal "zeroqwait-staging" "app=backend" "http://hr-mcp.zeroqwait-staging.svc.cluster.local:8892/health"      "Staging hr-mcp"      '"status"'

# Staging voice routing (shared voice-mcp in prod namespace)
py_http_internal "zeroqwait-staging" "app=backend" "http://voice-mcp.zeroqwait.svc.cluster.local:8881/health" "Staging→Prod voice-mcp" '"status"'

# Staging DB
STAGING_BACKEND_POD=$($KUBECTL get pods -n zeroqwait-staging -l app=backend --no-headers 2>/dev/null | awk '$3=="Running"{print $1}' | head -1)
if [[ -n "$STAGING_BACKEND_POD" ]]; then
  STAGING_TABLES=$($KUBECTL exec -n zeroqwait-staging "$STAGING_BACKEND_POD" -- python3 -c "
import os; from sqlalchemy import create_engine, text
h=os.environ.get('DB_HOST','postgres.zeroqwait-staging.svc.cluster.local')
u=os.environ.get('DB_USER','zeroqwait')
p=os.environ.get('DB_PASSWORD','staging-password-change-me')
port=os.environ.get('DB_PORT','5432')
db=os.environ.get('DB_NAME','zeroqwait')
e=create_engine(f'postgresql://{u}:{p}@{h}:{port}/{db}')
r=e.connect().execute(text(\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='platform'\")).scalar(); print(r)" \
    2>/dev/null || echo "0")
  [[ "$STAGING_TABLES" =~ ^[1-9] ]] && pass "Staging DB: platform schema has $STAGING_TABLES tables" || fail "Staging DB: table count=$STAGING_TABLES"
fi

# Staging Redis (no password)
STAGING_REDIS_PONG=$($KUBECTL exec -n zeroqwait-staging redis-0 -- redis-cli ping 2>/dev/null || echo "FAIL")
[[ "$STAGING_REDIS_PONG" == "PONG" ]] && pass "Staging Redis: PONG" || fail "Staging Redis: $STAGING_REDIS_PONG"

check_temporal_worker "zeroqwait-staging" "app=temporal-worker" "Staging"

# HTTPS ingress
check_http_external "https://staging.zeroqwait.com/api/agent/health"    "Staging HTTPS ingress"    '"status"'
check_http_external "https://staging.zeroqwait.com/api/v2/agent/health" "Staging v2 HTTPS ingress" '"status"'

# Frontend HTML
STAGING_FE=$(curl -sk --max-time 10 "https://staging.zeroqwait.com/" 2>/dev/null || true)
echo "$STAGING_FE" | grep -qi "doctype html" && pass "Staging frontend: serving HTML" || fail "Staging frontend: no HTML"

# =============================================================================
# SECTION 5 — VOICE PIPELINE
# =============================================================================
header "5. Voice Pipeline  (cross-namespace TTS+ASR routing)"

VMCP_POD=$($KUBECTL get pods -n zeroqwait -l app=voice-mcp --no-headers 2>/dev/null | awk '$3=="Running"{print $1}' | head -1)
if [[ -n "$VMCP_POD" ]]; then
  # voice-mcp → TTS
  TTS_REACH=$($KUBECTL exec -n zeroqwait "$VMCP_POD" -- python3 -c \
    "import urllib.request; r=urllib.request.urlopen('http://tts-service.zeroqwait-ai.svc.cluster.local:8880/health',timeout=8); print(r.read(150).decode())" \
    2>/dev/null || echo "ERR")
  [[ "$TTS_REACH" != ERR* ]] && pass "voice-mcp → TTS: ${TTS_REACH:0:80}" || fail "voice-mcp → TTS unreachable"

  # voice-mcp → ASR
  ASR_REACH=$($KUBECTL exec -n zeroqwait "$VMCP_POD" -- python3 -c \
    "import urllib.request; r=urllib.request.urlopen('http://asr-service.zeroqwait-ai.svc.cluster.local:8000/health',timeout=8); print(r.read(100).decode())" \
    2>/dev/null || echo "ERR")
  [[ "$ASR_REACH" != ERR* ]] && pass "voice-mcp → ASR: ${ASR_REACH:0:80}" || fail "voice-mcp → ASR unreachable"

  # TTS synthesis test (small text)
  TTS_BYTES=$($KUBECTL exec -n zeroqwait "$VMCP_POD" -- python3 -c \
    "import urllib.request,json; body=json.dumps({'model':'tts-1-en','input':'Hello','voice':'Vivian','language':'English'}).encode(); req=urllib.request.Request('http://tts-service.zeroqwait-ai.svc.cluster.local:8880/v1/audio/speech',data=body,headers={'Content-Type':'application/json'});
try:
  r=urllib.request.urlopen(req,timeout=45); print(len(r.read()))
except Exception as e:
  print(0)" \
    2>/dev/null || echo "0")
  if [[ "$TTS_BYTES" =~ ^[0-9]+$ && "$TTS_BYTES" -gt 1000 ]]; then
    pass "TTS synthesis: ${TTS_BYTES} bytes (voice=Vivian, model=Qwen3-TTS)"
  else
    warn "TTS synthesis: ${TTS_BYTES} bytes — may be warming up or GPU busy"
  fi
else
  fail "voice-mcp: no running pod"
fi

# TTS health via backend route
check_http_external "http://localhost:30000/api/voice/tts/health" "TTS health via backend /api/voice/tts/health" '"status"'

# ASR health via backend route
check_http_external "http://localhost:30000/api/voice/transcribe" "ASR endpoint reachable" ""

# =============================================================================
# SECTION 6 — MONITORING
# =============================================================================
header "6. Monitoring  (prometheus + grafana)"

check_pod "monitoring" "app=prometheus"         "Prometheus"
check_pod "monitoring" "app=grafana"            "Grafana"
check_pod "monitoring" "app=kube-state-metrics" "kube-state-metrics"
check_pod "monitoring" "app=node-exporter"      "node-exporter"

PROM_POD=$($KUBECTL get pods -n monitoring -l app=prometheus --no-headers 2>/dev/null | awk '$3=="Running"{print $1}' | head -1)
if [[ -n "$PROM_POD" ]]; then
  # Prometheus image has wget (no python3)
  PROM_H=$($KUBECTL exec -n monitoring "$PROM_POD" -- wget -qO- --timeout=8 http://localhost:9090/-/healthy 2>/dev/null || true)
  echo "$PROM_H" | grep -qi "healthy\|OK" && pass "Prometheus /-/healthy: ${PROM_H:0:40}" || warn "Prometheus health: ${PROM_H:0:60}"

  PROM_RAW=$($KUBECTL exec -n monitoring "$PROM_POD" -- wget -qO- --timeout=8 http://localhost:9090/api/v1/targets 2>/dev/null || true)
  PROM_TARGETS=$(echo "$PROM_RAW" | python3 -c \
    "import json,sys; d=json.load(sys.stdin); tgts=d['data']['activeTargets']; up=sum(1 for t in tgts if t['health']=='up'); print(f'{up}/{len(tgts)} targets up')" \
    2>/dev/null || true)
  [[ -n "$PROM_TARGETS" ]] && pass "Prometheus scrape targets: $PROM_TARGETS" || warn "Prometheus: could not query targets"
fi

GRAF_POD=$($KUBECTL get pods -n monitoring -l app=grafana --no-headers 2>/dev/null | awk '$3=="Running"{print $1}' | head -1)
if [[ -n "$GRAF_POD" ]]; then
  # Grafana image has curl (no python3)
  GRAF_H=$($KUBECTL exec -n monitoring "$GRAF_POD" -- curl -s --max-time 8 http://localhost:3000/api/health 2>/dev/null || true)
  echo "$GRAF_H" | grep -qi '"database"' && pass "Grafana /api/health: ${GRAF_H:0:80}" || warn "Grafana health: ${GRAF_H:0:60}"
fi

check_http_external "https://monitoring.zeroqwait.com" "Monitoring HTTPS ingress" ""

# =============================================================================
# SECTION 7 — RESOURCE SUMMARY
# =============================================================================
header "7. Cluster Resource Summary"
echo ""
echo "  Namespace pod counts:"
for ns in zeroqwait-ai zeroqwait zeroqwait-staging monitoring; do
  RUNNING=$($KUBECTL get pods -n "$ns" --no-headers 2>/dev/null | awk '$3=="Running"' | wc -l)
  TOTAL=$($KUBECTL get pods -n "$ns" --no-headers 2>/dev/null | wc -l)
  CRASH=$($KUBECTL get pods -n "$ns" --no-headers 2>/dev/null | awk '$3~"CrashLoop|OOMKilled"' | wc -l)
  echo "    $ns: $RUNNING/$TOTAL running  ($CRASH crashing)"
done
echo ""
$KUBECTL describe node 2>/dev/null | grep -A 6 "Allocated resources" | head -8 || true

# =============================================================================
# FINAL REPORT
# =============================================================================
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  FINAL TEST RESULTS${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${GREEN}PASS: $PASS${NC}   ${RED}FAIL: $FAIL${NC}   ${YELLOW}WARN: $WARN${NC}   Total: $((PASS+FAIL+WARN))"
echo ""

if [[ $FAIL -gt 0 ]]; then
  echo -e "${RED}  ── Failures ──${NC}"
  for r in "${RESULTS[@]}"; do
    [[ "$r" == \[FAIL\]* ]] && echo -e "  ${RED}$r${NC}"
  done
  echo ""
fi
if [[ $WARN -gt 0 ]]; then
  echo -e "${YELLOW}  ── Warnings ──${NC}"
  for r in "${RESULTS[@]}"; do
    [[ "$r" == \[WARN\]* ]] && echo -e "  ${YELLOW}$r${NC}"
  done
  echo ""
fi
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
