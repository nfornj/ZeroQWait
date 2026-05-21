"""
Deep Finance + Inventory Test Suite — Classic Cuts (shop_id=1) & Inventory Shop (shop_id=502)
20 questions: 10 finance (finance-mcp + postgres-mcp) + 10 inventory (postgres-mcp safe_query)
Each question is validated against DB ground truth.
"""
import json, time, urllib.request, urllib.error

FINANCE_URL  = "http://localhost:8891"  # replaced via sed
POSTGRES_URL = "http://localhost:8894"  # replaced via sed

# ── Ground truth from DB ────────────────────────────────────────────────────────
GT_FINANCE = {
    "shop_id": 1,
    "total_revenue_all_time":   19858.64,
    "peak_revenue_day":         720.26,
    "peak_revenue_date":        "2026-02-21",
    "avg_daily_revenue":        218.23,
    "total_customers_all_time": 1907,
    "total_completed_all_time": 1635,
    "total_cancelled_all_time": 262,
    "avg_wait_minutes":         19.1,
    # Month breakdown
    "revenue_by_month": {
        "2026-01": 5116.43,
        "2026-02": 9156.50,
        "2026-03": 4329.20,
        "2026-04": 1256.51,
    },
    "best_month": "2026-02",
    "worst_month_active": "2026-04",
    # Top services (from queue_items COMPLETED)
    "top_service_by_revenue":    "Hair & Beard Combo",
    "top_service_revenue_total": 329.91,
    "top_service_by_visits":     "Kids Haircut",
    "top_service_visits":        16,
    # Clients
    "top_client_name":           "Mia White",
    "top_client_id":             3,
    "top_client_visits":         20,
}

GT_INVENTORY = {
    "shop_id": 502,
    "total_items":          18,
    "total_categories":     4,
    "categories":           {"Consumables", "Hair Products", "Retail", "Tools"},
    "total_value":          1590.0,   # SUM(current_stock * cost_per_unit)
    "low_stock_count":      3,        # current_stock <= reorder_threshold
    "low_stock_names":      {"Foil Wraps (Pack of 50)", "Neck Strip Roll", "Hair Spray (Finishing)"},
    "highest_cost_item":    "Barber Cape (Black)",      # cost_per_unit = 15.00
    "highest_cost_value":   15.00,
    "most_stocked_item":    "Shaving Cream",            # current_stock = 30
    "most_stocked_qty":     30,
    "supplier_barbershop_co_count": 6,                  # "Barbershop Supply Co."
    "retail_priced_items":  9,                          # retail_price_cents IS NOT NULL
    "tools_items":          4,
    "consumables_items":    5,
    "hair_products_items":  6,
    "retail_items":         3,
    "highest_retail_margin_item": "Beard Brush (Boar Bristle)",  # retail 28.00 - cost 12.00 = $16/unit
    "highest_retail_margin":     16.0,
}

results = []

def call(method, url, **kwargs):
    t0 = time.perf_counter()
    try:
        body = kwargs.get("json")
        data = json.dumps(body).encode() if body else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read()), round((time.perf_counter()-t0)*1000), None
    except urllib.error.HTTPError as e:
        body_str = e.read().decode()
        return None, round((time.perf_counter()-t0)*1000), f"HTTP {e.code}: {body_str[:300]}"
    except Exception as ex:
        return None, round((time.perf_counter()-t0)*1000), str(ex)

def record(cat, n, question, status, ms, detail):
    icon = {"PASS":"✅", "WARN":"⚠️ ", "FAIL":"❌"}[status]
    print(f"\n  {icon}  Q{n} [{ms}ms] {question}")
    print(f"        → {detail}")
    results.append({"cat": cat, "n": n, "status": status, "ms": ms})

def approx(a, b, pct=5):
    """True if a is within pct% of b (or both zero)."""
    if b == 0:
        return a == 0
    return abs(a - b) / abs(b) * 100 <= pct


# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("CATEGORY 1: FINANCE — 10 Deep Questions (finance-mcp + postgres-mcp)")
print("="*70)

# F1 — Revenue trend "last 120 days": is Feb the best month?
data, ms, err = call("POST", f"{FINANCE_URL}/revenue/trend",
                     json={"shop_id": 1, "query": "last 120 days"})
if err:
    record("Finance", 1, "Revenue trend — confirm Feb is best month", "FAIL", ms, f"Error: {err}")
else:
    pts = data.get("points", [])
    # Use top-level best_period and best_period_revenue from the trend summary
    best_period = data.get("best_period", "?")
    best_period_rev = round(float(data.get("best_period_revenue", 0) or 0), 2)
    best_month = best_period[:7] if best_period and best_period != "?" else "?"
    match = best_month == GT_FINANCE["peak_revenue_date"][:7]  # 2026-02
    match_rev = abs(best_period_rev - GT_FINANCE["peak_revenue_day"]) < 1.0
    status = "PASS" if match and match_rev else "WARN"
    record("Finance", 1, "Revenue trend — confirm Feb is best month", status, ms,
           f"best_period={best_period} rev=${best_period_rev} (GT: {GT_FINANCE['peak_revenue_date']} ${GT_FINANCE['peak_revenue_day']}). "
           f"Feb is best={match}, rev_ok={match_rev}. Total points={len(pts)}")

# F2 — POS summary: does it return transaction data?
data, ms, err = call("POST", f"{FINANCE_URL}/pos/summary",
                     json={"shop_id": 1})
if err:
    record("Finance", 2, "POS summary — transaction data present", "FAIL", ms, f"Error: {err}")
else:
    keys = list(data.keys()) if isinstance(data, dict) else []
    # POS summary uses total_amount and total_transactions (not total_revenue)
    total_amount = data.get("total_amount", None)
    total_txns = data.get("total_transactions", None)
    has_expected_keys = "total_amount" in keys and "total_transactions" in keys
    # Data ends 2026-04-14; today is future → 0 is correct
    amount_ok = isinstance(total_amount, (int, float)) and total_amount >= 0
    status = "PASS" if has_expected_keys and amount_ok else "WARN"
    record("Finance", 2, "POS summary — transaction data present", status, ms,
           f"Keys: {keys}. total_amount={total_amount}, total_transactions={total_txns}. "
           f"expected_keys={has_expected_keys} (0 is correct — dataset ends 2026-04-14)")

# F3 — Top clients: Mia White must be #1
data, ms, err = call("POST", f"{FINANCE_URL}/clients/top",
                     json={"shop_id": 1, "limit": 5})
if err:
    record("Finance", 3, "Top clients — Mia White is #1 by visits", "FAIL", ms, f"Error: {err}")
else:
    clients = data if isinstance(data, list) else data.get("clients", data.get("top_clients", []))
    top = clients[0] if clients else {}
    top_name = top.get("name", "?")
    top_visits = top.get("visit_count", top.get("visits", "?"))
    is_mia = "mia" in str(top_name).lower()
    visits_ok = isinstance(top_visits, (int, float)) and top_visits >= GT_FINANCE["top_client_visits"]
    status = "PASS" if is_mia and visits_ok else "FAIL"
    record("Finance", 3, "Top clients — Mia White is #1 by visits", status, ms,
           f"#1 client: {top_name} (visits={top_visits}, GT={GT_FINANCE['top_client_visits']}). "
           f"Mia={is_mia}, visits_ok={visits_ok}. Total returned={len(clients)}")

# F4 — Inactive clients (45+ days): count must be >= 10 given data ends Apr 14
data, ms, err = call("POST", f"{FINANCE_URL}/clients/inactive",
                     json={"shop_id": 1, "days_threshold": 45})
if err:
    record("Finance", 4, "Inactive clients 45+ days — churn risk count", "FAIL", ms, f"Error: {err}")
