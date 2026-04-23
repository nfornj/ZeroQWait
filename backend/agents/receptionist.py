"""Receptionist specialist graph with explicit planner and executor nodes."""

import json
import logging
from typing import Any, Dict, Optional, Sequence

from langchain_core.messages import BaseMessage

from .specialist_graph import build_specialist_runnable
from .tools import booking_tools

logger = logging.getLogger(__name__)

SUPPORTED_OPERATIONS = [
    "list_queue",
    "join_queue",
    "call_next",
    "get_wait_time",
    "close_queue",
    "search_services",
    "create_service",
    "update_service",
    "delete_service",
    "book_appointment",
    "list_appointments",
    "cancel_appointment",
    "get_available_slots",
]

PLANNER_INSTRUCTIONS = """\
- list_queue: queue status, who is waiting, queue summary, queue line.
- join_queue: add or check in a customer; arguments: customer_name, phone(optional).
- call_next: call the next customer; arguments: employee_id(optional).
- get_wait_time: questions about wait time. For queue length or queue status, use list_queue instead.
- close_queue: owner wants to close or stop the queue; arguments: reason(optional). This requires approval.
- search_services: list services, search by service name, or look up a service before update/delete.
- create_service: add a new service; arguments: name, cost, duration_minutes(optional).
- update_service: only when service_id is known; otherwise choose search_services first.
- delete_service: only when service_id is known; otherwise choose search_services first.
- book_appointment: only when service_id, scheduled_start, and customer_name are available.
- list_appointments: list appointments for a date or status.
- cancel_appointment: cancel by appointment_id; ask if the id is missing.
- get_available_slots: availability questions when service_id and date are known.
- Never output read or get_queue_length. Use list_queue for queue counts and queue summaries.
"""

OPERATION_ALIASES = {
    "get_queue_length": "list_queue",
    "read": "list_queue",
}


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


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
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


def _normalize_receptionist_operation(operation: str, plan: Dict[str, Any], messages: Sequence[BaseMessage]) -> str:
    normalized_operation = str(operation or "").strip().lower()
    if normalized_operation in OPERATION_ALIASES:
        return OPERATION_ALIASES[normalized_operation]

    plan_text = _flatten_text(plan).lower()
    conversation_text = _recent_conversation_text(messages).lower()
    combined_text = f"{conversation_text} {plan_text}".strip()
    queue_keywords = ("queue", "waiting", "line")
    asks_for_count_or_status = any(
        phrase in combined_text
        for phrase in ("how many", "queue status", "who is waiting", "who's waiting", "line status", "queue length")
    )
    asks_for_wait_time = any(phrase in combined_text for phrase in ("wait time", "how long", "estimated wait"))

    if normalized_operation in {"answer", "respond", "lookup", "summarize"} and any(
        keyword in combined_text for keyword in queue_keywords
    ):
        if asks_for_wait_time:
            return "get_wait_time"
        return "list_queue"

    if any(keyword in combined_text for keyword in queue_keywords):
        if asks_for_count_or_status:
            return "list_queue"
        if asks_for_wait_time:
            return "get_wait_time"

    return str(operation or "").strip()


def _execute_receptionist_operation(operation: str, arguments: Dict[str, Any], messages: Sequence[BaseMessage]) -> Dict[str, Any]:
    if operation == "list_queue":
        return booking_tools.list_queue(arguments.get("shop_id", 0))
    return {"error": f"Unsupported receptionist operation: {operation}"}


