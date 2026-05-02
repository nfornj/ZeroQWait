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
    "leave_request",
]

PLANNER_INSTRUCTIONS = """\
- list_employees: list active employees unless include_inactive=true is explicitly requested.
- add_employee: use when the owner asks to add or hire someone; requires at least the employee name. This requires approval.
- remove_employee: use when the owner asks to remove or deactivate an employee and a user_id is known. This requires approval.
- get_shifts: use for shift schedules and staffing views; arguments: date(optional), user_id(optional).
- assign_shift: use when assigning a shift to a known employee id; requires user_id, start_time, end_time, and date. This requires approval.
- clock_in_out: use for clock-in or clock-out requests; arguments: user_id and action.
- leave_request: use when an employee asks for time off, sick leave, annual leave, personal day, or vacation; OR when the owner is notified that an employee wants leave. Requires approval. Arguments: employee_name, leave_date (YYYY-MM-DD or descriptive), reason (optional), leave_type (sick/annual/personal/other).
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
    if any(keyword in combined_text for keyword in (
        "leave", "day off", "time off", "sick", "vacation", "annual leave",
        "personal day", "absent", "not coming in", "take friday", "take monday",
        "request off", "requesting leave", "can i take",
    )):
        return "leave_request"
    return "list_employees"


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
        if operation == "leave_request":
            employee_name = _optional_str(arguments.get("employee_name") or arguments.get("name"))
            leave_date = _optional_str(
                arguments.get("leave_date") or arguments.get("date") or arguments.get("start_date")
            )
            reason = _optional_str(arguments.get("reason")) or "No reason provided"
            leave_type = _optional_str(arguments.get("leave_type")) or "leave"
            if not employee_name:
                return {"error": "leave_request requires employee_name"}
            if not leave_date:
                return {"error": "leave_request requires leave_date"}
            return {
                "requires_approval": True,
                "action": "leave_request",
                "details": {
                    "employee_name": employee_name,
                    "leave_date": leave_date,
                    "leave_type": leave_type,
                    "reason": reason,
                },
                "message": (
                    f"{employee_name}'s {leave_type} request for {leave_date} has been forwarded to you for approval. "
                    "Please approve or deny this request in your Agent Inbox."
                ),
            }
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
        shifts = list(result.get("shifts") or [])
        if not shifts:
            return "No shifts matched that request."
        lines = []
        for shift in shifts[:10]:
            lines.append(
                f"- Employee {shift.get('user_id')} on {shift.get('date')}: {shift.get('start_time')} to {shift.get('end_time')}"
            )
        return f"I found {len(shifts)} shift(s):\n" + "\n".join(lines)
    if result.get("message"):
        return str(result["message"])
    if operation == "leave_request":
        return "The leave request has been forwarded for your approval — check the Agent Inbox."
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
        executor=_build_hr_executor(shop_id),
        formatter=_format_hr_response,
    )


    __all__ = ["create_hr_runnable"]
