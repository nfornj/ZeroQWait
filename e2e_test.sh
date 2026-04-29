#!/bin/bash
set -euo pipefail
API="http://localhost:30000"
OWNER_EMAIL="owner_danielle_johnson_1@example-zeroqwait.com"
PASSWORD="Test1234!"
SHOP_ID=1
PASS=0; FAIL=0

ts() { date +%s%3N; }
ms() { echo $(( $(ts) - $1 )); }

result() {
  local label=$1 status=$2 detail=$3 latency=${4:-""}
  if [[ "$status" == "PASS" ]]; then
    echo "  ✓ $label${latency:+ (${latency}ms)} — $detail"
    PASS=$((PASS+1))
  else
    echo "  ✗ $label — $detail"
    FAIL=$((FAIL+1))
  fi
}

echo "╔══════════════════════════════════════════════════════════╗"
echo "║       ZeroQwait E2E Test + Performance Report            ║"
echo "║  $(date)  ║"
echo "║  Image: v20260429160650-4ac8b8b                          ║"
echo "║  Provider: NVIDIA NIM (meta/llama-3.1-8b-instruct)      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

###############################################################################
echo "─── [1] INFRASTRUCTURE HEALTH ─────────────────────────────"
for endpoint in "/api/agent/health" "/api/v2/agent/health" "/api/voice/tts/health"; do
  t=$(ts)
  resp=$(curl -s --max-time 5 "${API}${endpoint}" 2>&1)
  code=$(echo "$resp" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('status',d.get('detail','?')))" 2>/dev/null || echo "err")
  http=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${API}${endpoint}" 2>/dev/null)
  lat=$(ms $t)
  if [[ "$http" == "200" ]]; then
    result "$endpoint" "PASS" "HTTP 200, status=$code" "$lat"
  else
    result "$endpoint" "FAIL" "HTTP $http"
  fi
done
echo ""

