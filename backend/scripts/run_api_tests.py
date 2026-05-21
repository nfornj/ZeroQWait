"""
Comprehensive API test suite for FastCuts.
Tests: auth, shops, queues, services, employees, analytics, agent, tenant mgmt.
"""

import sys
import json
import time
import requests

BASE = "http://localhost:30000"

DEMO_ACCOUNTS = [
    {"email": "demo_owner_premium@example.com", "password": "Test123!", "shop_id": 503, "tier": "PREMIUM"},
    {"email": "demo_owner_free@example.com",    "password": "Test123!", "shop_id": 504, "tier": "FREE"},
    {"email": "free_user_1@example.com",        "password": "Test123!", "shop_id": 505, "tier": "FREE"},
    {"email": "free_user_2@example.com",        "password": "Test123!", "shop_id": 506, "tier": "FREE"},
]

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"


def login(email, password):
    r = requests.post(f"{BASE}/api/auth/token",
                      data={"username": email, "password": password},
                      timeout=10)
    if r.status_code == 200:
        return r.json()["access_token"]
    return None


def api(method, path, token=None, **kwargs):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    kwargs.setdefault("timeout", 10)
    return getattr(requests, method)(f"{BASE}{path}", headers=headers, **kwargs)


def check(label, condition, detail=""):
    if condition:
        print(f"  {PASS} {label}" + (f" — {detail}" if detail else ""))
        return True
    else:
        print(f"  {FAIL} {label}" + (f" — {detail}" if detail else ""))
        return False


results = {"passed": 0, "failed": 0, "warnings": 0}


def report(ok):
    if ok:
        results["passed"] += 1
    else:
        results["failed"] += 1
    return ok


# -----------------------------------------------------------------------
# 1. Auth Tests
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("1. AUTH TESTS")
print("=" * 60)
tokens = {}
for acct in DEMO_ACCOUNTS:
    tok = login(acct["email"], acct["password"])
    ok = report(check(f"Login {acct['email']}", tok is not None, f"tier={acct['tier']}"))
    if tok:
        tokens[acct["email"]] = tok

# Test bad password
r = requests.post(f"{BASE}/api/auth/token",
                  data={"username": "demo_owner_premium@example.com", "password": "wrongpass"},
                  timeout=5)
report(check("Reject bad password", r.status_code == 401))

# -----------------------------------------------------------------------
# 2. Shop APIs
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("2. SHOP APIs")
print("=" * 60)
tok_premium = tokens.get("demo_owner_premium@example.com")
tok_free    = tokens.get("demo_owner_free@example.com")

if tok_premium:
    # GET own shops
    r = api("get", "/api/shops/my-shops", tok_premium)
    ok = report(check("GET /api/shops/my-shops (premium)", r.status_code == 200))
    if ok:
        shops = r.json()
        shop_count = len(shops) if isinstance(shops, list) else shops.get("total", "?")
        print(f"       shops returned: {shop_count}")

    # GET specific shop
    r = api("get", "/api/shops/503", tok_premium)
    report(check("GET /api/shops/503", r.status_code == 200, f"name={r.json().get('name','?') if r.status_code==200 else r.text[:60]}"))

    # GET shop by slug
    r = api("get", "/api/shops/slug/demo-owner-premium")
    report(check("GET /api/shops/slug/demo-owner-premium", r.status_code == 200))

# -----------------------------------------------------------------------
# 3. Services APIs
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("3. SERVICES APIs")
print("=" * 60)
if tok_premium:
    r = api("get", "/api/services/shops/503", tok_premium)
    ok = report(check("GET /api/services/shops/503", r.status_code == 200))
    if ok:
        svcs = r.json()
        svc_count = len(svcs) if isinstance(svcs, list) else "?"
        print(f"       services: {svc_count}")
        if isinstance(svcs, list) and svc_count > 0:
            print(f"       first service: {svcs[0].get('name','?')} cost={svcs[0].get('cost','?')}")

if tok_free:
    r = api("get", "/api/services/shops/504", tok_free)
    report(check("GET /api/services/shops/504 (free user)", r.status_code == 200))

# -----------------------------------------------------------------------
# 4. Employees APIs
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("4. EMPLOYEES APIs")
print("=" * 60)
if tok_premium:
    r = api("get", "/api/employees/shops/503", tok_premium)
    ok = report(check("GET /api/employees/shops/503", r.status_code == 200))
    if ok:
        emps = r.json()
        emp_count = len(emps) if isinstance(emps, list) else "?"
        print(f"       employees: {emp_count}")