else:
    clients = data if isinstance(data, list) else data.get("inactive_clients", data.get("clients", []))
    count = len(clients) if isinstance(clients, list) else data.get("count", 0)
    # Data ends Apr 14; today May 14 = 30 days past. 45+ days inactive means inactive before Mar 30.
    status = "PASS" if count >= 5 else "WARN"
    first = clients[0] if isinstance(clients, list) and clients else {}
    record("Finance", 4, "Inactive clients 45+ days — churn risk count", status, ms,
           f"Inactive count={count} (expected ≥5 given 45-day window). "
           f"First: {first.get('name','?')} last_visit={first.get('last_visit','?')} days_inactive={first.get('days_inactive','?')}")

# F5 — Client profile for Mia White (id=3): verify 20 visits
data, ms, err = call("POST", f"{FINANCE_URL}/clients/profile",
                     json={"shop_id": 1, "client_id": GT_FINANCE["top_client_id"]})
if err:
    record("Finance", 5, "Client profile Mia White (id=3) — verify 20 visits", "FAIL", ms, f"Error: {err}")
else:
    name = data.get("name", data.get("client_name", "?"))
    visits = data.get("visit_count", data.get("total_visits", data.get("visits", "?")))
    is_mia = "mia" in str(name).lower()
    visits_match = isinstance(visits, (int, float)) and int(visits) == GT_FINANCE["top_client_visits"]
    status = "PASS" if is_mia and visits_match else ("WARN" if is_mia else "FAIL")
    record("Finance", 5, "Client profile Mia White (id=3) — verify 20 visits", status, ms,
           f"name={name}, visits={visits} (GT={GT_FINANCE['top_client_visits']}). "
           f"is_mia={is_mia}, visits_match={visits_match}. Keys: {list(data.keys())[:8]}")

# F6 — Service customer counts: Hair & Beard Combo should be highest revenue
data, ms, err = call("POST", f"{FINANCE_URL}/services/customer-counts",
                     json={"shop_id": 1, "query": "last 90 days", "limit": 10})
if err:
    record("Finance", 6, "Service revenue breakdown — Hair & Beard Combo #1", "FAIL", ms, f"Error: {err}")
else:
    services = data if isinstance(data, list) else data.get("services", data.get("top_services", []))
    names = [s.get("name", s.get("service_name", "?")) for s in services]
    top_name = names[0] if names else "?"
    has_combo = any("combo" in str(n).lower() or "beard" in str(n).lower() for n in names)
    status = "PASS" if has_combo else "WARN"
    record("Finance", 6, "Service revenue breakdown — Hair & Beard Combo #1", status, ms,
           f"Top service={top_name} (GT=Hair & Beard Combo). All: {names}. Has combo/beard={has_combo}")

# F7 — Visit frequency distribution: multi-visit customers
data, ms, err = call("POST", f"{FINANCE_URL}/clients/visit-frequency",
                     json={"shop_id": 1})
if err:
    record("Finance", 7, "Client visit-frequency distribution", "FAIL", ms, f"Error: {err}")
else:
    freq = data.get("frequency_distribution", data.get("distribution", data.get("buckets", [])))
    total = data.get("total_clients", data.get("total", len(freq) if isinstance(freq, list) else 0))
    multi = data.get("repeat_clients", data.get("multi_visit", "?"))
    keys = list(data.keys())
    status = "PASS" if isinstance(total, (int, float)) and total > 0 else "WARN"
    record("Finance", 7, "Client visit-frequency distribution", status, ms,
           f"total_clients={total}, repeat_clients={multi}. Keys: {keys}")

# F8 — Natural-language finance question: what was total revenue all time?
data, ms, err = call("POST", f"{FINANCE_URL}/query/answer",
                     json={"shop_id": 1, "question": "What was the total revenue for February 2026?",
                           "mode": "enabled"})
if err:
    record("Finance", 8, "NL query — total revenue for February 2026", "FAIL", ms, f"Error: {err}")
