"""
test_raw_read_queries.py
========================
End-to-end tests for the raw_read endpoint on postgres-mcp.

Runs 5 complex SELECT queries (JOINs, CTEs, window functions, aggregations)
and 6 security rejection tests.

Run from inside the backend container so postgres-mcp is reachable by service name:
    docker cp test_raw_read_queries.py zeroqwait-backend-1:/tmp/
    docker exec zeroqwait-backend-1 python3 /tmp/test_raw_read_queries.py

Or run via the helper at the bottom if the postgres-mcp port is exposed.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# ── Config ─────────────────────────────────────────────────────────────────────
POSTGRES_MCP = "http://postgres-mcp:8894"   # inside docker network
ENDPOINT     = f"{POSTGRES_MCP}/query/raw_read"
SHOP_ID      = 502   # Classic Cuts — has inventory (18 items) + 19 k queue_items
SHOP_ID_PEER = 85    # Different shop — used in cross-tenant isolation checks

# ── Helpers ────────────────────────────────────────────────────────────────────
def call(shop_id: int, sql: str, params: dict | None = None, limit: int = 100):
    payload = {"shop_id": shop_id, "sql": sql, "params": params or {}, "limit": limit}
    data    = json.dumps(payload).encode()
    req     = urllib.request.Request(
        ENDPOINT, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


PASS = 0
FAIL = 0

def check(name: str, expr: bool, detail: str = ""):
    global PASS, FAIL
    if expr:
        PASS += 1
        print(f"  ✅  {name}")
    else:
        FAIL += 1
        print(f"  ❌  FAIL — {name}")
        if detail:
            print(f"       {detail}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION A — COMPLEX QUERY TESTS
# ══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 72)
print("SECTION A: Complex SELECT Queries")
print("=" * 72)

# ── A1: Multi-table JOIN — service popularity + avg wait time ─────────────────
print("\nA1: Multi-table JOIN — service name, bookings count, avg wait minutes")
sql_a1 = """
SELECT
    ss.name                                                     AS service_name,
    COUNT(qi.id)                                                AS bookings,
    ROUND(AVG(EXTRACT(EPOCH FROM (
        qi.completed_at - qi.service_started_at
    )) / 60.0)::numeric, 1)                                     AS avg_service_minutes
FROM queue_items qi
JOIN queues       q  ON qi.queue_id  = q.id
JOIN shop_services ss ON qi.service_id = ss.id
WHERE q.shop_id = :_shop_id
  AND qi.status = 'COMPLETED'
  AND qi.completed_at IS NOT NULL
  AND qi.service_started_at IS NOT NULL
GROUP BY ss.name
ORDER BY bookings DESC
LIMIT 10
"""
t0 = time.time()
status, body = call(SHOP_ID, sql_a1, limit=10)
ms = int((time.time() - t0) * 1000)

check(f"HTTP 200 [{ms}ms]", status == 200, f"status={status}, body={body}")
if status == 200:
    rows = body.get("rows", [])
    check("At least 3 services returned", len(rows) >= 3, f"got {len(rows)}")
    check("Rows have service_name, bookings, avg_service_minutes",
          rows and all(k in rows[0] for k in ("service_name", "bookings", "avg_service_minutes")),
          str(rows[0] if rows else "empty"))
    check("Top service has > 0 bookings", rows and rows[0]["bookings"] > 0, str(rows[:2]))
    print(f"       Top services: {[(r['service_name'], r['bookings']) for r in rows[:5]]}")

# ── A2: Aggregation + day-of-week breakdown ────────────────────────────────────
print("\nA2: Revenue by service × day-of-week (GROUP BY + EXTRACT)")
sql_a2 = """
SELECT
    ss.name                                    AS service_name,
    EXTRACT(DOW FROM qi.completed_at)::int     AS day_of_week,
    COUNT(*)                                   AS total_bookings,
    ROUND(SUM(qi.service_cost)::numeric, 2)    AS total_revenue
FROM queue_items qi
JOIN queues        q  ON qi.queue_id   = q.id
JOIN shop_services ss ON qi.service_id = ss.id
WHERE q.shop_id = :_shop_id
  AND qi.status = 'COMPLETED'
  AND qi.service_cost IS NOT NULL