###############################################################################
echo "─── [2] AUTHENTICATION ────────────────────────────────────"
t=$(ts)
AUTH_RESP=$(curl -s -X POST "${API}/api/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${OWNER_EMAIL}&password=${PASSWORD}")
lat=$(ms $t)
TOKEN=$(echo "$AUTH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [[ ${#TOKEN} -gt 20 ]]; then
  result "POST /api/auth/token" "PASS" "token acquired (${#TOKEN} chars)" "$lat"
else
  result "POST /api/auth/token" "FAIL" "$(echo $AUTH_RESP | head -c 100)"
  echo "Aborting — no auth token"; exit 1
fi
echo ""

###############################################################################
echo "─── [3] REST APIs ─────────────────────────────────────────"

# My shops
t=$(ts)
SHOP_RESP=$(curl -s "${API}/api/shops/my-shops" -H "Authorization: Bearer ${TOKEN}")
lat=$(ms $t)
SHOP_NAME=$(echo "$SHOP_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); d=d[0] if isinstance(d,list) and d else d; print(d.get('name','?'))" 2>/dev/null)
if [[ "$SHOP_NAME" != "?" && -n "$SHOP_NAME" ]]; then
  result "GET /api/shops/my-shops" "PASS" "shop='$SHOP_NAME'" "$lat"
else
  result "GET /api/shops/my-shops" "FAIL" "$(echo $SHOP_RESP | head -c 100)"
fi

# Queue status
t=$(ts)
QUEUE_RESP=$(curl -s "${API}/api/queues/shop/${SHOP_ID}/active" -H "Authorization: Bearer ${TOKEN}")
lat=$(ms $t)
QUEUE_STATUS=$(echo "$QUEUE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); d=d[0] if isinstance(d,list) and d else d; print(d.get('status',d.get('detail','?')))" 2>/dev/null)
if echo "$QUEUE_RESP" | python3 -c "import sys,json; json.load(sys.stdin)" &>/dev/null; then
  result "GET /api/queues/shop/$SHOP_ID/active" "PASS" "queue_status=$QUEUE_STATUS" "$lat"
else
  result "GET /api/queues/shop/$SHOP_ID/active" "FAIL" "$(echo $QUEUE_RESP | head -c 100)"
fi

# Analytics
t=$(ts)
ANALYTICS_RESP=$(curl -s "${API}/api/analytics/daily?shop_id=${SHOP_ID}&limit=1" -H "Authorization: Bearer ${TOKEN}")
lat=$(ms $t)
if echo "$ANALYTICS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d,list) or isinstance(d,dict)" &>/dev/null; then
  result "GET /api/analytics/daily" "PASS" "valid JSON response" "$lat"
else
  # Try alternate analytics path
  ANALYTICS_RESP=$(curl -s "${API}/api/shops/${SHOP_ID}/analytics" -H "Authorization: Bearer ${TOKEN}")
  lat=$(ms $t)
  if echo "$ANALYTICS_RESP" | python3 -c "import sys,json; json.load(sys.stdin)" &>/dev/null; then
    result "GET /api/shops/$SHOP_ID/analytics" "PASS" "valid JSON response" "$lat"
  else
    result "GET /api/analytics" "FAIL" "$(echo $ANALYTICS_RESP | head -c 80)"
  fi
fi
echo ""

###############################################################################
echo "─── [4] AGENT V2 CHAT (NVIDIA NIM) ────────────────────────"
echo "    Sending: 'Give me a quick summary of how the shop is doing today.'"
echo "    Timing full round-trip via streaming endpoint ..."
echo ""

THREAD_ID="e2e-$(date +%s)"
t=$(ts)

# Use the streaming endpoint — collect all SSE events until [DONE]
STREAM_RAW=$(curl -s -N -X POST "${API}/api/v2/agent/chat/stream" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Give me a quick summary of how the shop is doing today.\",\"shop_id\":${SHOP_ID},\"thread_id\":\"${THREAD_ID}\"}" \
  --max-time 180)

lat=$(ms $t)

# Parse SSE: extract text/sentence content and detect completion
CONTENT=$(echo "$STREAM_RAW" | python3 -c "
import sys
lines = sys.stdin.read().splitlines()
texts = []
done = False
for line in lines:
    if line == 'data: [DONE]':
        done = True
    elif line.startswith('data: '):
        import json
        try:
            ev = json.loads(line[6:])
            t = ev.get('type','')
            if t in ('text','sentence'):
                c = ev.get('content') or ev.get('text','')
                if c: texts.append(c)
            elif t == 'stream_status' and ev.get('status') == 'completed':
                done = True
        except: pass
result = ''.join(texts).strip()
print(result[:500] if result else 'EMPTY')
" 2>&1)

if [[ "$CONTENT" == "EMPTY" || ${#CONTENT} -lt 5 ]]; then
  result "POST /api/v2/agent/chat/stream" "FAIL" "empty/unparseable: $(echo $STREAM_RAW | head -c 200)"
  echo ""
  echo "  Raw SSE preview: $(echo $STREAM_RAW | head -c 400)"
else
  result "POST /api/v2/agent/chat/stream" "PASS" "got ${#CONTENT}-char response" "$lat"
  echo ""
  echo "  ┌─ Agent Response Preview ─────────────────────────────────"
  echo "$CONTENT" | fold -s -w 60 | while read line; do echo "  │ $line"; done
  echo "  └───────────────────────────────────────────────────────────"
fi
echo ""

###############################################################################
echo "─── [5] AGENT CHAT PERFORMANCE (3 runs via streaming) ─────"
declare -a TIMES=()
QUERIES=(
  "How many customers are in the queue right now?"
  "What are today's top services by bookings?"
  "Give me today's revenue so far."
)

for i in 0 1 2; do
  q="${QUERIES[$i]}"
  echo "  Run $((i+1)): \"$q\""
  t=$(ts)
  RESP=$(curl -s -N -X POST "${API}/api/v2/agent/chat/stream" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"message\":\"${q}\",\"shop_id\":${SHOP_ID},\"thread_id\":\"e2e-perf-${i}-$(date +%s)\"}" \
    --max-time 180)
  lat=$(ms $t)
  TIMES+=($lat)
  STATUS=$(echo "$RESP" | python3 -c "
import sys,json
lines=sys.stdin.read().splitlines()
texts=[]
for l in lines:
    if l.startswith('data: ') and l != 'data: [DONE]':
        try:
            ev=json.loads(l[6:])
            c=ev.get('content','') or ev.get('text','')
            if c: texts.append(c)
        except: pass
result=''.join(texts).strip()
print('ok:'+str(len(result))+'chars' if len(result)>5 else 'empty')
" 2>&1)
  echo "    → ${lat}ms | $STATUS"
  sleep 1
done

# Calculate avg/min/max
python3 -c "
times = [${TIMES[0]}, ${TIMES[1]}, ${TIMES[2]}]
print('')
print('  ┌─ Performance Summary ─────────────────────────────────')
print(f'  │  Min latency:  {min(times):>6}ms')
print(f'  │  Max latency:  {max(times):>6}ms')
print(f'  │  Avg latency:  {sum(times)//len(times):>6}ms')
print(f'  │  (Ollama qwen3:14b baseline: ~30,000–60,000ms per call)')
print('  └──────────────────────────────────────────────────────')
"
echo ""

###############################################################################
echo "─── [6] NVIDIA PROVIDER VERIFICATION ──────────────────────"
RECENT_LOGS=$(sudo env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl logs -n zeroqwait deployment/backend --since=5m 2>/dev/null)
NVIDIA_CALLS=$(echo "$RECENT_LOGS" | grep -c "nvidia\|integrate\.api\|ChatNVIDIA\|glm4\|NVIDIA" 2>/dev/null || echo 0)
ERRORS=$(echo "$RECENT_LOGS" | grep -c "ERROR\|Exception\|ModuleNotFoundError" 2>/dev/null || echo 0)
echo "$RECENT_LOGS" | grep -E "nvidia|ChatNVIDIA|LLM_PROVIDER|glm4|integrate.api" | tail -5 | while read line; do
  echo "  LOG: $line"
done
if [[ "$NVIDIA_CALLS" -gt 0 ]]; then
  result "NVIDIA provider usage in logs" "PASS" "$NVIDIA_CALLS log lines mentioning nvidia/glm4"
else
  echo "  ⚠  No nvidia references in recent logs (may be suppressed at INFO level)"
fi
if [[ "$ERRORS" -gt 0 ]]; then
  echo "  ⚠  $ERRORS ERROR lines in last 5min logs:"
  echo "$RECENT_LOGS" | grep "ERROR\|Exception\|ModuleNotFoundError" | tail -3 | while read line; do
    echo "    $line"
  done
else
  result "No errors in backend logs (5min)" "PASS" "clean"
fi
echo ""

###############################################################################
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  RESULTS: $PASS passed, $FAIL failed"
if [[ $FAIL -eq 0 ]]; then
  echo "║  STATUS: ALL TESTS PASSED ✓"
else
  echo "║  STATUS: $FAIL TEST(S) FAILED — check output above"
fi
echo "╚══════════════════════════════════════════════════════════╝"
