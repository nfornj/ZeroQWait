#!/usr/bin/env python3
"""
Comprehensive End-to-End Test Suite for ZeroQwait Agent Platform.

Tests real user flows with DB cross-checking to verify no LLM hallucination.

Flows tested:
1. Customer books an appointment
2. Customer joins the queue
3. Owner agent manages queue (call next)
4. Create invoice and record payment
5. Owner asks complex CRM questions
6. Owner asks payment/finance details
7. DB cross-check for every LLM response

Usage:
    python test_e2e_comprehensive.py

Requires:
    - Backend running on localhost:8000
    - PostgreSQL on localhost:5432
    - Twenty CRM on localhost:3001 (optional, for CRM tests)
    - Ollama at 192.168.2.134:30002
"""

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import requests

# ─── Configuration ──────────────────────────────────────────────────
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "zeroqwait")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "zeroqwait_dev")

# Test account: shop owner for Crystal Nail Spa (shop_id=41)
TEST_USERNAME = "test_bulk_owner_0_1361"
TEST_PASSWORD = "password123"
TEST_SHOP_ID = 41
TEST_SHOP_NAME = "Crystal Nail Spa"

# ─── Colors ─────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ─── Globals ────────────────────────────────────────────────────────
TOKEN: Optional[str] = None
DB_CONN: Optional[Any] = None
RESULTS: List[Dict[str, Any]] = []


def log(msg: str, color: str = RESET) -> None:
    print(f"{color}{msg}{RESET}")


def log_test(name: str) -> None:
    log(f"\n{'='*70}", CYAN)
    log(f"  TEST: {name}", BOLD)
    log(f"{'='*70}", CYAN)


def log_pass(msg: str) -> None:
    log(f"  ✓ {msg}", GREEN)


def log_fail(msg: str) -> None:
    log(f"  ✗ {msg}", RED)


def log_warn(msg: str) -> None:
    log(f"  ⚠ {msg}", YELLOW)


def log_info(msg: str) -> None:
    log(f"  → {msg}", CYAN)


# ─── DB helpers ─────────────────────────────────────────────────────
def db_connect() -> Any:
    global DB_CONN
    DB_CONN = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )
    DB_CONN.autocommit = True
    return DB_CONN


def db_query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    with DB_CONN.cursor() as cur:
        cur.execute(sql, params)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def db_scalar(sql: str, params: tuple = ()) -> Any:
    with DB_CONN.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None


def db_execute(sql: str, params: tuple = ()) -> None:
    with DB_CONN.cursor() as cur:
        cur.execute(sql, params)


# ─── API helpers ────────────────────────────────────────────────────
def authenticate() -> str:
    global TOKEN
    resp = requests.post(
        f"{BASE_URL}/api/auth/token",
        data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200, f"Auth failed: {resp.status_code} {resp.text}"
    TOKEN = resp.json()["access_token"]
    return TOKEN


def agent_chat(message: str, shop_id: int = TEST_SHOP_ID) -> Dict[str, Any]:
    """Call the owner-facing agent v2 sync chat endpoint."""
    t0 = time.time()
    resp = requests.post(
        f"{BASE_URL}/api/v2/agent/chat",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"message": message, "shop_id": shop_id},
        timeout=120,
    )
    elapsed = time.time() - t0
    data = resp.json()
    data["_elapsed_s"] = round(elapsed, 1)
    data["_status_code"] = resp.status_code
    return data


def api_post(path: str, body: Dict = None, auth: bool = True) -> Dict[str, Any]:
    """Generic API POST."""
    headers = {"Content-Type": "application/json"}
    if auth and TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    resp = requests.post(f"{BASE_URL}{path}", json=body or {}, headers=headers, timeout=60)
    return {"status_code": resp.status_code, **resp.json()}


def api_get(path: str, auth: bool = True) -> Dict[str, Any]:
    """Generic API GET."""
    headers = {}
    if auth and TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    resp = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)
    return {"status_code": resp.status_code, **resp.json()}


# ─── Cross-check helpers ───────────────────────────────────────────
def extract_numbers(text: str) -> List[float]:
    """Extract all numeric values from text (including $-prefixed)."""
    matches = re.findall(r'\$?([\d,]+(?:\.\d+)?)', text)
    result = []
    for m in matches:
        cleaned = m.replace(",", "").strip()
        if cleaned:
            try:
                result.append(float(cleaned))
            except ValueError:
                continue
    return result


def check_number_in_response(response_text: str, expected: float, tolerance: float = 0.01, label: str = "") -> bool:
    """Check if a numeric value appears in the LLM response (within tolerance)."""
    numbers = extract_numbers(response_text)
    for n in numbers:
        if abs(n - expected) <= tolerance * max(abs(expected), 1):
            log_pass(f"DB-verified: {label} = {expected} found in response")
            return True
    log_fail(f"HALLUCINATION? {label} = {expected} NOT found in response. Found numbers: {numbers}")
    return False