GROUP BY ss.name, EXTRACT(DOW FROM qi.completed_at)
ORDER BY total_revenue DESC
LIMIT 20
"""
t0 = time.time()
status, body = call(SHOP_ID, sql_a2, limit=20)
ms = int((time.time() - t0) * 1000)

check(f"HTTP 200 [{ms}ms]", status == 200, str(body))
if status == 200:
    rows = body.get("rows", [])
    check("At least 5 rows returned", len(rows) >= 5, f"got {len(rows)}")
    check("Rows have required columns",
          rows and all(k in rows[0] for k in ("service_name", "day_of_week", "total_bookings", "total_revenue")),
          str(rows[0] if rows else "empty"))
    if rows:
        top = rows[0]
        check("day_of_week is 0-6", 0 <= int(top["day_of_week"]) <= 6, str(top["day_of_week"]))
        print(f"       Top combo: {top['service_name']} on dow={top['day_of_week']} "
              f"({top['total_bookings']} bookings, ${top['total_revenue']})")

# ── A3: Customer frequency + total spend (GROUP BY, ORDER BY, HAVING) ─────────
print("\nA3: Top customers by visits + spend (HAVING COUNT > 1)")
sql_a3 = """
SELECT
    qi.customer_name,
    COUNT(*)                                       AS total_visits,
    ROUND(SUM(COALESCE(qi.service_cost, 0))::numeric, 2) AS total_spent,
    MIN(qi.checked_in_at)::date                    AS first_visit,
    MAX(qi.checked_in_at)::date                    AS last_visit
FROM queue_items qi
JOIN queues q ON qi.queue_id = q.id
WHERE q.shop_id = :_shop_id
  AND qi.status = 'COMPLETED'
GROUP BY qi.customer_name
HAVING COUNT(*) > 1
ORDER BY total_visits DESC, total_spent DESC
LIMIT 10
"""
t0 = time.time()
status, body = call(SHOP_ID, sql_a3, limit=10)
ms = int((time.time() - t0) * 1000)

check(f"HTTP 200 [{ms}ms]", status == 200, str(body))
if status == 200:
    rows = body.get("rows", [])
    check("At least 3 repeat customers", len(rows) >= 3, f"got {len(rows)}")
    if rows:
        top = rows[0]
        check("Top customer has > 1 visit", int(top["total_visits"]) > 1, str(top))
        check("Rows have all columns",
              all(k in top for k in ("customer_name", "total_visits", "total_spent", "first_visit", "last_visit")),
              str(top))
        print(f"       Top: {top['customer_name']} — {top['total_visits']} visits, ${top['total_spent']}")

# ── A4: CTE + window function — monthly revenue with running total ─────────────
print("\nA4: CTE + window function — monthly revenue with running total")
sql_a4 = """
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', qi.completed_at)                         AS month,
        ROUND(SUM(COALESCE(qi.service_cost, 0))::numeric, 2)         AS monthly_revenue,
        COUNT(*)                                                     AS completed_visits
    FROM queue_items qi
    JOIN queues q ON qi.queue_id = q.id
    WHERE q.shop_id = :_shop_id
      AND qi.status = 'COMPLETED'
    GROUP BY DATE_TRUNC('month', qi.completed_at)
)
SELECT
    month,
    monthly_revenue,
    completed_visits,
    ROUND(SUM(monthly_revenue) OVER (ORDER BY month)::numeric, 2)    AS running_total_revenue
