"""HR specialist graph with explicit planner and executor nodes."""

import logging
from typing import Any, Dict, Optional, Sequence

from langchain_core.messages import BaseMessage

from .specialist_graph import build_specialist_runnable
from .tools import hr_tools

logger = logging.getLogger(__name__)

OPERATION_ALIASES = {
    "request_employee_details": "add_employee",
    "employee_details": "list_employees",
}

SUPPORTED_OPERATIONS = [
    "list_employees",
    "add_employee",
    "remove_employee",
    "get_shifts",
    "assign_shift",
    "clock_in_out",
]

PLANNER_INSTRUCTIONS = """\
- list_employees: list active employees unless include_inactive=true is explicitly requested.
- add_employee: use when the owner asks to add or hire someone; requires at least the employee name. This requires approval.
- remove_employee: use when the owner asks to remove or deactivate an employee and a user_id is known. This requires approval.
- get_shifts: use for shift schedules and staffing views; arguments: date(optional), user_id(optional).
- assign_shift: use when assigning a shift to a known employee id; requires user_id, start_time, end_time, and date. This requires approval.
- clock_in_out: use for clock-in or clock-out requests; arguments: user_id and action.
"""


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def _recent_conversation_text(messages: Sequence[BaseMessage]) -> str:
    recent_messages = list(messages or [])[-6:]
    parts = []
    for message in recent_messages:
        parts.append(_flatten_text(getattr(message, "content", None)))
        additional_kwargs = getattr(message, "additional_kwargs", None)
        if additional_kwargs:
            parts.append(_flatten_text(additional_kwargs))
    return " ".join(part for part in parts if part).strip()


def _normalize_hr_operation(operation: str, plan: Dict[str, Any], messages: Sequence[BaseMessage]) -> str:
    normalized_operation = str(operation or "").strip().lower()
    if normalized_operation in OPERATION_ALIASES:
        normalized_operation = OPERATION_ALIASES[normalized_operation]

    plan_text = _flatten_text(plan).lower()
    conversation_text = _recent_conversation_text(messages).lower()
    combined_text = f"{normalized_operation} {conversation_text} {plan_text}".strip()

    if normalized_operation in SUPPORTED_OPERATIONS:
        return normalized_operation

    if any(keyword in combined_text for keyword in ("add employee", "new employee", "hire", "onboard", "staff member")):
        return "add_employee"
    if any(keyword in combined_text for keyword in ("remove employee", "deactivate employee", "terminate employee", "fire employee")):
        return "remove_employee"
    if any(keyword in combined_text for keyword in ("assign shift", "schedule ", "put ", "roster")) and any(
        keyword in combined_text for keyword in ("shift", "schedule", "tomorrow", "today")
    ):
        return "assign_shift"
    if any(keyword in combined_text for keyword in ("clock in", "clock out", "punch in", "punch out")):
        return "clock_in_out"
    if any(keyword in combined_text for keyword in ("shift", "schedule", "who is on shift", "staffing")):
        return "get_shifts"
    return "list_employees"


def _looks_like_current_staffing_request(text: str) -> bool:
    normalized = str(text or "").lower()
    if not normalized:
        return False

    mentions_current_shift = any(
        phrase in normalized
        for phrase in (
            "who is on shift now",
            "who's on shift now",
            "on shift now",
            "on duty",
            "right now",
            "currently on shift",
            "current staffing",
        )
    )
    mentions_staffing_gap = "staffing gap" in normalized or "staffing gaps" in normalized
    mentions_shift_and_now = "shift" in normalized and any(token in normalized for token in ("now", "current", "right now"))
    return mentions_current_shift or mentions_staffing_gap or mentions_shift_and_now


def _build_hr_fast_plan(messages: Sequence[BaseMessage]) -> Optional[Dict[str, Any]]:
    conversation_text = _recent_conversation_text(messages)
    if _looks_like_current_staffing_request(conversation_text):
        return {
            "operation": "get_shifts",
            "arguments": {},
            "requires_clarification": False,
            "clarification_question": "",
            "rationale": "Selected get shifts for this HR request because the owner is asking who is on shift now and where staffing coverage is missing.",
        }
    return None