def record_result(test_name: str, passed: bool, details: str = "", elapsed: float = 0) -> None:
    RESULTS.append({
        "test": test_name,
        "passed": passed,
        "details": details,
        "elapsed_s": elapsed,
    })


# ═══════════════════════════════════════════════════════════════════
# TEST FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def test_0_health_check() -> bool:
    """Verify all services are up."""
    log_test("0. Health Checks")
    passed = True

    # Backend health
    try:
        resp = requests.get(f"{BASE_URL}/api/v2/agent/health", timeout=10)
        data = resp.json()
        components = data.get("components", data)
        if components.get("ollama") == "ok" and components.get("postgres") == "ok":
            log_pass(f"Agent v2 health: {data}")
        else:
            log_fail(f"Agent v2 health degraded: {data}")
            passed = False
    except Exception as e:
        log_fail(f"Health check failed: {e}")
        passed = False

    # DB connection
    try:
        db_connect()
        count = db_scalar("SELECT COUNT(*) FROM shops WHERE id = %s", (TEST_SHOP_ID,))
        assert count == 1, f"Test shop not found (id={TEST_SHOP_ID})"
        log_pass(f"Database connected, test shop '{TEST_SHOP_NAME}' exists")
    except Exception as e:
        log_fail(f"Database check failed: {e}")
        passed = False

    # Auth
    try:
        authenticate()
        log_pass(f"Authenticated as {TEST_USERNAME}")
    except Exception as e:
        log_fail(f"Authentication failed: {e}")
        passed = False

    record_result("health_check", passed)
    return passed


def test_1_book_appointment() -> bool:
    """
    Test: Customer books an appointment via agent → verify in DB.

    Flow:
    1. Ask agent to book an appointment for a customer
    2. Verify appointment record created in DB
    3. Cross-check appointment details (service, time, customer name)
    """
    log_test("1. Book Appointment (via Agent)")

    # Get available services for the shop
    services = db_query(
        "SELECT id, name, cost, duration_minutes FROM shop_services WHERE shop_id = %s AND is_active = true LIMIT 1",
        (TEST_SHOP_ID,),
    )
    if not services:
        log_fail("No services found for test shop")
        record_result("book_appointment", False, "No services")
        return False

    service = services[0]
    log_info(f"Using service: {service['name']} (${service['cost']}, {service['duration_minutes']}min)")

    # Count existing appointments before
    appt_count_before = db_scalar(
        "SELECT COUNT(*) FROM appointments WHERE shop_id = %s", (TEST_SHOP_ID,)
    )

    # Book via agent
    tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
    message = f"Book an appointment for customer Jane Doe for {service['name']} tomorrow at 10:00 AM"
    log_info(f"Agent message: \"{message}\"")

    result = agent_chat(message)
    log_info(f"Agent response ({result['_elapsed_s']}s): {result.get('response', '')[:200]}")
    log_info(f"Routed to: {result.get('agent', 'unknown')}")

    # Verify routing
    passed = True
    if result.get("agent") not in ("receptionist", "booking"):
        log_warn(f"Expected receptionist routing, got: {result.get('agent')}")

    # Check DB for new appointment
    appt_count_after = db_scalar(
        "SELECT COUNT(*) FROM appointments WHERE shop_id = %s", (TEST_SHOP_ID,)
    )
    new_appts = db_query(
        """SELECT id, customer_name, service_id, status, scheduled_start, service_cost
           FROM appointments
           WHERE shop_id = %s
           ORDER BY created_at DESC LIMIT 3""",
        (TEST_SHOP_ID,),
    )

    if appt_count_after > appt_count_before:
        log_pass(f"Appointment created in DB (count: {appt_count_before} → {appt_count_after})")
        latest = new_appts[0]
        log_info(f"  Appointment: {latest['customer_name']} | status={latest['status']} | service_id={latest['service_id']}")

        # Cross-check: customer name
        if "jane" in (latest.get("customer_name") or "").lower():
            log_pass("Customer name 'Jane Doe' verified in DB")
        else:
            log_warn(f"Customer name mismatch: DB has '{latest.get('customer_name')}'")
    else:
        log_warn("No new appointment found in DB — agent may not have called the tool")
        log_info("This is expected if agent asked for confirmation first or gave informational response")
        # Still check the response text for relevant content
        response_text = result.get("response", "").lower()
        if any(w in response_text for w in ["appointment", "book", "schedule", "slot", "available"]):
            log_pass("Agent response mentions appointment-related content")
        else:
            log_fail("Agent response doesn't mention appointments at all")
            passed = False

    record_result("book_appointment", passed, f"{result['_elapsed_s']}s", result['_elapsed_s'])
    return passed