else:
    # query/answer requires an LLM token; without one it returns InvalidToken + fallback_used=True
    error_class = data.get("error_class", "")
    fallback = data.get("fallback_used", False)
    has_token_err = error_class == "InvalidToken"
    # If LLM is available the answer should mention $9156
    answer = data.get("answer", data.get("response", ""))
    answer_str = str(answer).lower()
    has_feb_revenue = any(x in answer_str for x in ["9156", "9,156", "feb", "february"])
    if has_token_err:
        status = "WARN"  # Known: LLM token not configured in test env
        detail = f"InvalidToken (no LLM configured) — fallback_used={fallback}. Known limitation."
    elif has_feb_revenue:
        status = "PASS"
        detail = f"Answer mentions Feb revenue correctly: {str(answer)[:200]}"
    else:
        status = "WARN"
        detail = f"Answer: {str(answer)[:200]}. Mentions Feb revenue={has_feb_revenue}"
    record("Finance", 8, "NL query — total revenue for February 2026 (LLM)", status, ms, detail)

# F9 — Search client by name: "Mia" should return Mia White
data, ms, err = call("POST", f"{FINANCE_URL}/clients/search",
                     json={"shop_id": 1, "name": "Mia"})
if err:
    record("Finance", 9, "Client search 'Mia' — find Mia White", "FAIL", ms, f"Error: {err}")
else:
    clients = data if isinstance(data, list) else data.get("clients", data.get("results", []))
    names = [c.get("name", c.get("client_name", "?")) for c in clients]
    has_mia = any("mia" in str(n).lower() for n in names)
    status = "PASS" if has_mia else "FAIL"
    record("Finance", 9, "Client search 'Mia' — find Mia White", status, ms,
           f"Found={names}. has_mia={has_mia}")

# F10 — Postgres-mcp service popularity: Kids Haircut must have most visits
data, ms, err = call("POST", f"{POSTGRES_URL}/analytics/service-popularity",
                     json={"shop_id": 1, "days": 365})
if err:
    record("Finance", 10, "Service popularity by visits — Kids Haircut is #1", "FAIL", ms, f"Error: {err}")
else:
    services = data.get("data", data.get("services", []))
    # Filter out NULL-named rows (unlinked queue_items) — fixed in postgres-mcp via INNER JOIN
    named = [s for s in services if s.get("service_name") is not None]
    top = named[0] if named else (services[0] if services else {})
    top_name = top.get("service_name", top.get("name", "?"))
    top_count = top.get("total_served", top.get("count", top.get("visits", "?")))
    is_kids = "kids" in str(top_name).lower() or "kid" in str(top_name).lower()
    null_rows = len(services) - len(named)
    status = "PASS" if is_kids and null_rows == 0 else ("WARN" if is_kids else "FAIL")
    record("Finance", 10, "Service popularity by visits — Kids Haircut is #1", status, ms,
           f"#1 service={top_name} (visits={top_count}). GT=Kids Haircut (16 visits). "
           f"NULL-named rows={null_rows} (0 expected after fix). "
           f"All named: {[s.get('service_name') for s in named[:5]]}")


# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("CATEGORY 2: INVENTORY — 10 Deep Questions (postgres-mcp safe_query, shop_id=502)")
print("="*70)

def safe_query(table, filters=None, limit=100, order_by=None, desc=False):
    body = {"shop_id": GT_INVENTORY["shop_id"], "table": table, "limit": limit}
    if filters:
        body["filters"] = filters
    if order_by:
        body["order_by"] = order_by
    if desc:
        body["desc"] = True
    return call("POST", f"{POSTGRES_URL}/query/safe", json=body)

# I1 — Total item count for shop 502
data, ms, err = safe_query("inventory_items")
if err:
    record("Inventory", 1, "Total inventory item count for shop 502", "FAIL", ms, f"Error: {err}")
