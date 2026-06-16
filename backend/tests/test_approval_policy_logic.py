"""
Unit tests for the pure-logic portions of agents/approval_policy.py.

Covers the text-generation helpers (_summary_for_action, _rationale_for_action,
_impact_for_action), the catalog utilities (_action_defaults, get_policy_definition,
list_policy_definitions), and the SUPPORTED_POLICY_MODES constant.

All DB-touching functions (list_shop_policies, resolve_action_policy,
build_pending_approval) are covered in test_approval_actions.py.
No live database is required for these tests.
"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")

from agents.approval_policy import (
    _summary_for_action,
    _rationale_for_action,
    _impact_for_action,
    _action_defaults,
    get_policy_definition,
    list_policy_definitions,
    SUPPORTED_POLICY_MODES,
    _ACTION_CATALOG,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

ALL_CATALOG_ACTIONS = list(_ACTION_CATALOG.keys())


# ── SUPPORTED_POLICY_MODES ────────────────────────────────────────────────────

class TestSupportedPolicyModes:
    def test_is_non_empty_tuple(self):
        assert isinstance(SUPPORTED_POLICY_MODES, tuple)
        assert len(SUPPORTED_POLICY_MODES) > 0

    def test_contains_require_approval(self):
        assert "require_approval" in SUPPORTED_POLICY_MODES

    def test_contains_allow(self):
        assert "allow" in SUPPORTED_POLICY_MODES

    def test_contains_forbid(self):
        assert "forbid" in SUPPORTED_POLICY_MODES


# ── _action_defaults ──────────────────────────────────────────────────────────

class TestActionDefaults:
    def test_returns_dict(self):
        result = _action_defaults("some_action")
        assert isinstance(result, dict)

    def test_required_keys_present(self):
        result = _action_defaults("close_queue")
        for key in ("policy_key", "category", "title", "risk_level", "urgency", "default_mode"):
            assert key in result, f"Missing key: {key}"

    def test_policy_key_includes_action(self):
        result = _action_defaults("my_action")
        assert "my_action" in result["policy_key"]

    def test_title_derived_from_action(self):
        result = _action_defaults("close_queue")
        assert "Close" in result["title"] or "close" in result["title"].lower()

    def test_empty_action_uses_placeholder(self):
        result = _action_defaults("")
        assert result["policy_key"] == "approval.action"

    def test_none_action_uses_placeholder(self):
        result = _action_defaults(None)
        assert result["policy_key"] == "approval.action"

    def test_default_mode_is_require_approval(self):
        result = _action_defaults("new_action")
        assert result["default_mode"] == "require_approval"


# ── _summary_for_action ───────────────────────────────────────────────────────

class TestSummaryForAction:
    def test_close_queue_summary(self):
        result = _summary_for_action("close_queue", {})
        assert "queue" in result.lower()
        assert "join" in result.lower() or "stop" in result.lower() or "pause" in result.lower()

    def test_add_employee_summary_includes_name(self):
        result = _summary_for_action("add_employee", {"name": "Alice"})
        assert "Alice" in result

    def test_add_employee_summary_no_name(self):
        result = _summary_for_action("add_employee", {})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_remove_employee_summary_includes_user_id(self):
        result = _summary_for_action("remove_employee", {"user_id": 42})
        assert "42" in result

    def test_assign_shift_summary_includes_employee_and_date(self):
        result = _summary_for_action("assign_shift", {"user_id": 7, "date": "2026-05-01"})
        assert "7" in result
        assert "2026-05-01" in result

    def test_create_invoice_summary_includes_service_name(self):
        result = _summary_for_action("create_invoice", {"service_name": "Haircut"})
        assert "Haircut" in result

    def test_record_payment_summary_shows_amount(self):
        result = _summary_for_action("record_payment", {"amount": 35.50})
        assert "35.50" in result

    def test_process_refund_summary_with_amount(self):
        result = _summary_for_action("process_refund", {"payment_id": 99, "refund_amount": 12.0})
        assert "12.00" in result

    def test_process_refund_summary_without_amount(self):
        result = _summary_for_action("process_refund", {"payment_id": 99})
        assert "99" in result

    def test_unknown_action_returns_generic_string(self):
        result = _summary_for_action("unknown_action", {})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_all_catalog_actions_return_strings(self):
        for action in ALL_CATALOG_ACTIONS:
            result = _summary_for_action(action, {})
            assert isinstance(result, str), f"Summary not a string for action '{action}'"
            assert len(result) > 0, f"Empty summary for action '{action}'"


# ── _rationale_for_action ─────────────────────────────────────────────────────

class TestRationaleForAction:
    def test_close_queue_rationale_uses_reason(self):
        result = _rationale_for_action("close_queue", {"reason": "End of day"})
        assert "End of day" in result

    def test_close_queue_rationale_default_when_no_reason(self):
        result = _rationale_for_action("close_queue", {})
        assert "queue" in result.lower() or "intake" in result.lower()

    def test_add_employee_rationale_includes_name(self):
        result = _rationale_for_action("add_employee", {"name": "Bob"})
        assert "Bob" in result

    def test_remove_employee_rationale_includes_user_id(self):
        result = _rationale_for_action("remove_employee", {"user_id": 55})
        assert "55" in result

    def test_assign_shift_rationale_includes_times(self):
        result = _rationale_for_action("assign_shift", {
            "user_id": 3, "start_time": "09:00", "end_time": "17:00"
        })
        assert "09:00" in result
        assert "17:00" in result

    def test_create_invoice_rationale_includes_price_and_quantity(self):
        result = _rationale_for_action("create_invoice", {
            "service_name": "Beard Trim", "unit_price": 20.0, "quantity": 1
        })
        assert "20.00" in result
        assert "Beard Trim" in result

    def test_record_payment_rationale_includes_method_and_amount(self):
        result = _rationale_for_action("record_payment", {"amount": 50.0, "method": "card"})
        assert "card" in result
        assert "50.00" in result

    def test_process_refund_rationale_includes_reason(self):
        result = _rationale_for_action("process_refund", {
            "payment_id": 10, "refund_amount": 5.0, "reason": "Overcharge"
        })
        assert "Overcharge" in result

    def test_process_refund_rationale_without_amount(self):
        result = _rationale_for_action("process_refund", {"payment_id": 10})
        assert "10" in result

    def test_unknown_action_returns_generic_string(self):
        result = _rationale_for_action("mystery_action", {})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_all_catalog_actions_return_strings(self):
        for action in ALL_CATALOG_ACTIONS:
            result = _rationale_for_action(action, {})
            assert isinstance(result, str)
            assert len(result) > 0


# ── _impact_for_action ────────────────────────────────────────────────────────

class TestImpactForAction:
    def test_close_queue_mentions_walk_ins(self):
        result = _impact_for_action("close_queue", {})
        assert "walk-in" in result.lower() or "join" in result.lower()

    def test_add_employee_mentions_roster(self):
        result = _impact_for_action("add_employee", {})
        assert "roster" in result.lower() or "team" in result.lower()

    def test_remove_employee_mentions_active(self):
        result = _impact_for_action("remove_employee", {})
        assert "active" in result.lower() or "employee" in result.lower()

    def test_assign_shift_mentions_schedule(self):
        result = _impact_for_action("assign_shift", {})
        assert "schedule" in result.lower() or "staffing" in result.lower()

    def test_create_invoice_mentions_financial_record(self):
        result = _impact_for_action("create_invoice", {})
        assert "financial" in result.lower() or "invoice" in result.lower() or "record" in result.lower()

    def test_record_payment_mentions_ledger(self):
        result = _impact_for_action("record_payment", {})
        assert "ledger" in result.lower() or "payment" in result.lower() or "invoice" in result.lower()

    def test_process_refund_mentions_ledger_and_refund(self):
        result = _impact_for_action("process_refund", {})
        assert "ledger" in result.lower() or "refund" in result.lower()

    def test_unknown_action_returns_generic(self):
        result = _impact_for_action("dragon_mode", {})
        assert "operation" in result.lower() or "change" in result.lower()

    def test_all_catalog_actions_return_strings(self):
        for action in ALL_CATALOG_ACTIONS:
            result = _impact_for_action(action, {})
            assert isinstance(result, str)
            assert len(result) > 0


# ── get_policy_definition ─────────────────────────────────────────────────────

class TestGetPolicyDefinition:
    def test_known_key_returns_dict(self):
        result = get_policy_definition("approval.close_queue")
        assert result is not None
        assert isinstance(result, dict)

    def test_known_key_action_field(self):
        result = get_policy_definition("approval.close_queue")
        assert result["action"] == "close_queue"

    def test_known_key_policy_key_field(self):
        result = get_policy_definition("approval.add_employee")
        assert result["policy_key"] == "approval.add_employee"

    def test_known_key_has_supported_modes(self):
        result = get_policy_definition("approval.process_refund")
        assert "supported_modes" in result
        assert isinstance(result["supported_modes"], list)

    def test_supported_modes_match_constant(self):
        result = get_policy_definition("approval.close_queue")
        assert set(result["supported_modes"]) == set(SUPPORTED_POLICY_MODES)

    def test_unknown_key_returns_none(self):
        result = get_policy_definition("approval.nonexistent_action")
        assert result is None

    def test_empty_key_returns_none(self):
        assert get_policy_definition("") is None

    def test_none_key_returns_none(self):
        assert get_policy_definition(None) is None

    def test_all_catalog_keys_are_resolvable(self):
        for action, config in _ACTION_CATALOG.items():
            result = get_policy_definition(config["policy_key"])
            assert result is not None, f"Could not resolve policy_key for action '{action}'"
            assert result["action"] == action


# ── list_policy_definitions ───────────────────────────────────────────────────

class TestListPolicyDefinitions:
    def test_returns_list(self):
        result = list_policy_definitions()
        assert isinstance(result, list)

    def test_length_matches_catalog(self):
        result = list_policy_definitions()
        assert len(result) == len(_ACTION_CATALOG)

    def test_each_item_has_required_keys(self):
        required = {
            "action", "policy_key", "category", "title",
            "risk_level", "urgency", "default_mode", "supported_modes",
        }
        for item in list_policy_definitions():
            assert required.issubset(item.keys()), f"Missing keys in {item}"

    def test_all_supported_modes_populated(self):
        for item in list_policy_definitions():
            assert set(item["supported_modes"]) == set(SUPPORTED_POLICY_MODES)

    def test_sorted_by_category_then_policy_key(self):
        definitions = list_policy_definitions()
        sort_keys = [(d["category"], d["policy_key"]) for d in definitions]
        assert sort_keys == sorted(sort_keys)

    def test_no_duplicate_policy_keys(self):
        definitions = list_policy_definitions()
        keys = [d["policy_key"] for d in definitions]
        assert len(keys) == len(set(keys))

    def test_known_actions_present(self):
        definitions = list_policy_definitions()
        actions = {d["action"] for d in definitions}
        for action in ALL_CATALOG_ACTIONS:
            assert action in actions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