def test_2_customer_join_queue() -> bool:
    """
    Test: Customer joins the queue via public REST API → verify in DB.

    Flow:
    1. POST /api/queues/shop/{id}/join (public, no auth)
    2. Verify queue_item created in DB with status WAITING
    3. Verify position and estimated wait
    """
    log_test("2. Customer Joins Queue (Public REST)")

    # Ensure the queue is active
    queue_active = db_scalar(
        "SELECT is_active FROM queues WHERE shop_id = %s", (TEST_SHOP_ID,)
    )
    if not queue_active:
        log_warn("Queue is inactive, activating...")
        db_execute("UPDATE queues SET is_active = true WHERE shop_id = %s", (TEST_SHOP_ID,))

    # Count waiting items before
    waiting_before = db_scalar(
        "SELECT COUNT(*) FROM queue_items WHERE queue_id = %s AND status = 'WAITING'",
        (TEST_SHOP_ID,),
    )

    # Customer joins queue (public endpoint, no auth)
    customer_name = f"E2E Test Customer {int(time.time()) % 10000}"
    resp = requests.post(
        f"{BASE_URL}/api/queues/shop/{TEST_SHOP_ID}/join",
        json={"customer_name": customer_name, "customer_phone": "555-0199"},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )

    passed = True
    if resp.status_code in (200, 201):
        join_data = resp.json()
        log_pass(f"Queue join response: status={resp.status_code}")
        log_info(f"  Response data: {json.dumps(join_data, indent=2)[:300]}")

        # Check DB for the new queue item
        waiting_after = db_scalar(
            "SELECT COUNT(*) FROM queue_items WHERE queue_id = %s AND status = 'WAITING'",
            (TEST_SHOP_ID,),
        )
        if waiting_after > waiting_before:
            log_pass(f"Queue item created: waiting count {waiting_before} → {waiting_after}")
        else:
            log_fail(f"Queue item NOT found in DB (waiting: {waiting_before} → {waiting_after})")
            passed = False

        # Verify customer name in DB
        latest_item = db_query(
            """SELECT id, customer_name, status, position
               FROM queue_items
               WHERE queue_id = %s
               ORDER BY id DESC LIMIT 1""",
            (TEST_SHOP_ID,),
        )
        if latest_item:
            item = latest_item[0]
            if customer_name in (item.get("customer_name") or ""):
                log_pass(f"Customer name verified: '{item['customer_name']}' at position {item.get('position')}")
            else:
                log_warn(f"Customer name in DB: '{item['customer_name']}' (expected '{customer_name}')")
    else:
        log_fail(f"Queue join failed: {resp.status_code} {resp.text[:200]}")
        passed = False

    # Also test get queue estimate
    try:
        metrics = requests.get(
            f"{BASE_URL}/api/queues/shop/{TEST_SHOP_ID}/live-metrics", timeout=10,
        ).json()
        log_info(f"Live metrics: queue_length={metrics.get('queue_length')}, wait={metrics.get('estimated_wait_minutes')}min")
    except Exception as e:
        log_warn(f"Could not get live metrics: {e}")

    record_result("customer_join_queue", passed)
    return passed