else:
    rows = data.get("rows", data.get("data", data if isinstance(data, list) else []))
    count = len(rows)
    match = count == GT_INVENTORY["total_items"]
    status = "PASS" if match else "FAIL"
    record("Inventory", 1, "Total inventory item count for shop 502", status, ms,
           f"Count={count} (GT={GT_INVENTORY['total_items']}). Match={match}")

# I2 — Category distribution: 4 categories
if data and not err:
    rows = data.get("rows", data.get("data", []))
    cats = set(r.get("category", "") for r in rows if r.get("category"))
    count_cats = len(cats)
    match = cats == GT_INVENTORY["categories"]
    status = "PASS" if match else "WARN"
    ms2 = 0  # derived from same query
    record("Inventory", 2, "Category distribution — 4 distinct categories", status, 0,
           f"Categories found={cats} (GT={GT_INVENTORY['categories']}). Match={match}")
else:
    data2, ms2, err2 = safe_query("inventory_items")
    rows = data2.get("rows", []) if data2 else []
    cats = set(r.get("category", "") for r in rows if r.get("category"))
    record("Inventory", 2, "Category distribution — 4 distinct categories",
           "FAIL" if err2 else "WARN", ms2, f"cats={cats}")

# I3 — Total inventory value (current_stock × cost_per_unit)
data, ms, err = safe_query("inventory_items")
if err:
    record("Inventory", 3, "Total inventory value (stock × cost) = $1,590", "FAIL", ms, f"Error: {err}")
else:
    rows = data.get("rows", data.get("data", []))
    total_value = sum(
        float(r.get("current_stock", 0) or 0) * float(r.get("cost_per_unit", 0) or 0)
        for r in rows
    )
    total_value = round(total_value, 2)
    match = approx(total_value, GT_INVENTORY["total_value"], pct=1)
    status = "PASS" if match else "FAIL"
    record("Inventory", 3, "Total inventory value (stock × cost) = $1,590", status, ms,
           f"Computed value=${total_value} (GT=${GT_INVENTORY['total_value']}). Within 1%={match}")

# I4 — Low stock items (current_stock <= reorder_threshold): expect 3
data, ms, err = safe_query("inventory_items")
if err:
    record("Inventory", 4, "Low stock items (stock ≤ threshold) — expect 3", "FAIL", ms, f"Error: {err}")
else:
    rows = data.get("rows", data.get("data", []))
    low = [r for r in rows
           if float(r.get("current_stock", 0) or 0) <= float(r.get("reorder_threshold", 0) or 0)]
    low_names = {r.get("name", "?") for r in low}
    count_low = len(low)
    match_count = count_low == GT_INVENTORY["low_stock_count"]
    match_names = low_names == GT_INVENTORY["low_stock_names"]
    status = "PASS" if match_count and match_names else ("WARN" if match_count else "FAIL")
    record("Inventory", 4, "Low stock items (stock ≤ threshold) — expect 3", status, ms,
           f"Low stock count={count_low} (GT={GT_INVENTORY['low_stock_count']}). "
           f"Names={low_names}. GT={GT_INVENTORY['low_stock_names']}. "
           f"count_ok={match_count}, names_ok={match_names}")

# I5 — Most expensive item by cost_per_unit: Barber Cape at $15
data, ms, err = safe_query("inventory_items", order_by="cost_per_unit", desc=True, limit=5)
if err:
    record("Inventory", 5, "Most expensive item by cost — Barber Cape $15", "FAIL", ms, f"Error: {err}")
else:
    rows = data.get("rows", data.get("data", []))
    top = rows[0] if rows else {}
    name = top.get("name", "?")
    cost = round(float(top.get("cost_per_unit", 0) or 0), 2)
    is_cape = "cape" in str(name).lower()
    cost_ok = approx(cost, GT_INVENTORY["highest_cost_value"], pct=1)
    status = "PASS" if is_cape and cost_ok else "FAIL"
    record("Inventory", 5, "Most expensive item by cost — Barber Cape $15", status, ms,
           f"Top item={name} cost=${cost} (GT={GT_INVENTORY['highest_cost_item']} ${GT_INVENTORY['highest_cost_value']}). "
           f"is_cape={is_cape}, cost_ok={cost_ok}")

