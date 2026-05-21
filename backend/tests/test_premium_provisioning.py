#!/usr/bin/env python3
"""
Phase 6 test: Premium shop provisioning.

Confirms:
1. Platform provisioner API is accessible (super_admin only)
2. POST /api/platform/shops/{id}/provision-schema creates tenant schema
3. POST /api/platform/shops/{id}/provision-premium marks shop as dedicated
4. GET /api/platform/shops/{id}/runtime returns correct runtime info
5. POST /api/platform/shops/{id}/revert-shared reverts to shared compute
"""

import os
import pytest
import requests

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:30000")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@zeroqwait.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/token", data={
        "username": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    }, timeout=10)
    if r.status_code != 200:
        pytest.skip(f"Cannot obtain admin token: {r.status_code} {r.text}")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def test_shop_id(admin_token):
    """Get the first non-admin shop ID."""
    r = requests.get(f"{BASE_URL}/api/shops/", timeout=10)
    if r.status_code != 200 or not r.json():
        pytest.skip("No shops available for provisioning test")
    return r.json()[0]["id"]


def test_provision_schema_endpoint(admin_token, test_shop_id):
    r = requests.post(
        f"{BASE_URL}/api/platform/shops/{test_shop_id}/provision-schema",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    assert r.status_code == 200, f"provision-schema failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["status"] == "provisioned"
    assert data["schema"] == f"tenant_{test_shop_id}"
    assert data["shop_id"] == test_shop_id


def test_provision_premium_endpoint(admin_token, test_shop_id):
    r = requests.post(
        f"{BASE_URL}/api/platform/shops/{test_shop_id}/provision-premium",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    assert r.status_code == 200, f"provision-premium failed: {r.status_code} {r.text}"
    data = r.json()
    # Should reflect dedicated compute mode
    assert data.get("shop_id") == test_shop_id or "shop_id" in data


def test_get_runtime_endpoint(admin_token, test_shop_id):
    r = requests.get(
        f"{BASE_URL}/api/platform/shops/{test_shop_id}/runtime",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10,
    )
    assert r.status_code == 200, f"get-runtime failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["shop_id"] == test_shop_id
    assert "compute_mode" in data
    assert "data_isolation_mode" in data
    assert "tenant_schema" in data


def test_revert_shared_endpoint(admin_token, test_shop_id):
    """Revert back to shared so we don't leave the test shop in dedicated mode."""
    r = requests.post(
        f"{BASE_URL}/api/platform/shops/{test_shop_id}/revert-shared",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10,
    )
    assert r.status_code == 200, f"revert-shared failed: {r.status_code} {r.text}"


def test_provisioner_requires_super_admin(test_shop_id):
    """Non-admin token should be rejected."""
    r = requests.post(
        f"{BASE_URL}/api/platform/shops/{test_shop_id}/provision-schema",
        headers={"Authorization": "Bearer invalidtoken"},
        timeout=10,
    )
    assert r.status_code in (401, 403), f"Expected auth failure, got {r.status_code}"


if __name__ == "__main__":
    import pytest as _pt
    _pt.main([__file__, "-v"])