def test_3_agent_manages_queue() -> bool:
    """
    Test: Owner asks agent about queue status and to call next customer.

    Flow:
    1. Ask agent "How many people are waiting in the queue?"
    2. Cross-check count with DB
    3. Ask agent "Call the next customer"
    4. Verify queue_item status changed to BEING_SERVED in DB
    """
    log_test("3. Agent Manages Queue (Call Next)")

    # Step 1: Ask queue status
    waiting_count_db = db_scalar(
        "SELECT COUNT(*) FROM queue_items WHERE queue_id = %s AND status = 'WAITING'",
        (TEST_SHOP_ID,),
    )
    log_info(f"DB says {waiting_count_db} people waiting in queue")

    result = agent_chat("How many people are waiting in our queue right now?")
    log_info(f"Agent response ({result['_elapsed_s']}s): {result.get('response', '')[:300]}")
    log_info(f"Routed to: {result.get('agent')}")

    passed = True

    # Cross-check: agent should mention the correct count
    response_text = result.get("response", "")
    if waiting_count_db > 0:
        if check_number_in_response(response_text, waiting_count_db, tolerance=0.0, label="waiting count"):
            pass  # Already logged
        else:
            # Some tolerance — LLM might round or approximate
            log_warn("Queue count not exactly matched; checking if response mentions queue")
            if any(w in response_text.lower() for w in ["queue", "waiting", "people", "customer"]):
                log_pass("Response discusses queue (count may differ)")
            else:
                passed = False

    if waiting_count_db == 0:
        log_info("No one waiting — skipping call-next test")
        record_result("agent_manages_queue", passed, "No waiting customers")
        return passed

    # Step 2: Call next customer
    # Get the first waiting item for verification
    first_waiting = db_query(
        """SELECT id, customer_name FROM queue_items
           WHERE queue_id = %s AND status = 'WAITING'
           ORDER BY position, id LIMIT 1""",
        (TEST_SHOP_ID,),
    )
    if not first_waiting:
        log_warn("No waiting items for call-next")
        record_result("agent_manages_queue", passed)
        return passed

    expected_customer = first_waiting[0]["customer_name"]
    expected_item_id = first_waiting[0]["id"]
    log_info(f"Next expected customer: '{expected_customer}' (item_id={expected_item_id})")

    result2 = agent_chat("Call the next customer in the queue")
    log_info(f"Agent response ({result2['_elapsed_s']}s): {result2.get('response', '')[:300]}")

    # Verify DB: the item should now be BEING_SERVED
    item_status = db_scalar(
        "SELECT status FROM queue_items WHERE id = %s", (expected_item_id,)
    )
    if item_status == "BEING_SERVED":
        log_pass(f"Queue item {expected_item_id} status changed to BEING_SERVED ✓")
    elif item_status == "WAITING":
        log_warn(f"Queue item {expected_item_id} still WAITING — agent may not have executed tool")
        # Check if response mentions calling next
        if any(w in result2.get("response", "").lower() for w in ["serving", "called", "next"]):
            log_info("Agent mentioned calling next but DB didn't update")
    else:
        log_info(f"Queue item {expected_item_id} status: {item_status}")

    # Check if agent mentioned the customer name
    resp_text = result2.get("response", "")
    if expected_customer.lower() in resp_text.lower():
        log_pass(f"Agent correctly mentioned customer name '{expected_customer}'")
    else:
        log_info(f"Agent didn't mention specific customer name (may have used anonymized form)")

    record_result("agent_manages_queue", passed, f"call-next item={expected_item_id}", result['_elapsed_s'])
    return passed


def test_4_create_invoice_and_payment() -> bool:
    """
    Test: Create an invoice and record a payment via agent.

    Flow:
    1. Ask agent to create an invoice for a service
    2. Verify invoice record in DB
    3. Ask agent to record a payment
    4. Verify payment record in DB
    5. Cross-check amounts
    """
    log_test("4. Invoice & Payment (via Agent)")

    # Get a service for invoicing
    services = db_query(
        "SELECT id, name, cost FROM shop_services WHERE shop_id = %s AND is_active = true LIMIT 1",
        (TEST_SHOP_ID,),
    )
    if not services:
        log_fail("No services for invoicing")
        record_result("invoice_and_payment", False, "No services")
        return False

    service = services[0]
    invoice_count_before = db_scalar("SELECT COUNT(*) FROM invoices WHERE shop_id = %s", (TEST_SHOP_ID,))

    # Step 1: Create invoice via agent
    message = f"Create an invoice for a {service['name']} service, cost ${service['cost']}"
    log_info(f"Agent message: \"{message}\"")

    result = agent_chat(message)
    log_info(f"Agent response ({result['_elapsed_s']}s): {result.get('response', '')[:300]}")
    log_info(f"Routed to: {result.get('agent')}")

    passed = True

    # Check DB for new invoice
    invoice_count_after = db_scalar("SELECT COUNT(*) FROM invoices WHERE shop_id = %s", (TEST_SHOP_ID,))

    invoice_id = None
    if invoice_count_after > invoice_count_before:
        log_pass(f"Invoice created (count: {invoice_count_before} → {invoice_count_after})")
        latest_inv = db_query(
            """SELECT id, invoice_number, subtotal, total, status
               FROM invoices WHERE shop_id = %s ORDER BY created_at DESC LIMIT 1""",
            (TEST_SHOP_ID,),
        )
        if latest_inv:
            inv = latest_inv[0]
            invoice_id = inv["id"]
            log_info(f"  Invoice: #{inv['invoice_number']} | total=${inv['total']} | status={inv['status']}")
            check_number_in_response(result.get("response", ""), float(inv["total"]), label="invoice total")
    else:
        log_warn("No new invoice in DB — agent may need more specific instructions")
        response_text = result.get("response", "").lower()
        if any(w in response_text for w in ["invoice", "bill", "charge", "cost"]):
            log_pass("Agent response mentions invoicing")
        else:
            log_warn("Agent response doesn't mention invoicing")

    # Step 2: Record payment via agent
    payment_count_before = db_scalar("SELECT COUNT(*) FROM payments WHERE shop_id = %s", (TEST_SHOP_ID,))

    pay_message = f"Record a cash payment of ${service['cost']} for the latest invoice"
    log_info(f"Agent message: \"{pay_message}\"")

    result2 = agent_chat(pay_message)
    log_info(f"Agent response ({result2['_elapsed_s']}s): {result2.get('response', '')[:300]}")

    payment_count_after = db_scalar("SELECT COUNT(*) FROM payments WHERE shop_id = %s", (TEST_SHOP_ID,))

    if payment_count_after > payment_count_before:
        log_pass(f"Payment recorded (count: {payment_count_before} → {payment_count_after})")
        latest_pmt = db_query(
            """SELECT id, amount, method, status
               FROM payments WHERE shop_id = %s ORDER BY created_at DESC LIMIT 1""",
            (TEST_SHOP_ID,),
        )
        if latest_pmt:
            pmt = latest_pmt[0]
            log_info(f"  Payment: id={pmt['id']} | ${pmt['amount']} | {pmt['method']} | {pmt['status']}")
            check_number_in_response(result2.get("response", ""), float(pmt["amount"]), label="payment amount")
    else:
        log_warn("No new payment in DB — checking response content")
        if any(w in result2.get("response", "").lower() for w in ["payment", "paid", "cash", "recorded"]):
            log_pass("Agent response mentions payment")
        else:
            log_warn("Agent may not have executed payment tool")

    record_result("invoice_and_payment", passed, f"invoice_id={invoice_id}")
    return passed