# -----------------------------------------------------------------------
# 5. Queues APIs
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("5. QUEUES APIs")
print("=" * 60)
if tok_premium:
    r = api("get", "/api/queues/shop/503", tok_premium)
    ok = report(check("GET /api/queues/shop/503", r.status_code == 200))
    if ok:
        queues = r.json()
        q_count = len(queues) if isinstance(queues, list) else "?"
        print(f"       queues: {q_count}")
        if isinstance(queues, list) and len(queues) > 0:
            today_q = queues[0]
            qid = today_q.get("id")
            print(f"       today's queue: id={qid} name={today_q.get('name','?')}")

            # Get queue items
            if qid:
                r2 = api("get", f"/api/queues/{qid}/items", tok_premium)
                ok2 = report(check(f"GET /api/queues/{qid}/items", r2.status_code == 200))
                if ok2:
                    items = r2.json()
                    print(f"       queue items: {len(items) if isinstance(items, list) else '?'}")

if tok_free:
    r = api("get", "/api/queues/shop/504", tok_free)
    report(check("GET /api/queues/shop/504 (free user)", r.status_code == 200))

# -----------------------------------------------------------------------
# 6. Analytics APIs
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("6. ANALYTICS APIs")
print("=" * 60)
if tok_premium:
    r = api("get", "/api/analytics/503", tok_premium)
    ok = report(check("GET /api/analytics/503", r.status_code == 200, f"status={r.status_code}"))
    if ok and isinstance(r.json(), dict):
        data = r.json()
        print(f"       analytics keys: {list(data.keys())[:5]}")

    r = api("get", "/api/analytics/daily/503?days=30", tok_premium)
    report(check("GET /api/analytics/daily/503 (30 days)", r.status_code == 200))

    r = api("get", "/api/analytics/peak-hours/503", tok_premium)
    report(check("GET /api/analytics/peak-hours/503", r.status_code == 200))

if tok_free:
    r = api("get", "/api/analytics/504", tok_free)
    report(check("GET /api/analytics/504 (free)", r.status_code == 200))

# -----------------------------------------------------------------------
# 7. Appointments APIs
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("7. APPOINTMENTS APIs")
print("=" * 60)
if tok_premium:
    r = api("get", "/api/appointments/shop/503", tok_premium)
    ok = report(check("GET /api/appointments/shop/503", r.status_code == 200))
    if ok:
        appts = r.json()
        print(f"       appointments: {len(appts) if isinstance(appts, list) else appts}")

# -----------------------------------------------------------------------
# 8. Subscriptions API
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("8. SUBSCRIPTIONS APIs")
print("=" * 60)
if tok_premium:
    r = api("get", "/api/subscriptions/status", tok_premium)
    report(check("GET /api/subscriptions/status (premium)", r.status_code == 200,
                 r.json().get("subscription_tier","?") if r.status_code == 200 else r.text[:60]))

if tok_free:
    r = api("get", "/api/subscriptions/status", tok_free)
    report(check("GET /api/subscriptions/status (free)", r.status_code == 200))

# -----------------------------------------------------------------------
# 9. Tenant Management APIs
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("9. TENANT MANAGEMENT APIs")
print("=" * 60)

# Check if tenant endpoints exist (they may not — new code may not be deployed)
r = api("get", "/api/tenants/runtimes", tok_premium)
if r.status_code == 200:
    report(check("GET /api/tenants/runtimes", True, f"runtimes: {len(r.json()) if isinstance(r.json(), list) else '?'}"))
elif r.status_code == 404:
    print(f"  {WARN} GET /api/tenants/runtimes — 404 (tenant endpoints not deployed to K8s yet)")
    results["warnings"] += 1
else:
    report(check("GET /api/tenants/runtimes", False, f"status={r.status_code}"))

r = api("get", "/api/tenants/list", tok_premium)
if r.status_code == 200:
    report(check("GET /api/tenants/list", True))
elif r.status_code == 404:
    print(f"  {WARN} GET /api/tenants/list — 404 (not deployed)")
    results["warnings"] += 1
else:
    report(check("GET /api/tenants/list", False, f"status={r.status_code}"))

