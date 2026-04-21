"""HR specialist graph with explicit planner and executor nodes."""

import logging
from typing import Any, Dict, Optional, Sequence

from langchain_core.messages import BaseMessage

from .specialist_graph import build_specialist_runnable
from .tools import hr_tools

logger = logging.getLogger(__name__)

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
        executor=_build_hr_executor(shop_id),
        formatter=_format_hr_response,
    )


__all__ = ["create_hr_runnable"]