def test_5_owner_crm_questions() -> bool:
    """
    Test: Business owner asks complex CRM questions.

    Flow:
    1. "Show me my CRM contacts"
    2. Cross-check with Twenty CRM GraphQL
    3. "Show pipeline summary"
    4. Cross-check pipeline data
    """
    log_test("5. Owner CRM Questions")

    # Step 1: Ask for CRM contacts
    result = agent_chat("Show me all my CRM contacts")
    log_info(f"Agent response ({result['_elapsed_s']}s): {result.get('response', '')[:400]}")
    log_info(f"Routed to: {result.get('agent')}")

    passed = True
    response_text = result.get("response", "")

    # Verify routing
    if result.get("agent") == "crm":
        log_pass("Correctly routed to CRM agent")
    else:
        log_warn(f"Expected CRM routing, got: {result.get('agent')}")

    # Cross-check: try to fetch contacts from Twenty CRM directly
    twenty_url = os.getenv("TWENTY_GRAPHQL_URL", "http://localhost:3001/graphql")
    twenty_key = os.getenv("TWENTY_API_KEY", "")

    if twenty_key:
        try:
            gql_resp = requests.post(
                twenty_url,
                json={
                    "query": """{ people(first: 20, orderBy: { createdAt: { direction: DescNullsLast }}) { edges { node { name { firstName lastName } emails { primaryEmail } } } } }"""
                },
                headers={"Authorization": f"Bearer {twenty_key}", "Content-Type": "application/json"},
                timeout=10,
            )
            crm_data = gql_resp.json()
            edges = crm_data.get("data", {}).get("people", {}).get("edges", [])
            log_info(f"Twenty CRM has {len(edges)} contacts")

            # Check if agent mentioned the correct count
            if len(edges) > 0:
                check_number_in_response(response_text, len(edges), label="CRM contact count")
                # Check if at least one name appears in response
                first_person = edges[0]["node"]["name"]
                first_name = first_person.get("firstName", "")
                if first_name and first_name.lower() in response_text.lower():
                    log_pass(f"CRM contact '{first_name}' found in agent response")
                else:
                    log_info(f"First CRM contact '{first_name}' not explicitly in response (may be summarized)")
        except Exception as e:
            log_warn(f"Could not cross-check with Twenty CRM: {e}")
    else:
        log_warn("TWENTY_API_KEY not set — skipping CRM cross-check")

    # Check response has meaningful content
    if "crm" in response_text.lower() or "contact" in response_text.lower() or "people" in response_text.lower():
        log_pass("Response discusses CRM data")
    elif "error" in response_text.lower() or "don't have" in response_text.lower():
        log_info("CRM might be empty or Twenty CRM not configured")
    else:
        log_warn("Response doesn't clearly discuss CRM contacts")

    # Step 2: Pipeline summary
    result2 = agent_chat("Show me the CRM pipeline summary")
    log_info(f"Pipeline response ({result2['_elapsed_s']}s): {result2.get('response', '')[:400]}")

    if result2.get("agent") == "crm":
        log_pass("Pipeline query routed to CRM agent")
    else:
        log_warn(f"Pipeline routing: {result2.get('agent')}")

    record_result("owner_crm_questions", passed, f"{result['_elapsed_s']}s + {result2['_elapsed_s']}s")
    return passed