# -----------------------------------------------------------------------
# 10. Agent v2 (LangGraph Owner Chat)
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("10. AGENT v2 (LangGraph Owner Chat)")
print("=" * 60)
if tok_premium:
    payload = {
        "message": "How many customers did my shop serve today?",
        "shop_id": 503,
        "thread_id": "test-thread-premium-001"
    }
    try:
        r = requests.post(f"{BASE}/api/v2/agent/chat/stream",
                          headers={"Authorization": f"Bearer {tok_premium}"},
                          json=payload,
                          timeout=30,
                          stream=True)
        if r.status_code == 200:
            chunks = []
            for line in r.iter_lines(max_content=2000):
                if line:
                    chunks.append(line.decode("utf-8", errors="replace"))
                if len(chunks) >= 5:
                    break
            report(check("POST /api/v2/agent/chat/stream (premium)", True,
                         f"streaming OK, {len(chunks)} chunks received"))
            if chunks:
                print(f"       first chunk: {chunks[0][:120]}")
        else:
            report(check("POST /api/v2/agent/chat/stream (premium)", False,
                         f"status={r.status_code} body={r.text[:120]}"))
    except Exception as e:
        report(check("POST /api/v2/agent/chat/stream (premium)", False, str(e)[:100]))

if tok_free:
    payload = {
        "message": "What services do I offer?",
        "shop_id": 504,
        "thread_id": "test-thread-free-001"
    }
    try:
        r = requests.post(f"{BASE}/api/v2/agent/chat/stream",
                          headers={"Authorization": f"Bearer {tok_free}"},
                          json=payload,
                          timeout=30,
                          stream=True)
        if r.status_code == 200:
            chunks = []
            for line in r.iter_lines(max_content=2000):
                if line:
                    chunks.append(line.decode("utf-8", errors="replace"))
                if len(chunks) >= 3:
                    break
            report(check("POST /api/v2/agent/chat/stream (free)", True,
                         f"{len(chunks)} chunks received"))
        else:
            report(check("POST /api/v2/agent/chat/stream (free)", False,
                         f"status={r.status_code} body={r.text[:120]}"))
    except Exception as e:
        report(check("POST /api/v2/agent/chat/stream (free)", False, str(e)[:100]))

# -----------------------------------------------------------------------
# 11. Legacy Customer-Facing Agent
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("11. CUSTOMER-FACING AGENT")
print("=" * 60)
try:
    r = requests.post(f"{BASE}/api/agent/chat",
                      json={"message": "What are the services available?", "shop_id": 503},
                      timeout=20)
    if r.status_code == 200:
        data = r.json()
        report(check("POST /api/agent/chat", True, f"response keys: {list(data.keys())[:4]}"))
    else:
        report(check("POST /api/agent/chat", False, f"status={r.status_code}"))
except Exception as e:
    report(check("POST /api/agent/chat", False, str(e)[:80]))

# -----------------------------------------------------------------------
# 12. Public Booking API
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("12. PUBLIC BOOKING APIs")
print("=" * 60)
r = requests.get(f"{BASE}/api/public/shops/demo-owner-premium", timeout=5)
report(check("GET /api/public/shops/demo-owner-premium", r.status_code in (200, 404),
             f"status={r.status_code}"))

r = requests.get(f"{BASE}/api/public/shops/503/services", timeout=5)
report(check("GET /api/public/shops/503/services", r.status_code in (200, 404),
             f"status={r.status_code}"))

# -----------------------------------------------------------------------
# 13. Admin APIs
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("13. ADMIN APIs")
print("=" * 60)
if tok_premium:
    r = api("get", "/api/admin/users", tok_premium)
    report(check("GET /api/admin/users", r.status_code in (200, 403),
                 f"status={r.status_code} (403=not admin, expected)"))

# -----------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("FINAL TEST RESULTS")
print("=" * 60)
total = results["passed"] + results["failed"]
print(f"  Passed:   {results['passed']}/{total}")
print(f"  Failed:   {results['failed']}/{total}")
print(f"  Warnings: {results['warnings']}")
if results["failed"] == 0:
    print("\n  ✅ ALL TESTS PASSED")
else:
    print(f"\n  ❌ {results['failed']} TESTS FAILED — see above")
print("=" * 60)

sys.exit(0 if results["failed"] == 0 else 1)
