from __future__ import annotations

from typing import Any, Dict

from database import SessionLocal
from modules.agent.models import PolicyMode
from modules.agent.work_repository import AgentWorkRepository


SUPPORTED_POLICY_MODES = tuple(mode.value for mode in PolicyMode)


_ACTION_CATALOG: Dict[str, Dict[str, str]] = {
    "close_queue": {
        "policy_key": "approval.close_queue",
        "category": "operations",
        "title": "Close Active Queue",
        "risk_level": "high",
        "urgency": "high",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "add_employee": {
        "policy_key": "approval.add_employee",
        "category": "staffing",
        "title": "Add Team Member",
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "remove_employee": {
        "policy_key": "approval.remove_employee",
        "category": "staffing",
        "title": "Deactivate Team Member",
        "risk_level": "high",
        "urgency": "high",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "assign_shift": {
        "policy_key": "approval.assign_shift",
        "category": "staffing",
        "title": "Assign Employee Shift",
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "create_invoice": {
        "policy_key": "approval.create_invoice",
        "category": "finance",
        "title": "Create Invoice",
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "record_payment": {
        "policy_key": "approval.record_payment",
        "category": "finance",
        "title": "Record Payment",
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "process_refund": {
        "policy_key": "approval.process_refund",
        "category": "finance",
        "title": "Process Refund",
        "risk_level": "high",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
}


def _action_defaults(action: str) -> Dict[str, str]:
    fallback_title = action.replace("_", " ").title() if action else "Approval Required"
    return {
        "policy_key": f"approval.{action or 'action'}",
        "category": "operations",
        "title": fallback_title,
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    }


def _summary_for_action(action: str, details: Dict[str, Any]) -> str:
    if action == "close_queue":
        return "Pause new customers from joining the queue for this shop."
    if action == "add_employee":
        employee_name = str(details.get("name") or "this employee")
        return f"Add {employee_name} to the shop team."
    if action == "remove_employee":
        employee_id = details.get("user_id")
        return f"Remove employee access for user ID {employee_id}."
    if action == "assign_shift":
        employee_id = details.get("user_id")
        date = details.get("date") or "the selected day"
        return f"Assign employee {employee_id} to a shift on {date}."
    if action == "create_invoice":
        service_name = str(details.get("service_name") or "the requested service")
        return f"Create an invoice for {service_name}."
    if action == "record_payment":
        amount = details.get("amount")
        return f"Record a payment of ${float(amount or 0.0):.2f}."
    if action == "process_refund":
        payment_id = details.get("payment_id")
        refund_amount = details.get("refund_amount")
        if refund_amount in (None, ""):
            return f"Refund payment {payment_id}."
        return f"Refund ${float(refund_amount or 0.0):.2f} for payment {payment_id}."
    return "A business action needs a policy decision before the agent can continue."


def _rationale_for_action(action: str, details: Dict[str, Any]) -> str:
    if action == "close_queue":
        return str(details.get("reason") or "The agent wants to pause new queue intake.")
    if action == "add_employee":
        employee_name = str(details.get("name") or "this employee")
        return f"Create a new employee record for {employee_name}."
    if action == "remove_employee":
        employee_id = details.get("user_id")
        return f"Remove employee access for user ID {employee_id}."
    if action == "assign_shift":
        employee_id = details.get("user_id")
        start_time = details.get("start_time") or "start time"
        end_time = details.get("end_time") or "end time"
        return f"Create a shift from {start_time} to {end_time} for employee {employee_id}."
    if action == "create_invoice":
        service_name = str(details.get("service_name") or "the requested service")
        unit_price = float(details.get("unit_price") or 0.0)
        quantity = int(details.get("quantity") or 1)
        return f"Create an invoice for {service_name} at ${unit_price:.2f} x {quantity}."
    if action == "record_payment":
        amount = float(details.get("amount") or 0.0)
        method = str(details.get("method") or "cash")
        return f"Record a {method} payment of ${amount:.2f}."
    if action == "process_refund":
        payment_id = details.get("payment_id")
        refund_amount = details.get("refund_amount")
        reason = str(details.get("reason") or "No explicit reason was provided.")
        if refund_amount in (None, ""):
            return f"Refund payment {payment_id}. Reason: {reason}"
        return f"Refund ${float(refund_amount or 0.0):.2f} for payment {payment_id}. Reason: {reason}"
    return "The agent flagged this change as operationally significant."


def _impact_for_action(action: str, details: Dict[str, Any]) -> str:
    if action == "close_queue":
        return "New walk-ins will stop joining until the queue is reopened."
    if action == "add_employee":
        return "The team roster will change and the employee can be scheduled immediately."
    if action == "remove_employee":
        return "The employee will no longer appear as active for staffing and scheduling workflows."
    if action == "assign_shift":
        return "The staffing schedule will change immediately after execution."
    if action == "create_invoice":
        return "A new financial record will be created and become available for payment tracking."
    if action == "record_payment":
        return "The invoice and payment ledger will update immediately after execution."
    if action == "process_refund":
        return "The payment ledger will be adjusted immediately and the refund cannot be silently ignored by staff or customers."
    return "Shop operations will change immediately after execution."


def get_policy_definition(policy_key: str) -> Dict[str, Any] | None:
    normalized = str(policy_key or "").strip()
    if not normalized:
        return None
    for action, config in sorted(_ACTION_CATALOG.items()):
        if config["policy_key"] != normalized:
            continue
        return {
            "action": action,
            "policy_key": config["policy_key"],
            "category": config["category"],
            "title": config["title"],
            "risk_level": config["risk_level"],
            "urgency": config["urgency"],
            "default_mode": config["default_mode"],
            "supported_modes": list(SUPPORTED_POLICY_MODES),
        }
    return None


def list_policy_definitions() -> list[Dict[str, Any]]:
    definitions: list[Dict[str, Any]] = []
    for action, config in sorted(_ACTION_CATALOG.items(), key=lambda item: (item[1]["category"], item[1]["policy_key"])):
        definitions.append(
            {
                "action": action,
                "policy_key": config["policy_key"],
                "category": config["category"],
                "title": config["title"],
                "risk_level": config["risk_level"],
                "urgency": config["urgency"],
                "default_mode": config["default_mode"],
                "supported_modes": list(SUPPORTED_POLICY_MODES),
            }
        )
    return definitions


def list_shop_policies(shop_id: int) -> list[Dict[str, Any]]:
    if shop_id <= 0:
        return []

    stored_modes: Dict[str, str] = {}
    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        for policy in repo.get_shop_policies(shop_id):
            policy_key = str(getattr(policy, "policy_key", "") or "").strip()
            if not policy_key:
                continue
            resolved_mode = getattr(policy, "mode", None)
            stored_modes[policy_key] = resolved_mode.value if hasattr(resolved_mode, "value") else str(resolved_mode)
    finally:
        db.close()

    payload: list[Dict[str, Any]] = []
    for item in list_policy_definitions():
        payload.append(
            {
                **item,
                "mode": stored_modes.get(item["policy_key"], item["default_mode"]),
                "explicit": item["policy_key"] in stored_modes,
            }
        )
    return payload


def resolve_action_policy(shop_id: int, action: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    normalized_action = str(action or "approval_required").strip() or "approval_required"
    detail_payload = dict(details or {})
    catalog = {**_action_defaults(normalized_action), **_ACTION_CATALOG.get(normalized_action, {})}
    policy_mode = catalog["default_mode"]

    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        for policy in repo.get_shop_policies(shop_id):
            if getattr(policy, "policy_key", None) != catalog["policy_key"]:
                continue
            resolved_mode = getattr(policy, "mode", policy_mode)
            policy_mode = resolved_mode.value if hasattr(resolved_mode, "value") else str(resolved_mode)
            break
    finally:
        db.close()

    return {
        "action": normalized_action,
        "policy_key": catalog["policy_key"],
        "policy_mode": policy_mode,
        "category": catalog["category"],
        "title": catalog["title"],
        "risk_level": catalog["risk_level"],
        "urgency": catalog["urgency"],
        "summary": _summary_for_action(normalized_action, detail_payload),
        "rationale": _rationale_for_action(normalized_action, detail_payload),
        "expected_impact": _impact_for_action(normalized_action, detail_payload),
    }


def build_pending_approval(shop_id: int, action: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    pending_details = dict(details or {})
    policy = resolve_action_policy(shop_id, action, pending_details)
    return {
        "action": policy["action"],
        "details": pending_details,
        "shop_id": shop_id,
        "policy_key": policy["policy_key"],
        "policy_mode": policy["policy_mode"],
        "category": policy["category"],
        "title": policy["title"],
        "risk_level": policy["risk_level"],
        "urgency": policy["urgency"],
        "summary": policy["summary"],
        "rationale": policy["rationale"],
        "expected_impact": policy["expected_impact"],
    }