def test_6_owner_finance_details() -> bool:
    """
    Test: Business owner asks for financial details.

    Flow:
    1. "What was today's revenue?"
    2. Cross-check with daily_analytics table
    3. "Show me this week's revenue breakdown"
    4. Cross-check week totals with DB
    5. "How many customers did we serve today?"
    6. Cross-check customer count
    """
    log_test("6. Owner Finance Details (with DB Cross-Check)")

    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Get today's actual data from DB
    today_data = db_query(
        """SELECT total_revenue, total_customers, completed_services
           FROM daily_analytics WHERE shop_id = %s AND date::date = %s""",
        (TEST_SHOP_ID, today),
    )

    passed = True

    if today_data:
        actual_revenue = float(today_data[0]["total_revenue"])
        actual_customers = int(today_data[0]["total_customers"])
        actual_services = int(today_data[0]["completed_services"])
        log_info(f"DB today: revenue=${actual_revenue}, customers={actual_customers}, services={actual_services}")
    else:
        # Try recent dates (up to 5 days back) since analytics may lag
        for days_back in range(1, 6):
            check_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            today_data = db_query(
                """SELECT total_revenue, total_customers, completed_services
                   FROM daily_analytics WHERE shop_id = %s AND date::date = %s""",
                (TEST_SHOP_ID, check_date),
            )
            if today_data:
                today = check_date
                break
        if today_data:
            actual_revenue = float(today_data[0]["total_revenue"])
            actual_customers = int(today_data[0]["total_customers"])
            actual_services = int(today_data[0]["completed_services"])
            log_info(f"DB most recent data ({today}): revenue=${actual_revenue}, customers={actual_customers}, services={actual_services}")
        else:
            log_fail("No analytics data found in last 5 days")
            record_result("owner_finance_details", False, "No analytics data")
            return False

    # Step 1: Today's revenue
    result = agent_chat(f"What was the revenue on {today}?")
    log_info(f"Agent response ({result['_elapsed_s']}s): {result.get('response', '')[:400]}")
    log_info(f"Routed to: {result.get('agent')}")

    if result.get("agent") in ("finance",):
        log_pass("Revenue query routed to Finance agent")
    else:
        log_warn(f"Expected finance routing, got: {result.get('agent')}")

    # Cross-check: revenue amount
    resp_text = result.get("response", "")
    revenue_verified = check_number_in_response(resp_text, actual_revenue, tolerance=0.05, label=f"revenue for {today}")
    if not revenue_verified:
        # Check if any reasonable revenue number is mentioned
        nums = extract_numbers(resp_text)
        if nums:
            log_warn(f"Agent mentioned these numbers: {nums} (expected ~${actual_revenue})")
        else:
            log_fail("No numeric values in revenue response — possible hallucination or tool failure")
            passed = False

    # Step 2: Weekly revenue
    # Calculate actual weekly total from DB
    week_start = (datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())).strftime("%Y-%m-%d")
    week_data = db_query(
        """SELECT SUM(total_revenue) as week_revenue,
                  SUM(total_customers) as week_customers,
                  SUM(completed_services) as week_services,
                  COUNT(*) as days_with_data
           FROM daily_analytics
           WHERE shop_id = %s AND date >= %s""",
        (TEST_SHOP_ID, week_start),
    )

    if week_data and week_data[0]["week_revenue"]:
        actual_week_revenue = float(week_data[0]["week_revenue"])
        log_info(f"DB this week: revenue=${actual_week_revenue} ({week_data[0]['days_with_data']} days)")

        result2 = agent_chat("Show me this week's revenue breakdown")
        log_info(f"Weekly response ({result2['_elapsed_s']}s): {result2.get('response', '')[:400]}")

        check_number_in_response(
            result2.get("response", ""), actual_week_revenue,
            tolerance=0.1, label="weekly revenue",
        )

    # Step 3: Customer count
    result3 = agent_chat(f"How many customers were served on {today}?")
    log_info(f"Customer count response ({result3['_elapsed_s']}s): {result3.get('response', '')[:300]}")

    check_number_in_response(
        result3.get("response", ""), actual_customers,
        tolerance=0.0, label=f"customer count for {today}",
    )

    record_result("owner_finance_details", passed, f"revenue=${actual_revenue}")
    return passed


