#!/usr/bin/env python3
"""
Phase 6 test: Registration flow end-to-end.

Confirms:
1. POST /api/users (create user)
2. POST /api/auth/token (login)
3. POST /api/shops/ (create shop + auto-provision schema)
4. GET /api/shops/my-shops (list owner's shops)
5. Tenant schema is provisioned after shop creation
"""

import os
import sys
import uuid
import pytest
import requests

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:30000")


def _unique_email() -> str:
    return f"testuser_{uuid.uuid4().hex[:8]}@test.zeroqwait.com"


def _unique_slug() -> str:
    return f"test-shop-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def registered_user():
    """Create a user and return (email, password, user_id)."""
    email = _unique_email()
    password = "TestPass123!"
    r = requests.post(f"{BASE_URL}/api/users", json={
        "email": email,
        "password": password,
        "full_name": "Phase6 Tester",
        "role": "shop_owner",
    }, timeout=10)
    assert r.status_code == 201, f"User creation failed: {r.status_code} {r.text}"
    data = r.json()
    return {"email": email, "password": password, "user_id": data["id"]}


@pytest.fixture(scope="module")
def auth_token(registered_user):
    """Obtain a JWT for the registered user."""
    r = requests.post(f"{BASE_URL}/api/auth/token", data={
        "username": registered_user["email"],
        "password": registered_user["password"],
    }, timeout=10)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def created_shop(auth_token):
    """Create a shop and return the shop data."""
    slug = _unique_slug()
    r = requests.post(
        f"{BASE_URL}/api/shops/",
        json={
            "name": f"Phase6 Test Shop {slug}",
            "slug": slug,
            "description": "Automated phase 6 test shop",
            "category": "barbershop",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=15,
    )
    assert r.status_code in (200, 201), f"Shop creation failed: {r.status_code} {r.text}"
    return r.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_user_creation(registered_user):
    assert registered_user["user_id"] > 0


def test_login(auth_token):
    assert auth_token and len(auth_token) > 10


def test_shop_creation(created_shop):
    assert created_shop["id"] > 0
    assert "slug" in created_shop


def test_my_shops(auth_token, created_shop):
    r = requests.get(
        f"{BASE_URL}/api/shops/my-shops",
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=10,
    )
    assert r.status_code == 200
    shops = r.json()
    shop_ids = [s["id"] for s in shops]
    assert created_shop["id"] in shop_ids, "New shop not in my-shops"


def test_tenant_schema_provisioned_after_shop_creation(created_shop):
    """After shop creation, tenant_<id> schema should exist in PostgreSQL."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database import SessionLocal
    from tenant_manager import tenant_schema_exists

    shop_id = created_shop["id"]
    db = SessionLocal()
    try:
        exists = tenant_schema_exists(db, shop_id)
        assert exists, (
            f"tenant_{shop_id} schema was NOT created after shop registration. "
            "Check ensure_shop_schema hook in shops/router.py"
        )
    finally:
        db.close()


def test_shop_health_endpoint(created_shop, auth_token):
    r = requests.get(
        f"{BASE_URL}/api/v2/agent/health",
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=10,
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") in ("ok", "degraded"), f"Unexpected health status: {data}"


if __name__ == "__main__":
    import pytest as _pt
    _pt.main([__file__, "-v"])