def _build_receptionist_executor(shop_id: int):
    def executor(operation: str, arguments: Dict[str, Any], messages: Sequence[BaseMessage]) -> Dict[str, Any]:
        if operation == "list_queue":
            return booking_tools.list_queue(shop_id)
        if operation == "join_queue":
            customer_name = _optional_str(arguments.get("customer_name") or arguments.get("name"))
            if not customer_name:
                return {"error": "join_queue requires customer_name"}
            return booking_tools.join_queue(shop_id, customer_name, _optional_str(arguments.get("phone")))
        if operation == "call_next":
            return booking_tools.call_next(shop_id, _to_int(arguments.get("employee_id")))
        if operation == "get_wait_time":
            return booking_tools.get_wait_time(shop_id)
        if operation == "close_queue":
            reason = _optional_str(arguments.get("reason")) or "Owner requested closure"
            return {
                "requires_approval": True,
                "action": "close_queue",
                "details": {"reason": reason},
                "message": f"Queue closure has been submitted for owner approval. Reason: {reason}",
            }
        if operation == "search_services":
            return booking_tools.search_services(shop_id, _optional_str(arguments.get("query")))
        if operation == "create_service":
            name = _optional_str(arguments.get("name"))
            cost = _to_float(arguments.get("cost"))
            if not name or cost is None:
                return {"error": "create_service requires name and cost"}
            duration = _to_int(arguments.get("duration_minutes")) or 30
            return booking_tools.create_service(shop_id, name, cost, duration)
        if operation == "update_service":
            service_id = _to_int(arguments.get("service_id"))
            if service_id is None:
                return {"error": "update_service requires service_id"}
            return booking_tools.update_service(
                shop_id,
                service_id,
                name=_optional_str(arguments.get("name")),
                cost=_to_float(arguments.get("cost")),
                duration_minutes=_to_int(arguments.get("duration_minutes")),
            )
        if operation == "delete_service":
            service_id = _to_int(arguments.get("service_id"))
            if service_id is None:
                return {"error": "delete_service requires service_id"}
            return booking_tools.delete_service(shop_id, service_id)
        if operation == "book_appointment":
            service_id = _to_int(arguments.get("service_id"))
            scheduled_start = _optional_str(arguments.get("scheduled_start"))
            customer_name = _optional_str(arguments.get("customer_name"))
            if service_id is None or not scheduled_start or not customer_name:
                return {"error": "book_appointment requires service_id, scheduled_start, and customer_name"}
            return booking_tools.book_appointment(
                shop_id,
                service_id,
                scheduled_start,
                customer_name,
                customer_phone=_optional_str(arguments.get("customer_phone")),
                customer_email=_optional_str(arguments.get("customer_email")),
                employee_id=_to_int(arguments.get("employee_id")),
                notes=_optional_str(arguments.get("notes")),
            )
        if operation == "list_appointments":
            return booking_tools.list_appointments(
                shop_id,
                date=_optional_str(arguments.get("date")),
                status=_optional_str(arguments.get("status")),
                employee_id=_to_int(arguments.get("employee_id")),
            )
        if operation == "cancel_appointment":
            appointment_id = _to_int(arguments.get("appointment_id"))
            if appointment_id is None:
                return {"error": "cancel_appointment requires appointment_id"}
            return booking_tools.cancel_appointment(shop_id, appointment_id, reason=_optional_str(arguments.get("reason")))
        if operation == "get_available_slots":
            service_id = _to_int(arguments.get("service_id"))
            date = _optional_str(arguments.get("date"))
            if service_id is None or not date:
                return {"error": "get_available_slots requires service_id and date"}
            return booking_tools.get_available_slots(shop_id, service_id, date, employee_id=_to_int(arguments.get("employee_id")))
        return {"error": f"Unsupported receptionist operation: {operation}"}

    return executor


def _format_receptionist_response(operation: str, result: Dict[str, Any]) -> str:
    if result.get("error"):
        return f"I couldn't complete that receptionist task: {result['error']}"
    if operation == "list_queue":
        items = list(result.get("queue_items") or [])
        live_metrics = dict(result.get("live_metrics") or {})
        queue_length = live_metrics.get("queue_length", len(items))
        wait_minutes = live_metrics.get("estimated_wait_minutes")
        if not items:
            return "There is no active queue right now."
        names = [str(item.get("customer_name") or "customer") for item in items[:5]]
        names_text = ", ".join(names)
        if wait_minutes is not None:
            return f"There are {queue_length} people waiting. Estimated wait time is about {wait_minutes} minutes. First in line: {names_text}."
        return f"There are {queue_length} people waiting. First in line: {names_text}."
    if operation == "get_wait_time":
        return (
            f"Estimated wait time is about {result.get('estimated_wait_minutes', 0)} minutes "
            f"with {result.get('queue_length', 0)} people in the queue."
        )
    if operation == "search_services":
        services = list(result.get("services") or [])
        if not services:
            return "I couldn't find any matching services."
        lines = []
        for service in services[:8]:
            lines.append(
                f"- #{service.get('id')}: {service.get('name')} — ${float(service.get('cost', 0.0) or 0.0):.2f} ({int(service.get('duration_minutes', 0) or 0)} min)"
            )
        return "Available services:\n" + "\n".join(lines)
    if operation == "list_appointments":
        appointments = list(result.get("appointments") or [])
        if not appointments:
            return "No appointments matched that request."
        lines = []
        for appointment in appointments[:8]:
            lines.append(
                f"- #{appointment.get('id')}: {appointment.get('customer_name', 'Customer')} at {appointment.get('scheduled_start', appointment.get('date', 'scheduled time unavailable'))}"
            )
        return f"I found {len(appointments)} appointment(s):\n" + "\n".join(lines)
    if operation == "get_available_slots":
        slots = list(result.get("available_slots") or [])
        if not slots:
            return "I couldn't find any open slots for that service on that date."
        return "Available slots: " + ", ".join(str(slot) for slot in slots[:12])
    if result.get("message"):
        return str(result["message"])
    return f"The receptionist completed {operation.replace('_', ' ')}."

def create_receptionist_runnable(shop_id: int | None = None):
    if not shop_id:
        raise ValueError("shop_id is required — cannot build the receptionist graph without it")

    return build_specialist_runnable(
        agent_name="receptionist",
        shop_id=shop_id,
        temperature=0.25,
        planner_instructions=PLANNER_INSTRUCTIONS,
        supported_operations=SUPPORTED_OPERATIONS,
        operation_aliases=OPERATION_ALIASES,
        operation_normalizer=_normalize_receptionist_operation,
        executor=_build_receptionist_executor(shop_id),
        formatter=_format_receptionist_response,
    )


__all__ = ["create_receptionist_runnable", "_normalize_receptionist_operation"]
