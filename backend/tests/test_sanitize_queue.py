"""
Unit tests for permissions.sanitize_queue_data_for_public().

This function sanitizes queue data returned to unauthenticated / non-staff
users by stripping employee assignment fields from queue items.

All DB access is mocked — no live database required.
"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")

from permissions import sanitize_queue_data_for_public


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_queue_data(*employee_ids):
    """Return a fake queue dict with queue_items that have assigned_employee fields."""
    items = []
    for i, emp_id in enumerate(employee_ids, start=1):
        items.append({
            "id": i,
            "customer_name": f"Customer {i}",
            "position": i,
            "assigned_employee": {"id": emp_id, "name": f"Employee {emp_id}"},
            "assigned_employee_id": emp_id,
        })
    return {"id": 1, "name": "Main Queue", "queue_items": items}


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSanitizeQueueDataForPublic:
    """Tests for sanitize_queue_data_for_public()."""

    # --- No-user path (public access) ----------------------------------------

    def test_no_user_removes_assigned_employee_key(self):
        data = _make_queue_data(10, 20)
        result = sanitize_queue_data_for_public(data, user=None, shop_id=None)
        for item in result["queue_items"]:
            assert "assigned_employee" not in item

    def test_no_user_nullifies_assigned_employee_id(self):
        data = _make_queue_data(10)
        result = sanitize_queue_data_for_public(data, user=None, shop_id=None)
        assert result["queue_items"][0]["assigned_employee_id"] is None

    def test_no_user_preserves_other_item_fields(self):
        data = _make_queue_data(10)
        result = sanitize_queue_data_for_public(data, user=None, shop_id=None)
        item = result["queue_items"][0]
        assert item["customer_name"] == "Customer 1"
        assert item["position"] == 1

    def test_no_user_no_mutation_of_original(self):
        """The original dict must not be modified."""
        data = _make_queue_data(5)
        original_item = data["queue_items"][0].copy()
        sanitize_queue_data_for_public(data, user=None, shop_id=None)
        assert data["queue_items"][0] == original_item

    def test_no_user_empty_items_list(self):
        data = {"id": 1, "queue_items": []}
        result = sanitize_queue_data_for_public(data, user=None, shop_id=None)
        assert result["queue_items"] == []

    def test_no_user_no_items_key(self):
        data = {"id": 1, "name": "Queue without items"}
        result = sanitize_queue_data_for_public(data, user=None, shop_id=None)
        assert "queue_items" not in result

    def test_no_user_multiple_items_all_sanitized(self):
        data = _make_queue_data(1, 2, 3)
        result = sanitize_queue_data_for_public(data, user=None, shop_id=None)
        for item in result["queue_items"]:
            assert item.get("assigned_employee_id") is None
            assert "assigned_employee" not in item

    # --- Staff / owner path (should see full data) ----------------------------

    def test_authenticated_staff_sees_full_data(self):
        """When check_shop_access does not raise, full data is returned unchanged."""
        data = _make_queue_data(10)
        user = {"id": 1, "role": "shop_owner"}
        with patch("permissions.check_shop_access", return_value=True):
            result = sanitize_queue_data_for_public(data, user=user, shop_id=1)
        # Full data — employee fields intact.
        assert result["queue_items"][0]["assigned_employee_id"] == 10
        assert "assigned_employee" in result["queue_items"][0]

    def test_authenticated_staff_same_object_returned(self):
        data = _make_queue_data(5)
        user = {"id": 1, "role": "shop_owner"}
        with patch("permissions.check_shop_access", return_value=True):
            result = sanitize_queue_data_for_public(data, user=user, shop_id=1)
        assert result is data

    def test_non_staff_with_user_but_access_denied(self):
        """User present but check_shop_access raises HTTPException → sanitize."""
        data = _make_queue_data(99)
        user = {"id": 99, "role": "customer"}
        with patch("permissions.check_shop_access", side_effect=HTTPException(status_code=403, detail="Forbidden")):
            result = sanitize_queue_data_for_public(data, user=user, shop_id=1)
        assert result["queue_items"][0].get("assigned_employee_id") is None

    def test_user_none_shop_id_none_both_falsy(self):
        """user=None and shop_id=None → is_staff=False → sanitize."""
        data = _make_queue_data(7)
        result = sanitize_queue_data_for_public(data, user=None, shop_id=None)
        assert result["queue_items"][0].get("assigned_employee_id") is None

    def test_returns_dict(self):
        data = _make_queue_data(1)
        result = sanitize_queue_data_for_public(data, user=None, shop_id=None)
        assert isinstance(result, dict)

    def test_top_level_fields_preserved(self):
        data = {"id": 42, "name": "Special Queue", "queue_items": []}
        result = sanitize_queue_data_for_public(data, user=None, shop_id=None)
        assert result["id"] == 42
        assert result["name"] == "Special Queue"

    def test_item_without_assigned_employee_unchanged(self):
        """Items that have no employee fields should be passed through as-is."""
        data = {
            "id": 1,
            "queue_items": [
                {"id": 10, "customer_name": "Alice", "position": 1},
            ],
        }
        result = sanitize_queue_data_for_public(data, user=None, shop_id=None)
        item = result["queue_items"][0]
        assert item["customer_name"] == "Alice"
        assert "assigned_employee" not in item
        assert item.get("assigned_employee_id") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
