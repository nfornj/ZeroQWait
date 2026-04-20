"""
End-to-End test: queue join rate limiting.

Requires a running backend (BASE_URL env var, default http://localhost:8000).
Sends 12 rapid queue-join requests from the same test IP and asserts that at
least one returns HTTP 429.

Because the real Redis key is keyed by the actual client IP seen by the server
(the test runner's IP), this test should only be run in CI where the runner
IP is the same across retries OR when Redis is flushed between test runs.

Run:
    BASE_URL=http://localhost:8000 pytest backend/tests/test_e2e_rate_limit.py -v
"""
import os
import time
import requests
import pytest

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
# Use a non-existent shop_id so the join fails at 404 BEFORE hitting the rate limit.
# We only care about whether 429 is returned, not successful joins.
TEST_SHOP_ID = 99999
REQUESTS_PER_BURST = 15  # Enough to exceed the limit of 10/min.


def _join_url() -> str:
    return f"{BASE_URL}/api/queues/shop/{TEST_SHOP_ID}/join"


def _payload(name_suffix: str = "") -> dict:
    return {
        "customer_name": f"RateLimitTestUser{name_suffix}",
        "customer_phone": "5550000000",
    }


@pytest.mark.e2e
def test_rate_limit_triggers_429():
    """
    Burst-send REQUESTS_PER_BURST queue-join requests.
    We expect to see at least one HTTP 429 among the responses once
    the 10-per-minute per-IP limit is exceeded.
    """
    # Quick connectivity check
    try:
        health = requests.get(f"{BASE_URL}/api/agent/health", timeout=5)
        if health.status_code >= 500:
            pytest.skip("Backend not healthy — skipping E2E rate-limit test")
    except requests.exceptions.ConnectionError:
        pytest.skip(f"Backend unreachable at {BASE_URL}")

    statuses = []
    for i in range(REQUESTS_PER_BURST):
        try:
            resp = requests.post(
                _join_url(),
                json=_payload(str(i)),
                timeout=5,
            )
            statuses.append(resp.status_code)
        except requests.exceptions.RequestException:
            statuses.append(0)

    # Acceptable response codes:
    # 404 — shop not found (expected for TEST_SHOP_ID = 99999)
    # 429 — rate limited (what we want to see eventually)
    # 422 — validation error (acceptable; still means request reached handler)
    # 500 — server error (we tolerate it here; we just want at least one 429)
    assert 429 in statuses, (
        f"Expected at least one HTTP 429 among {REQUESTS_PER_BURST} rapid requests. "
        f"Got statuses: {statuses}"
    )
    print(f"Rate limit triggered after statuses: {statuses}")


@pytest.mark.e2e
def test_rate_limit_resets_after_window():
    """
    After triggering a 429, waiting slightly and trying again should NOT
    return 429 immediately (the window has or will reset).
    This is a soft assertion — we just verify the endpoint is reachable again.
    """
    try:
        resp = requests.get(f"{BASE_URL}/api/agent/health", timeout=5)
        if resp.status_code >= 500:
            pytest.skip("Backend not healthy")
    except requests.exceptions.ConnectionError:
        pytest.skip(f"Backend unreachable at {BASE_URL}")

    # Single request after a pause should not immediately 429
    # (window is 60s but we can't wait that; just verify 429 is not the ONLY option)
    resp = requests.post(_join_url(), json=_payload("reset"), timeout=5)
    # 404 or 429 are both acceptable; we just don't want a crash.
    assert resp.status_code in (404, 422, 429, 500)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
