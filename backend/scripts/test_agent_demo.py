#!/usr/bin/env python3
"""
Comprehensive agent demo test for shop_id=4 (Prestige Cuts Barber Shop).
Tests all major categories: Queue, Finance, HR, CRM/Odoo, Inventory, General.

Usage:
    python3 backend/scripts/test_agent_demo.py
"""

import json
import time
import sys
import os
import requests

BASE_URL = os.environ.get("BASE_URL", "http://192.168.2.134:30000")
OWNER_EMAIL = "owner_danielle_johnson_1@example-zeroqwait.com"
OWNER_PASS  = "testpass123"
SHOP_ID     = 4

# ─── colour codes ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ─── Test questions ───────────────────────────────────────────────────────────
TESTS = [
    # (category, question, pass_keywords)  — pass if ANY keyword found in response
    ("Queue",    "How many people are currently in the queue?",                  ["waiting", "queue", "customer", "5", "people"]),
    ("Queue",    "Who is next in line?",                                         ["next", "queue", "waiting", "first", "customer"]),
    ("Queue",    "What is the current average wait time?",                       ["wait", "minute", "time", "average"]),
    ("Queue",    "How many customers were served today?",                        ["served", "completed", "today", "customer"]),
    ("Queue",    "Can you close the queue for today?",                           ["close", "queue", "confirm", "approval", "sure"]),

    ("Finance",  "What was the total revenue today?",                           ["revenue", "today", "$", "dollar", "earned"]),
    ("Finance",  "Show me this week's earnings",                                ["week", "revenue", "earning", "$", "total"]),
    ("Finance",  "Which service makes the most money?",                         ["service", "revenue", "popular", "haircut", "shave", "color", "beard"]),
    ("Finance",  "Give me a financial summary for last month",                  ["month", "revenue", "total", "summary", "analytics"]),
    ("Finance",  "What is our average revenue per customer?",                   ["average", "per customer", "revenue", "$"]),

    ("HR",       "Who are my employees?",                                       ["employee", "staff", "barber", "team", "worker"]),
    ("HR",       "Who is working today?",                                       ["today", "working", "shift", "employee", "schedule"]),
    ("HR",       "Add a new employee named Carlos Rivera",                      ["add", "employee", "carlos", "rivera", "creat", "new"]),
    ("HR",       "Show me the shift schedule for this week",                    ["shift", "schedule", "week", "employee"]),

    ("CRM",      "Show me my leads and opportunities",                          ["lead", "opportunit", "crm", "pipeline", "deal"]),
    ("CRM",      "Who are my top clients?",                                     ["client", "contact", "customer", "top", "vip"]),
    ("CRM",      "Create a new lead for Marcus Johnson interested in VIP membership", ["lead", "creat", "marcus", "johnson", "opportunit"]),
    ("CRM",      "What is my current sales pipeline?",                          ["pipeline", "lead", "opportunit", "stage", "deal", "crm"]),
    ("CRM",      "Show me invoice summary",                                     ["invoice", "bill", "payment", "account", "total"]),

    ("Inventory","Do we have any low stock supplies?",                          ["stock", "inventory", "supply", "low", "item", "odoo"]),
    ("Inventory","What products do we carry?",                                  ["product", "service", "item", "offer", "sell", "carry"]),
    ("Inventory","How much hair color do we have in stock?",                    ["stock", "inventory", "color", "product", "odoo", "item"]),

    ("General",  "Hello, what can you help me with?",                          ["help", "assist", "queue", "employee", "finance", "hr", "receptionist"]),
    ("General",  "What are our shop hours?",                                    ["hour", "open", "close", "schedule", "time"]),
    ("General",  "Give me a quick status update on the shop",                  ["status", "queue", "revenue", "employee", "today", "summary"]),
]

# ─── Auth ─────────────────────────────────────────────────────────────────────

def login() -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/token",
        data={"username": OWNER_EMAIL, "password": OWNER_PASS},
        timeout=15,
    )
    if r.status_code != 200:
        print(f"{RED}Login failed: {r.status_code} {r.text[:200]}{RESET}")
        sys.exit(1)
    token = r.json()["access_token"]
    print(f"{GREEN}✓ Logged in as {OWNER_EMAIL}{RESET}")
    return token


# ─── SSE streaming chat ───────────────────────────────────────────────────────

