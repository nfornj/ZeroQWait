from __future__ import annotations

from typing import Any, Dict

from database import SessionLocal
from modules.agent.models import PolicyMode
from modules.agent.work_repository import AgentWorkRepository


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
    return "Shop operations will change immediately after execution."


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
