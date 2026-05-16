#!/usr/bin/env bash
# run_all_tests.sh — Phase 6 test suite runner
#
# Usage:
#   ./run_all_tests.sh [TEST_BASE_URL] [TTS_SERVICE_URL]
#
# Defaults:
#   TEST_BASE_URL    = http://localhost:30000
#   TTS_SERVICE_URL  = http://localhost:30880
set -euo pipefail

export TEST_BASE_URL="${1:-http://localhost:30000}"
export TTS_SERVICE_URL="${2:-http://localhost:30880}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo " ZeroQwait Phase 6 Test Suite"
echo " Backend: $TEST_BASE_URL"
echo " TTS:     $TTS_SERVICE_URL"
echo "========================================"

cd "$BACKEND_DIR"

# Check backend is reachable
if ! curl -sf "$TEST_BASE_URL/api/agent/health" > /dev/null; then
  echo "ERROR: Backend not reachable at $TEST_BASE_URL"
  exit 1
fi
echo "✓ Backend reachable"

PASS=0
FAIL=0
SKIP=0

run_test() {
  local name=$1
  local file=$2
  echo ""
  echo "--- $name ---"
  if python -m pytest "$file" -v --tb=short --no-header 2>&1; then
    echo "PASS: $name"
    ((PASS++)) || true
  else
    echo "FAIL: $name"
    ((FAIL++)) || true
  fi
}

run_test "Schema Isolation"        "tests/test_schema_isolation.py"
run_test "Registration Flow"       "tests/test_registration_flow.py"
run_test "Premium Provisioning"    "tests/test_premium_provisioning.py"

# GPU TTS tests require TTS service to be running
if curl -sf "$TTS_SERVICE_URL/health" > /dev/null 2>&1; then
  run_test "GPU TTS"               "tests/test_gpu_tts.py"
else
  echo ""
  echo "SKIP: GPU TTS (TTS service not reachable at $TTS_SERVICE_URL)"
  ((SKIP++)) || true
fi

echo ""
echo "========================================"
echo " Results: $PASS passed / $FAIL failed / $SKIP skipped"
echo "========================================"

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