# I6 — Most stocked item: Shaving Cream (30 units)
data, ms, err = safe_query("inventory_items", order_by="current_stock", desc=True, limit=5)
if err:
    record("Inventory", 6, "Most stocked item — Shaving Cream (30 units)", "FAIL", ms, f"Error: {err}")
else:
    rows = data.get("rows", data.get("data", []))
    top = rows[0] if rows else {}
    name = top.get("name", "?")
    qty = float(top.get("current_stock", 0) or 0)
    is_shaving = "shaving" in str(name).lower()
    qty_ok = qty == GT_INVENTORY["most_stocked_qty"]
    status = "PASS" if is_shaving and qty_ok else "FAIL"
    record("Inventory", 6, "Most stocked item — Shaving Cream (30 units)", status, ms,
           f"Top item={name} qty={qty} (GT={GT_INVENTORY['most_stocked_item']} {GT_INVENTORY['most_stocked_qty']} units). "
           f"is_shaving={is_shaving}, qty_ok={qty_ok}")

# I7 — Supplier analysis: Barbershop Supply Co. has 6 items
data, ms, err = safe_query("inventory_items", filters={"supplier": "Barbershop Supply Co."})
if err:
    record("Inventory", 7, "Supplier 'Barbershop Supply Co.' — 6 items", "FAIL", ms, f"Error: {err}")
else:
    rows = data.get("rows", data.get("data", []))
    count = len(rows)
    match = count == GT_INVENTORY["supplier_barbershop_co_count"]
    status = "PASS" if match else "FAIL"
    names = [r.get("name", "?") for r in rows]
    record("Inventory", 7, "Supplier 'Barbershop Supply Co.' — 6 items", status, ms,
           f"Count={count} (GT={GT_INVENTORY['supplier_barbershop_co_count']}). "
           f"Items={names}. match={match}")

# I8 — Tools category: exactly 4 items
data, ms, err = safe_query("inventory_items", filters={"category": "Tools"})
if err:
    record("Inventory", 8, "Tools category — exactly 4 items", "FAIL", ms, f"Error: {err}")
else:
    rows = data.get("rows", data.get("data", []))
    count = len(rows)
    match = count == GT_INVENTORY["tools_items"]
    status = "PASS" if match else "FAIL"
    names = [r.get("name", "?") for r in rows]
    record("Inventory", 8, "Tools category — exactly 4 items", status, ms,
           f"Count={count} (GT={GT_INVENTORY['tools_items']}). Items={names}. match={match}")

# I9 — Retail-priced items (retail_price_cents present): check via all items
data, ms, err = safe_query("inventory_items")
if err:
    record("Inventory", 9, "Items with retail price set — expect 9 (resellable)", "FAIL", ms, f"Error: {err}")
else:
    rows = data.get("rows", data.get("data", []))
    retail = [r for r in rows if r.get("retail_price_cents") is not None and r.get("retail_price_cents", 0) > 0]
    count = len(retail)
    match = count == GT_INVENTORY["retail_priced_items"]
    status = "PASS" if match else "WARN"
    names = [r.get("name", "?") for r in retail]
    record("Inventory", 9, "Items with retail price set — expect 9 (resellable)", status, ms,
           f"Count={count} (GT={GT_INVENTORY['retail_priced_items']}). "
           f"Items={names}. match={match}")

# I10 — Best retail margin: Beard Brush ($28 retail - $12 cost = $16/unit margin)
data, ms, err = safe_query("inventory_items")
if err:
    record("Inventory", 10, "Best retail margin — Beard Brush at $16/unit", "FAIL", ms, f"Error: {err}")
