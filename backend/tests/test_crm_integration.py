#!/usr/bin/env python3
"""
Test CRM integration through the agent v2 API.

Tests the full CRM flow:
  Owner message → classify_intent (crm) → execute_plan → _run_crm_agent → synthesize

Usage:
    python test_crm_integration.py [--base-url URL] [--token TOKEN]
    
    Or set env vars: BASE_URL, AUTH_TOKEN, TEST_SHOP_ID
"""

import argparse
import json
import os
import sys
import time

import httpx

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
TEST_SHOP_ID = int(os.getenv("TEST_SHOP_ID", "1"))


def _headers():
    return {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json",
    }


def test_health():
    """Test agent v2 health endpoint."""
    print("=== Test: Agent v2 Health ===")
    resp = httpx.get(f"{BASE_URL}/api/v2/agent/health", headers=_headers(), timeout=10)
    print(f"  Status: {resp.status_code}")
    print(f"  Body: {resp.text[:200]}")
    assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
    print("  PASS\n")


def test_crm_chat_sync(message: str, label: str = ""):
    """Test synchronous CRM chat."""
    print(f"=== Test: CRM Chat (sync) — {label or message[:40]} ===")
    resp = httpx.post(
        f"{BASE_URL}/api/v2/agent/chat",
        json={"message": message, "shop_id": TEST_SHOP_ID},
        headers=_headers(),
        timeout=120,
    )
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        content = data.get("response", data.get("content", str(data)))
        print(f"  Response: {content[:300]}...")
        return data
    else:
        print(f"  Error: {resp.text[:300]}")
        return None


def test_crm_chat_stream(message: str, label: str = ""):
    """Test SSE streaming CRM chat."""
    print(f"=== Test: CRM Chat (stream) — {label or message[:40]} ===")
    collected_text = ""
    collected_events = []

    with httpx.stream(
        "POST",
        f"{BASE_URL}/api/v2/agent/chat/stream",
        json={"message": message, "shop_id": TEST_SHOP_ID},
        headers=_headers(),
        timeout=120,
    ) as resp:
        print(f"  Status: {resp.status_code}")
        for line in resp.iter_lines():
            line = line.strip()
            if not line:
                continue
            if line == "[DONE]" or line == "data: [DONE]":
                break
            if line.startswith("data: "):
                payload = line[6:]
                try:
                    event = json.loads(payload)
                    event_type = event.get("type", "unknown")
                    collected_events.append(event_type)
                    if event_type == "text":
                        collected_text += event.get("content", "")
                    elif event_type == "thinking_step":
                        step = event.get("step", "")
                        status = event.get("status", "")
                        agent = event.get("agent", "")
                        print(f"  [thinking] {step} ({status}) agent={agent}")
                    elif event_type == "agent_switch":
                        print(f"  [agent_switch] → {event.get('agent')}")
                    elif event_type == "error":
                        print(f"  [error] {event.get('message', '')[:200]}")
                except json.JSONDecodeError:
                    pass

    print(f"  Events received: {collected_events}")
    print(f"  Response text: {collected_text[:300]}...")
    print()
    return collected_text


def test_crm_tools_directly():
    """Test CRM tools directly via Odoo (not through agent pipeline)."""
    print("=== Test: CRM Tools (Odoo direct import) ===")
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
        from agents.tools import odoo_tools
        import asyncio

        shop_id = TEST_SHOP_ID

        print("  Testing odoo_get_contacts...")
        contacts = asyncio.run(odoo_tools.odoo_get_contacts(shop_id=shop_id, limit=5))
        print(f"    Got {contacts.get('count', 0)} contacts")
        if contacts.get("contacts"):
            print(f"    First: {contacts['contacts'][0].get('name')}")

        print("  Testing odoo_get_companies...")
        companies = asyncio.run(odoo_tools.odoo_get_companies(shop_id=shop_id, limit=5))
        print(f"    Got {companies.get('count', 0)} companies")

        print("  Testing odoo_get_pipeline_summary...")
        pipeline = asyncio.run(odoo_tools.odoo_get_pipeline_summary(shop_id=shop_id))
        print(f"    Total leads: {pipeline.get('total_leads', 0)}")
        for stage in pipeline.get("pipeline", []):
            print(f"      {stage['stage']}: {stage['count']} leads, ${stage['total_revenue']:,.2f}")

        print("  Testing odoo_get_leads...")
        leads = asyncio.run(odoo_tools.odoo_get_leads(shop_id=shop_id, limit=5))
        print(f"    Got {leads.get('count', 0)} leads")

        print("  Testing odoo_get_products...")
        products = asyncio.run(odoo_tools.odoo_get_products(shop_id=shop_id, limit=5))
        print(f"    Got {products.get('count', 0)} products")

        print("  PASS\n")
    except Exception as e:
        print(f"  FAIL: {e}\n")


def main():
    global BASE_URL, AUTH_TOKEN, TEST_SHOP_ID
    
    parser = argparse.ArgumentParser(description="Test CRM integration")
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--token", default=AUTH_TOKEN)
    parser.add_argument("--shop-id", type=int, default=TEST_SHOP_ID)
    parser.add_argument("--tools-only", action="store_true", help="Only test CRM tools directly")
    parser.add_argument("--stream-only", action="store_true", help="Only test SSE streaming")
    args = parser.parse_args()

    BASE_URL = args.base_url
    AUTH_TOKEN = args.token
    TEST_SHOP_ID = args.shop_id

    print(f"CRM Integration Test Suite")
    print(f"  Base URL: {BASE_URL}")
    print(f"  Shop ID: {TEST_SHOP_ID}")
    print(f"  Token: {'*' * 8}...{AUTH_TOKEN[-4:] if len(AUTH_TOKEN) >= 4 else '(not set)'}")
    print()

    if args.tools_only:
        test_crm_tools_directly()
        return

    # Test CRM-intent messages through the agent pipeline
    crm_test_messages = [
        ("Who are my contacts?", "people list"),
        ("How many companies do I have?", "companies"),
        ("Show me my pipeline summary", "pipeline summary"),
        ("What notes have I added recently?", "notes"),
        ("How many open tasks do I have?", "tasks"),
        ("Show me details about client John Smith", "person search"),
        ("What are my top opportunities?", "opportunities"),
    ]

    if args.stream_only:
        for msg, label in crm_test_messages:
            test_crm_chat_stream(msg, label)
            time.sleep(1)
        return

    # Full test suite
    test_health()

    # Test sync endpoint
    for msg, label in crm_test_messages[:3]:
        test_crm_chat_sync(msg, label)
        time.sleep(1)

    # Test stream endpoint
    for msg, label in crm_test_messages[3:]:
        test_crm_chat_stream(msg, label)
        time.sleep(1)

    print("=== ALL TESTS COMPLETED ===")


if __name__ == "__main__":
    main()