def _build_hr_executor(shop_id: int):
    def executor(operation: str, arguments: Dict[str, Any], messages: Sequence[BaseMessage]) -> Dict[str, Any]:
        if operation == "list_employees":
            return hr_tools.list_employees(shop_id, bool(arguments.get("include_inactive", False)))
        if operation == "add_employee":
            name = _optional_str(arguments.get("name"))
            if not name:
                return {"error": "add_employee requires name"}
            return {
                "requires_approval": True,
                "action": "add_employee",
                "details": {
                    "name": name,
                    "email": _optional_str(arguments.get("email")),
                    "phone": _optional_str(arguments.get("phone")),
                    "role": _optional_str(arguments.get("role")) or "employee",
                },
                "message": (
                    f"Adding employee '{name}' has been submitted for owner approval. "
                    "A staff email will be generated automatically if one was not provided."
                ),
            }
        if operation == "remove_employee":
            user_id = _to_int(arguments.get("user_id"))
            if user_id is None:
                return {"error": "remove_employee requires user_id"}
            return {
                "requires_approval": True,
                "action": "remove_employee",
                "details": {"user_id": user_id},
                "message": f"Removing employee (user_id={user_id}) has been submitted for owner approval.",
            }
        if operation == "get_shifts":
            if _looks_like_current_staffing_request(_recent_conversation_text(messages)):
                return hr_tools._local_current_staffing_status(shop_id)
            return hr_tools.get_shifts(shop_id, _optional_str(arguments.get("date")), _to_int(arguments.get("user_id")))
        if operation == "assign_shift":
            user_id = _to_int(arguments.get("user_id"))
            start_time = _optional_str(arguments.get("start_time"))
            end_time = _optional_str(arguments.get("end_time"))
            date = _optional_str(arguments.get("date"))
            if user_id is None or not start_time or not end_time or not date:
                return {"error": "assign_shift requires user_id, start_time, end_time, and date"}
            return {
                "requires_approval": True,
                "action": "assign_shift",
                "details": {
                    "user_id": user_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "date": date,
                },
                "message": (
                    f"Assigning a shift for employee {user_id} on {date} from {start_time} to {end_time} "
                    "has been submitted for owner approval."
                ),
            }
        if operation == "clock_in_out":
            user_id = _to_int(arguments.get("user_id"))
            action = _optional_str(arguments.get("action"))
            if user_id is None or not action:
                return {"error": "clock_in_out requires user_id and action"}
            return hr_tools.clock_in_out(shop_id, user_id, action)
        return {"error": f"Unsupported HR operation: {operation}"}

    return executor


def _format_hr_response(operation: str, result: Dict[str, Any]) -> str:
    if result.get("error"):
        return f"I couldn't complete that HR task: {result['error']}"
    if operation == "list_employees":
        employees = list(result.get("employees") or [])
        if not employees:
            return "There are no active employees on file right now."
        lines = []
        for employee in employees[:10]:
            lines.append(f"- #{employee.get('id')}: {employee.get('name')} — {employee.get('role', 'employee')}")
        return f"I found {len(employees)} employee(s):\n" + "\n".join(lines)
    if operation == "get_shifts":
        if result.get("current_staffing"):
            on_shift = list(result.get("on_shift") or [])
            if not on_shift:
                return "No one is clocked in right now."

            lines = []
            for shift in on_shift[:10]:
                lines.append(f"- {shift.get('name')} since {shift.get('clock_in')}")

            queue_length = int(result.get("queue_length", 0) or 0)
            wait_minutes = int(result.get("estimated_wait_minutes", 0) or 0)
            staffing_gap_count = int(result.get("staffing_gap_count", 0) or 0)
            coverage_line = (
                f"Coverage is short by {staffing_gap_count} team member{'s' if staffing_gap_count != 1 else ''} "
                f"for the current queue."
                if staffing_gap_count > 0
                else "Current staffing covers the present queue load."
            )
            roster_mismatch_count = int(result.get("roster_mismatch_count", 0) or 0)
            mismatch_line = (
                f" I also found {roster_mismatch_count} active shift"
                f"{'s' if roster_mismatch_count != 1 else ''} not reflected in the active employee roster."
                if roster_mismatch_count > 0
                else ""
            )
            return (
                f"{len(on_shift)} team member{'s are' if len(on_shift) != 1 else ' is'} on shift right now.\n"
                + "\n".join(lines)
                + f"\nQueue load: {queue_length} in queue, about {wait_minutes} minutes estimated wait. "
                + coverage_line
                + mismatch_line
            )
        shifts = list(result.get("shifts") or [])
        if not shifts:
            return "No shifts matched that request."
        lines = []
        for shift in shifts[:10]:
            lines.append(
                f"- {shift.get('name') or f'Employee {shift.get('user_id')}'} on {shift.get('date')}: {shift.get('start_time')} to {shift.get('end_time')}"
            )
        return f"I found {len(shifts)} shift(s):\n" + "\n".join(lines)
    if result.get("message"):
        return str(result["message"])
    return f"The HR specialist completed {operation.replace('_', ' ')}."

def create_hr_runnable(shop_id: int | None = None):
    if not shop_id:
        raise ValueError("shop_id is required — cannot build the HR graph without it")

    return build_specialist_runnable(
        agent_name="hr",
        shop_id=shop_id,
        temperature=0.2,
        planner_instructions=PLANNER_INSTRUCTIONS,
        supported_operations=SUPPORTED_OPERATIONS,
        operation_aliases=OPERATION_ALIASES,
        operation_normalizer=_normalize_hr_operation,
        fast_plan_builder=_build_hr_fast_plan,
        executor=_build_hr_executor(shop_id),
        formatter=_format_hr_response,
    )


    __all__ = ["create_hr_runnable"]