FROM monthly
ORDER BY month
"""
t0 = time.time()
status, body = call(SHOP_ID, sql_a4, limit=100)
ms = int((time.time() - t0) * 1000)

check(f"HTTP 200 [{ms}ms]", status == 200, str(body))
if status == 200:
    rows = body.get("rows", [])
    check("At least 1 month of data", len(rows) >= 1, f"got {len(rows)}")
    if rows:
        check("Rows have running_total_revenue column",
              all("running_total_revenue" in r for r in rows),
              str(rows[0]))
        # running total must be non-decreasing
        totals = [float(r["running_total_revenue"]) for r in rows]
        check("Running total is non-decreasing",
              all(totals[i] <= totals[i+1] for i in range(len(totals)-1)),
              str(totals))
        print(f"       {len(rows)} months. Last running total: ${totals[-1]:,.2f}")

# ── A5: Inventory profit margin ranking ───────────────────────────────────────
print("\nA5: Inventory profit margin ranking (retail_price_cents - cost_per_unit*100)")
sql_a5 = """
SELECT
    name,
    category,
    ROUND((retail_price_cents / 100.0 - cost_per_unit)::numeric, 2)   AS margin_per_unit,
    ROUND((retail_price_cents / 100.0)::numeric, 2)                    AS retail_price,
    ROUND(cost_per_unit::numeric, 2)                                   AS cost,
    ROUND(
        ((retail_price_cents / 100.0 - cost_per_unit) / NULLIF(retail_price_cents / 100.0, 0) * 100)::numeric,
        1
    )                                                                  AS margin_pct
FROM inventory_items
WHERE shop_id = :_shop_id
  AND retail_price_cents IS NOT NULL
  AND cost_per_unit IS NOT NULL
  AND retail_price_cents > 0
ORDER BY margin_per_unit DESC
"""
t0 = time.time()
status, body = call(SHOP_ID, sql_a5, limit=20)
ms = int((time.time() - t0) * 1000)

check(f"HTTP 200 [{ms}ms]", status == 200, str(body))
if status == 200:
    rows = body.get("rows", [])
    check("At least 5 items with retail price", len(rows) >= 5, f"got {len(rows)}")
    if rows:
        top = rows[0]
        check("Top item is Beard Brush (Boar Bristle)",
              "beard brush" in top["name"].lower(),
              f"got: {top['name']}")
        check("Margin $16.00",
              abs(float(top["margin_per_unit"]) - 16.0) < 0.01,
              f"got: {top['margin_per_unit']}")
        check("Margin % positive", float(top["margin_pct"]) > 0, str(top["margin_pct"]))
        print(f"       Ranking: {[(r['name'], r['margin_per_unit']) for r in rows[:5]]}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION B — SECURITY REJECTION TESTS (all should return HTTP 400)
# ══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 72)
print("SECTION B: Security Rejection Tests (all expect HTTP 400)")
print("=" * 72)

def security_check(label: str, shop_id: int, sql: str, params: dict | None = None):
    status, body = call(shop_id, sql, params)
    detail = body.get("detail", "") if isinstance(body, dict) else str(body)
    check(f"{label} → 400", status == 400, f"got {status}: {detail}")
    if status == 400:
        print(f"       detail: {detail}")

print()
security_check(
    "B1: INSERT keyword blocked",
    SHOP_ID,
    "INSERT INTO inventory_items (shop_id) VALUES (:_shop_id)",
)

security_check(
    "B2: DELETE keyword blocked",
    SHOP_ID,
    "DELETE FROM inventory_items WHERE shop_id = :_shop_id",
)

security_check(
    "B3: UPDATE keyword blocked",
    SHOP_ID,
    "UPDATE inventory_items SET current_stock = 0 WHERE shop_id = :_shop_id",
)

security_check(
    "B4: -- comment sequence blocked",
    SHOP_ID,
    "SELECT id FROM inventory_items WHERE shop_id = :_shop_id -- injected",
)

security_check(
    "B5: No :_shop_id placeholder → blocked (tenant scope required)",
    SHOP_ID,
    "SELECT id FROM inventory_items WHERE shop_id = 502",
)

security_check(
    "B6: SELECT without FROM a valid table but with semicolon → blocked",
    SHOP_ID,
    "SELECT 1; DROP TABLE inventory_items",
)


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
total = PASS + FAIL
print()
print("=" * 72)
print(f"TOTAL: {total} tests | {PASS} PASS | {FAIL} FAIL")
if FAIL == 0:
    print("✅ All tests passed.")
else:
    print(f"❌ {FAIL} test(s) failed.")
print("=" * 72)
print()

sys.exit(0 if FAIL == 0 else 1)