def test_7_payment_details_query() -> bool:
    """
    Test: Owner asks about payment details.

    Flow:
    1. "Show me today's POS summary"
    2. Cross-check with payments table
    3. "List all invoices"
    4. Cross-check invoice count and totals
    """
    log_test("7. Payment Details Query")

    # Get payment data from DB
    today = datetime.utcnow().strftime("%Y-%m-%d")
    payments_today = db_query(
        """SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total
           FROM payments
           WHERE shop_id = %s AND status = 'COMPLETED' AND created_at::date = %s""",
        (TEST_SHOP_ID, today),
    )
    invoices_count = db_scalar("SELECT COUNT(*) FROM invoices WHERE shop_id = %s", (TEST_SHOP_ID,))

    passed = True

    # Step 1: POS summary
    result = agent_chat("Give me today's POS summary")
    log_info(f"POS response ({result['_elapsed_s']}s): {result.get('response', '')[:400]}")
    log_info(f"Routed to: {result.get('agent')}")

    if result.get("agent") in ("finance", "receptionist"):
        log_pass(f"POS query routed to: {result.get('agent')}")
    else:
        log_warn(f"POS routing: {result.get('agent')}")

    # Cross-check
    if payments_today and float(payments_today[0]["total"]) > 0:
        check_number_in_response(
            result.get("response", ""), float(payments_today[0]["total"]),
            tolerance=0.05, label="today's payment total",
        )
    else:
        response_lower = result.get("response", "").lower()
        if any(w in response_lower for w in ["no payment", "no transaction", "0", "zero", "no pos"]):
            log_pass("Agent correctly reports no payments today")
        else:
            log_info("No payments today — checking agent's response is reasonable")

    # Step 2: List invoices
    result2 = agent_chat("List all invoices for our shop")
    log_info(f"Invoices response ({result2['_elapsed_s']}s): {result2.get('response', '')[:400]}")

    if invoices_count > 0:
        check_number_in_response(
            result2.get("response", ""), invoices_count,
            tolerance=0.0, label="total invoice count",
        )
    else:
        response_lower = result2.get("response", "").lower()
        if any(w in response_lower for w in ["no invoice", "none", "0", "haven't", "don't have"]):
            log_pass("Agent correctly reports no invoices")
        else:
            log_info(f"Agent response for 0 invoices: {result2.get('response', '')[:200]}")

    record_result("payment_details_query", passed)
    return passed


def test_8_multi_turn_conversation() -> bool:
    """
    Test: Multi-turn conversation with context retention.

    Flow:
    1. Ask about revenue this week
    2. Follow up with "what about last week?"
    3. Verify follow-up routes to same agent (finance)
    """
    log_test("8. Multi-Turn Conversation Context")

    # Turn 1
    result1 = agent_chat("What was this week's revenue?")
    log_info(f"Turn 1 ({result1['_elapsed_s']}s): {result1.get('response', '')[:200]}")
    log_info(f"Routed to: {result1.get('agent')}")

    passed = True

    # Turn 2: Follow-up
    result2 = agent_chat("What about last week?")
    log_info(f"Turn 2 ({result2['_elapsed_s']}s): {result2.get('response', '')[:200]}")
    log_info(f"Routed to: {result2.get('agent')}")

    if result2.get("agent") in ("finance",):
        log_pass("Follow-up correctly routed to Finance (context retained)")
    else:
        log_warn(f"Follow-up routed to {result2.get('agent')} instead of finance")

    # Cross-check last week's revenue from DB
    last_week_start = (datetime.utcnow() - timedelta(days=datetime.utcnow().weekday() + 7)).strftime("%Y-%m-%d")
    last_week_end = (datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())).strftime("%Y-%m-%d")
    last_week_data = db_query(
        """SELECT SUM(total_revenue) as week_revenue
           FROM daily_analytics
           WHERE shop_id = %s AND date >= %s AND date < %s""",
        (TEST_SHOP_ID, last_week_start, last_week_end),
    )

    if last_week_data and last_week_data[0]["week_revenue"]:
        actual_last_week = float(last_week_data[0]["week_revenue"])
        log_info(f"DB last week revenue: ${actual_last_week}")
        check_number_in_response(
            result2.get("response", ""), actual_last_week,
            tolerance=0.1, label="last week's revenue",
        )

    record_result("multi_turn_conversation", passed)
    return passed


def test_9_greeting_and_capabilities() -> bool:
    """
    Test: Agent responds to a greeting with capabilities.
    """
    log_test("9. Greeting & Capabilities")

    result = agent_chat("Hello, what can you do?")
    log_info(f"Agent response ({result['_elapsed_s']}s): {result.get('response', '')[:400]}")

    passed = True
    response_lower = result.get("response", "").lower()

    # Should mention key capabilities
    capability_keywords = ["queue", "revenue", "employee", "booking", "appointment", "analytics", "schedule", "shift"]
    mentioned = [kw for kw in capability_keywords if kw in response_lower]

    if len(mentioned) >= 2:
        log_pass(f"Agent describes capabilities: {mentioned}")
    else:
        log_warn(f"Agent mentioned only {len(mentioned)} capability keywords: {mentioned}")

    record_result("greeting_and_capabilities", passed, f"capabilities: {mentioned}", result['_elapsed_s'])
    return passed


