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
    "hire": "hire_employee",
    "onboard": "hire_employee",
    "pay_rate": "update_pay_rate",
    "tip": "log_tip",
    "tips": "get_tips_summary",
    "payroll": "run_payroll",
    "t4": "generate_t4",
    "remittance": "get_remittance_summary",
}

SUPPORTED_OPERATIONS = [
    "list_employees",
    "add_employee",
    "remove_employee",
    "get_shifts",
    "assign_shift",
    "clock_in_out",
    "leave_request",
    # ── Payroll & hiring ──────────────────────────────────────────────────────
    "hire_employee",
    "get_payroll_profile",
    "update_pay_rate",
    "log_tip",
    "get_tips_summary",
    "run_payroll",
    "split_tips",
    "generate_t4",
    "get_remittance_summary",
]

PLANNER_INSTRUCTIONS = """\
- list_employees: list active employees unless include_inactive=true is explicitly requested.
- add_employee: use when the owner asks to add or hire someone; requires at least the employee name. This requires approval.
- remove_employee: use when the owner asks to remove or deactivate an employee and a user_id is known. This requires approval.
- get_shifts: use for shift schedules and staffing views; arguments: date(optional), user_id(optional).
- assign_shift: use when assigning a shift to a known employee id; requires user_id, start_time, end_time, and date. This requires approval.
- clock_in_out: use for clock-in or clock-out requests; arguments: user_id and action.
- leave_request: use when an employee asks for time off, sick leave, annual leave, personal day, or vacation; OR when the owner is notified that an employee wants leave. Requires approval. Arguments: employee_name, leave_date (YYYY-MM-DD or descriptive), reason (optional), leave_type (sick/annual/personal/other).
- hire_employee: use when the owner wants to hire someone WITH payroll setup (pay rate, province, etc.). Requires approval. Arguments: name (required), pay_type (hourly|salary), hourly_rate or annual_salary, pay_frequency (biweekly|weekly|semi-monthly|monthly), province (2-letter, default ON), email, phone, sin (optional, encrypted).
- get_payroll_profile: retrieve payroll details for a named employee. Arguments: employee_name.
- update_pay_rate: change an employee's hourly rate or annual salary. Requires approval. Arguments: employee_name, field (hourly_rate|annual_salary), new_rate.
- log_tip: record a tip for an employee. Arguments: employee_name, amount, tip_type (cash|card|pooled), source (optional), tip_date (optional YYYY-MM-DD).
- get_tips_summary: summarize tips for an employee or the shop. Arguments: employee_name (optional), since (optional YYYY-MM-DD).
- run_payroll: draft payslips for all active employees for a pay period. Requires approval. Arguments: period_start, period_end, pay_date (optional), regular_hours (default 80), overtime_hours (optional), tips_amount (optional).
- split_tips: create and split a tip pool among staff. Requires approval. Arguments: total_amount, pool_date (optional), employee_splits: list of {employee_name, hours_worked}.
- generate_t4: generate year-end T4 slips for all employees. Requires approval. Arguments: tax_year.
- get_remittance_summary: show pending CRA remittances. No required arguments.
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
    # Payroll-related fallbacks
    if any(keyword in combined_text for keyword in ("hire employee", "onboard employee", "pay rate", "pay type", "payroll setup", "sin number")):
        return "hire_employee"
    if any(keyword in combined_text for keyword in ("payroll profile", "pay info", "pay details")):
        return "get_payroll_profile"
    if any(keyword in combined_text for keyword in ("update pay", "change pay", "new rate", "raise", "increase pay")):
        return "update_pay_rate"
    if any(keyword in combined_text for keyword in ("log tip", "record tip", "add tip")):
        return "log_tip"
    if any(keyword in combined_text for keyword in ("tips summary", "tip summary", "how much tips", "tips today", "tips this week")):
        return "get_tips_summary"
    if any(keyword in combined_text for keyword in ("run payroll", "calculate payroll", "draft payslip", "payroll run")):
        return "run_payroll"
    if any(keyword in combined_text for keyword in ("split tips", "tip pool", "distribute tips")):
        return "split_tips"
    if any(keyword in combined_text for keyword in ("generate t4", "t4 slip", "t4 record", "year end", "yearend")):
        return "generate_t4"
    if any(keyword in combined_text for keyword in ("remittance", "cra payment", "source deduction")):
        return "get_remittance_summary"
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

        # ── Payroll & hiring ──────────────────────────────────────────────────
        if operation == "hire_employee":
            name = _optional_str(arguments.get("name"))
            if not name:
                return {"error": "hire_employee requires name"}
            pay_type = _optional_str(arguments.get("pay_type")) or "hourly"
            hourly_rate = arguments.get("hourly_rate")
            annual_salary = arguments.get("annual_salary")
            pay_frequency = _optional_str(arguments.get("pay_frequency")) or "biweekly"
            province = _optional_str(arguments.get("province")) or "ON"
            if pay_type == "hourly" and not hourly_rate:
                return {"error": "hire_employee requires hourly_rate for pay_type=hourly"}
            if pay_type == "salary" and not annual_salary:
                return {"error": "hire_employee requires annual_salary for pay_type=salary"}
            rate_str = (
                f"${float(hourly_rate):.2f}/hr" if hourly_rate else f"${float(annual_salary):,.2f}/yr"
            )
            return {
                "requires_approval": True,
                "action": "onboard_employee",
                "details": {
                    "name": name,
                    "pay_type": pay_type,
                    "hourly_rate": hourly_rate,
                    "annual_salary": annual_salary,
                    "pay_frequency": pay_frequency,
                    "province": province,
                    "email": _optional_str(arguments.get("email")),
                    "phone": _optional_str(arguments.get("phone")),
                    "role": _optional_str(arguments.get("role")) or "employee",
                    "sin": _optional_str(arguments.get("sin")),
                },
                "message": (
                    f"Onboarding '{name}' ({pay_type}, {rate_str}, {pay_frequency}, {province}) "
                    "has been submitted for your approval."
                ),
            }

        if operation == "get_payroll_profile":
            employee_name = _optional_str(arguments.get("employee_name") or arguments.get("name"))
            if not employee_name:
                return {"error": "get_payroll_profile requires employee_name"}
            return hr_tools.get_employee_payroll_profile(shop_id, employee_name)

        if operation == "update_pay_rate":
            employee_name = _optional_str(arguments.get("employee_name") or arguments.get("name"))
            field = _optional_str(arguments.get("field")) or "hourly_rate"
            new_rate = arguments.get("new_rate") or arguments.get("hourly_rate") or arguments.get("annual_salary")
            if not employee_name:
                return {"error": "update_pay_rate requires employee_name"}
            if new_rate is None:
                return {"error": "update_pay_rate requires new_rate (or hourly_rate/annual_salary)"}
            return {
                "requires_approval": True,
                "action": "update_pay_rate",
                "details": {
                    "employee_name": employee_name,
                    "field": field,
                    "new_rate": new_rate,
                },
                "message": (
                    f"Updating {employee_name}'s {field.replace('_', ' ')} to {new_rate} "
                    "has been submitted for your approval."
                ),
            }

        if operation == "log_tip":
            from agents.tools.payroll_tools import log_tip
            employee_name = _optional_str(arguments.get("employee_name") or arguments.get("name"))
            amount = arguments.get("amount")
            tip_type = _optional_str(arguments.get("tip_type")) or "cash"
            source = _optional_str(arguments.get("source"))
            tip_date = _optional_str(arguments.get("tip_date"))
            if not employee_name:
                return {"error": "log_tip requires employee_name"}
            if amount is None:
                return {"error": "log_tip requires amount"}
            return log_tip(
                shop_id=shop_id,
                employee_name=employee_name,
                amount=float(amount),
                tip_type=tip_type,
                source=source,
                tip_date=tip_date,
            )

        if operation == "get_tips_summary":
            from agents.tools.payroll_tools import get_tips_summary
            employee_name = _optional_str(arguments.get("employee_name") or arguments.get("name"))
            since = _optional_str(arguments.get("since"))
            return get_tips_summary(shop_id, employee_name=employee_name, since=since)

        if operation == "run_payroll":
            period_start = _optional_str(arguments.get("period_start"))
            period_end = _optional_str(arguments.get("period_end"))
            if not period_start or not period_end:
                return {"error": "run_payroll requires period_start and period_end (YYYY-MM-DD)"}
            pay_date = _optional_str(arguments.get("pay_date")) or period_end
            regular_hours = float(arguments.get("regular_hours") or 80.0)
            overtime_hours = float(arguments.get("overtime_hours") or 0.0)
            tips_amount = float(arguments.get("tips_amount") or 0.0)
            return {
                "requires_approval": True,
                "action": "run_payroll",
                "details": {
                    "period_start": period_start,
                    "period_end": period_end,
                    "pay_date": pay_date,
                    "regular_hours": regular_hours,
                    "overtime_hours": overtime_hours,
                    "tips_amount": tips_amount,
                },
                "message": (
                    f"Payroll run for {period_start} → {period_end} (pay date {pay_date}) "
                    "has been submitted for your approval. "
                    "Draft payslips will be calculated after you confirm."
                ),
            }

        if operation == "split_tips":
            total_amount = arguments.get("total_amount")
            pool_date = _optional_str(arguments.get("pool_date"))
            employee_splits = arguments.get("employee_splits") or []
            if total_amount is None:
                return {"error": "split_tips requires total_amount"}
            return {
                "requires_approval": True,
                "action": "split_tips",
                "details": {
                    "total_amount": float(total_amount),
                    "pool_date": pool_date,
                    "employee_splits": employee_splits,
                },
                "message": (
                    f"Splitting ${float(total_amount):.2f} tip pool among {len(employee_splits)} staff "
                    "has been submitted for your approval."
                ),
            }

        if operation == "generate_t4":
            from agents.tools.payroll_tools import list_t4_records, draft_t4
            from modules.employees.models import ShopEmployee
            from database import SessionLocal
            tax_year = _to_int(arguments.get("tax_year"))
            if not tax_year:
                return {"error": "generate_t4 requires tax_year (e.g. 2025)"}
            return {
                "requires_approval": True,
                "action": "generate_t4",
                "details": {"tax_year": tax_year},
                "message": (
                    f"Generating T4 slips for {tax_year} "
                    "has been submitted for your approval."
                ),
            }

        if operation == "get_remittance_summary":
            from agents.tools.payroll_tools import get_pending_remittances
            return get_pending_remittances(shop_id)

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
    if operation == "leave_request":
        return "The leave request has been forwarded for your approval — check the Agent Inbox."
    # Payroll formatting
    if operation == "get_payroll_profile":
        if result.get("error"):
            return f"I couldn't find a payroll profile: {result['error']}"
        return (
            f"Payroll profile for {result.get('shop_employee_id', '?')}:\n"
            f"  Pay type: {result.get('pay_type')} | Rate: {result.get('hourly_rate') or result.get('annual_salary')}\n"
            f"  Province: {result.get('province')} | Frequency: {result.get('pay_frequency')}\n"
            f"  YTD gross: ${float(result.get('ytd_gross') or 0):,.2f} | YTD net (est.): see payslips\n"
            f"  SIN: ***-***-{result.get('sin_last4', '????')}"
        )
    if operation == "get_tips_summary":
        entries = result.get("tips") if isinstance(result, dict) else result
        if not entries:
            return "No tip records found for that query."
        if isinstance(entries, dict) and entries.get("error"):
            return f"Could not retrieve tips: {entries['error']}"
        total = sum(float(t.get("amount") or 0) for t in (entries if isinstance(entries, list) else []))
        return f"Found {len(entries) if isinstance(entries, list) else '?'} tip entries totalling ${total:,.2f}."
    if operation == "get_remittance_summary":
        pending = result.get("remittances") if isinstance(result, dict) else result
        if not pending:
            return "No pending CRA remittances found."
        if isinstance(result, dict) and result.get("error"):
            return f"Could not retrieve remittances: {result['error']}"
        total = sum(float(r.get("amount") or 0) for r in (pending if isinstance(pending, list) else []))
        return f"You have {len(pending) if isinstance(pending, list) else '?'} pending remittance(s) totalling ${total:,.2f}."
    if operation == "log_tip":
        if result.get("error"):
            return f"Could not log tip: {result['error']}"
        return f"Tip of ${float(result.get('amount') or 0):.2f} logged for {result.get('employee_name', 'the employee')}."
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