def ask(question: str, token: str, shop_id: int = SHOP_ID, timeout: int = 120) -> tuple[str, float]:
    """
    POST to /api/v2/agent/chat/stream and collect the full SSE text response.
    Returns (response_text, elapsed_seconds).
    """
    headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
    import uuid
    payload = {
        "message":    question,
        "shop_id":    shop_id,
        "session_id": f"test_{uuid.uuid4().hex[:12]}",
        "is_voice":   False,
    }

    t0 = time.time()
    text_parts: list[str] = []
    agent_used = "unknown"

    try:
        with requests.post(
            f"{BASE_URL}/api/v2/agent/chat/stream",
            json=payload,
            headers=headers,
            stream=True,
            timeout=timeout,
        ) as resp:
            if resp.status_code != 200:
                return f"[HTTP {resp.status_code}] {resp.text[:300]}", 0.0

            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                if raw_line.startswith("data: "):
                    data_str = raw_line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        # plain text fallback
                        text_parts.append(data_str)
                        continue

                    ctype = chunk.get("type", "")
                    if ctype == "text":
                        text_parts.append(chunk.get("content", ""))
                    elif ctype == "agent_switch":
                        agent_used = chunk.get("agent", agent_used)
                    elif ctype == "approval_required":
                        text_parts.append(f"[APPROVAL REQUIRED: {chunk.get('action', '')}]")
                        break  # don't block waiting for approval
    except requests.exceptions.Timeout:
        return "[TIMEOUT]", time.time() - t0
    except Exception as e:
        return f"[ERROR: {e}]", time.time() - t0

    elapsed = time.time() - t0
    full_text = "".join(text_parts).strip()
    return full_text, elapsed


# ─── Evaluation ───────────────────────────────────────────────────────────────

def evaluate(response: str, keywords: list[str]) -> bool:
    low = response.lower()
    return any(kw.lower() in low for kw in keywords)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}{CYAN}  Prestige Cuts Barber Shop — Agent Demo Test{RESET}")
    print(f"{BOLD}{CYAN}  Shop ID: {SHOP_ID}  |  {len(TESTS)} questions across 6 categories{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}\n")

    token = login()
    print()

    results: list[dict] = []
    current_category = None

    for idx, (category, question, keywords) in enumerate(TESTS, start=1):
        if category != current_category:
            current_category = category
            print(f"\n{BOLD}── {category} ─────────────────────────────────────────────────────{RESET}")

        if idx > 1:
            time.sleep(2)
        print(f"  [{idx:02d}] {question[:70]}")
        response, elapsed = ask(question, token)

        passed = evaluate(response, keywords)
        status  = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        trimmed = response[:200].replace("\n", " ") if response else "(empty)"

        print(f"       {status}  ({elapsed:.1f}s)  {YELLOW}{trimmed}{RESET}")

        results.append({
            "idx":       idx,
            "category":  category,
            "question":  question,
            "response":  response,
            "elapsed":   elapsed,
            "passed":    passed,
        })

    # ── Summary table ────────────────────────────────────────────────────────
    passed_count = sum(1 for r in results if r["passed"])
    fail_count   = len(results) - passed_count

    print(f"\n\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}  RESULTS SUMMARY — {passed_count}/{len(results)} passed{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}")

    header = f"{'#':>3}  {'Category':<12}  {'Q (truncated)':<40}  {'T(s)':>5}  {'Result'}"
    print(f"\n{BOLD}{header}{RESET}")
    print("─" * 80)

    failed_list: list[dict] = []
    for r in results:
        icon  = f"{GREEN}✓{RESET}" if r["passed"] else f"{RED}✗{RESET}"
        row   = f"{r['idx']:>3}  {r['category']:<12}  {r['question'][:40]:<40}  {r['elapsed']:>5.1f}  {icon}"
        print(row)
        if not r["passed"]:
            failed_list.append(r)

    # ── Category breakdown ───────────────────────────────────────────────────
    print(f"\n{BOLD}Category Breakdown:{RESET}")
    cats = {}
    for r in results:
        cats.setdefault(r["category"], []).append(r["passed"])
    for cat, outcomes in cats.items():
        n = len(outcomes)
        p = sum(outcomes)
        bar = "█" * p + "░" * (n - p)
        print(f"  {cat:<12}  {bar}  {p}/{n}")

    # ── Failed details ───────────────────────────────────────────────────────
    if failed_list:
        print(f"\n{BOLD}{RED}Failed questions:{RESET}")
        for r in failed_list:
            print(f"\n  [{r['idx']:02d}] {r['question']}")
            print(f"       Response: {r['response'][:300]}")
            print(f"       Expected any of: {r['keywords'] if 'keywords' in r else '(see test definition)'}")

    # ── Timing stats ─────────────────────────────────────────────────────────
    times = [r["elapsed"] for r in results if r["elapsed"] > 0]
    if times:
        print(f"\n{BOLD}Timing:{RESET}")
        print(f"  Avg: {sum(times)/len(times):.1f}s  |  Min: {min(times):.1f}s  |  Max: {max(times):.1f}s")

    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}\n")

    # Exit code for CI
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