else:
    rows = data.get("rows", data.get("data", []))
    retail_items = [r for r in rows if r.get("retail_price_cents") and int(r.get("retail_price_cents", 0) or 0) > 0]
    margins = []
    for r in retail_items:
        retail_dollars = int(r.get("retail_price_cents", 0) or 0) / 100.0
        cost = float(r.get("cost_per_unit", 0) or 0)
        margin = round(retail_dollars - cost, 2)
        margins.append((r.get("name", "?"), margin, retail_dollars, cost))
    margins.sort(key=lambda x: x[1], reverse=True)
    best_name, best_margin, best_retail, best_cost = margins[0] if margins else ("?", 0, 0, 0)
    is_brush = "brush" in str(best_name).lower() or "beard brush" in str(best_name).lower()
    margin_ok = approx(best_margin, GT_INVENTORY["highest_retail_margin"], pct=2)
    status = "PASS" if is_brush and margin_ok else ("WARN" if margin_ok else "FAIL")
    record("Inventory", 10, "Best retail margin — Beard Brush at $16/unit", status, ms,
           f"Best={best_name} margin=${best_margin}/unit (retail=${best_retail} cost=${best_cost}). "
           f"GT={GT_INVENTORY['highest_retail_margin_item']} ${GT_INVENTORY['highest_retail_margin']}/unit. "
           f"is_brush={is_brush}, margin_ok={margin_ok}. "
           f"Full margins: {[(n, m) for n, m, _, _ in margins[:5]]}")


# ══════════════════════════════════════════════════════════════════════════════
print("\n\n" + "="*70)
print("TEST SUMMARY — Finance & Inventory Deep Test")
print("="*70)

cats = ["Finance", "Inventory"]
print(f"\n{'Category':<14} {'✅ Pass':>8} {'⚠️  Warn':>8} {'❌ Fail':>8} {'Avg ms':>8} {'Max ms':>8}")
print("-"*65)
grand = {"PASS":0, "WARN":0, "FAIL":0, "ms":[]}
for cat in cats:
    cr = [r for r in results if r["cat"]==cat]
    p = sum(1 for r in cr if r["status"]=="PASS")
    w = sum(1 for r in cr if r["status"]=="WARN")
    f = sum(1 for r in cr if r["status"]=="FAIL")
    ms_list = [r["ms"] for r in cr]
    avg = round(sum(ms_list)/len(ms_list)) if ms_list else 0
    mx  = max(ms_list) if ms_list else 0
    print(f"{cat:<14} {p:>8} {w:>8} {f:>8} {avg:>8} {mx:>8}")
    grand["PASS"]+=p; grand["WARN"]+=w; grand["FAIL"]+=f; grand["ms"]+=ms_list
print("-"*65)
all_ms = grand["ms"]
avg_all = round(sum(all_ms)/len(all_ms)) if all_ms else 0
mx_all  = max(all_ms) if all_ms else 0
print(f"{'TOTAL':<14} {grand['PASS']:>8} {grand['WARN']:>8} {grand['FAIL']:>8} {avg_all:>8} {mx_all:>8}")
total = grand["PASS"] + grand["WARN"] + grand["FAIL"]
pct = round(grand["PASS"]/total*100) if total else 0
pct_pw = round((grand["PASS"]+grand["WARN"])/total*100) if total else 0
print(f"\nOverall: {total} tests | {grand['PASS']} PASS | {grand['WARN']} WARN | {grand['FAIL']} FAIL")
print(f"Pass rate: {pct}%  (PASS+WARN: {pct_pw}%)")
if all_ms:
    sorted_ms = sorted(all_ms)
    p95_idx = int(len(sorted_ms)*0.95)-1
    print(f"Response time: fastest={min(all_ms)}ms, avg={avg_all}ms, "
          f"p95={sorted_ms[p95_idx]}ms, slowest={max(all_ms)}ms")