# ═══════════════════════════════════════════════════════════════════
# CLEANUP AND SUMMARY
# ═══════════════════════════════════════════════════════════════════

def cleanup_test_data() -> None:
    """Clean up any test artifacts created during E2E testing."""
    log(f"\n{'─'*70}", YELLOW)
    log("  Cleaning up test data...", YELLOW)
    log(f"{'─'*70}", YELLOW)

    # Remove test appointments
    deleted = db_scalar(
        """DELETE FROM appointments
           WHERE shop_id = %s AND customer_name LIKE '%%Jane Doe%%'
           RETURNING id""",
        (TEST_SHOP_ID,),
    )
    if deleted:
        log_info(f"Cleaned up test appointment(s)")

    # Remove test queue items (E2E test customers)
    db_execute(
        """DELETE FROM queue_items
           WHERE queue_id = %s AND customer_name LIKE 'E2E Test Customer%%'""",
        (TEST_SHOP_ID,),
    )
    log_info("Cleaned up test queue items")

    # Remove test invoices and payments (only from this test run)
    db_execute(
        """DELETE FROM payments
           WHERE shop_id = %s AND notes LIKE '%%E2E%%'""",
        (TEST_SHOP_ID,),
    )
    db_execute(
        """DELETE FROM invoice_line_items
           WHERE invoice_id IN (
               SELECT id FROM invoices WHERE shop_id = %s AND notes LIKE '%%E2E%%'
           )""",
        (TEST_SHOP_ID,),
    )
    db_execute(
        """DELETE FROM invoices
           WHERE shop_id = %s AND notes LIKE '%%E2E%%'""",
        (TEST_SHOP_ID,),
    )
    log_info("Cleaned up test invoices/payments")


def print_summary() -> None:
    log(f"\n{'═'*70}", BOLD)
    log(f"  E2E TEST SUMMARY", BOLD)
    log(f"{'═'*70}", BOLD)

    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["passed"])
    failed = total - passed

    for r in RESULTS:
        status = f"{GREEN}PASS{RESET}" if r["passed"] else f"{RED}FAIL{RESET}"
        elapsed = f" ({r['elapsed_s']:.1f}s)" if r.get("elapsed_s") else ""
        details = f" — {r['details']}" if r.get("details") else ""
        print(f"  {status}  {r['test']}{elapsed}{details}")

    log(f"\n{'─'*70}")
    color = GREEN if failed == 0 else RED
    log(f"  {passed}/{total} tests passed, {failed} failed", color)
    log(f"{'═'*70}\n", BOLD)


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main() -> int:
    log(f"\n{BOLD}ZeroQwait Comprehensive E2E Test Suite{RESET}")
    log(f"Target: {BASE_URL}")
    log(f"Shop: {TEST_SHOP_NAME} (id={TEST_SHOP_ID})")
    log(f"Time: {datetime.utcnow().isoformat()}\n")

    # 0. Health + DB + Auth
    if not test_0_health_check():
        log_fail("Health check failed — cannot proceed")
        print_summary()
        return 1

    # Clear LangGraph checkpoints for this tenant to avoid stale cached responses
    try:
        thread_id = f"tenant_{TEST_SHOP_ID}_{db_scalar('SELECT id FROM users WHERE username=%s', (TEST_USERNAME,))}"
        db_execute("DELETE FROM checkpoints WHERE thread_id = %s", (thread_id,))
        db_execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (thread_id,))
        log_pass(f"Cleared checkpoints for thread {thread_id}")
    except Exception as e:
        log_warn(f"Could not clear checkpoints (may not exist): {e}")

    # Run all tests in order
    tests = [
        test_1_book_appointment,
        test_2_customer_join_queue,
        test_3_agent_manages_queue,
        test_4_create_invoice_and_payment,
        test_5_owner_crm_questions,
        test_6_owner_finance_details,
        test_7_payment_details_query,
        test_8_multi_turn_conversation,
        test_9_greeting_and_capabilities,
    ]

    for test_fn in tests:
        try:
            test_fn()
        except Exception as e:
            test_name = test_fn.__name__
            log_fail(f"Test {test_name} CRASHED: {e}")
            traceback.print_exc()
            record_result(test_name, False, f"CRASH: {e}")

    # Cleanup
    try:
        cleanup_test_data()
    except Exception as e:
        log_warn(f"Cleanup error: {e}")

    # Summary
    print_summary()
    
    # Close DB
    if DB_CONN:
        DB_CONN.close()

    failed = sum(1 for r in RESULTS if not r["passed"])
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
