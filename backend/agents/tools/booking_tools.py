from typing import Any, Dict, Optional

from db_interface import db_interface
from integrations.booking_mcp_client import BookingMCPClient


def _get_booking_client() -> BookingMCPClient:
    return BookingMCPClient()


def list_queue(shop_id: int) -> Dict[str, Any]:
    """Get active queue items for a shop through the booking MCP service."""
    result = _get_booking_client().list_queue(shop_id)
    if result.get("error"):
        return result
    return {
        "queue_items": list(result.get("items") or result.get("queue_items") or []),
        "live_metrics": result.get("live_metrics") or {},
        "shop_id": result.get("shop_id", shop_id),
        "queue_id": result.get("queue_id"),
        "total_in_queue": result.get("total_in_queue"),
        "waiting_count": result.get("waiting_count"),
        "serving_count": result.get("serving_count"),
        "next_customer": result.get("next_customer"),
    }


def join_queue(shop_id: int, customer_name: str, phone: Optional[str] = None) -> Dict[str, Any]:
    """Join a queue through the booking MCP service."""
    result = _get_booking_client().join_queue(shop_id, customer_name, phone)
    if result.get("error"):
        return result
    result.setdefault("shop_id", shop_id)
    return result


def call_next(shop_id: int, employee_id: Optional[int] = None) -> Dict[str, Any]:
    """Call the next customer through the booking MCP service."""
    result = _get_booking_client().call_next(shop_id, employee_id)
    if result.get("error"):
        return result
    if result.get("message"):
        result.setdefault("shop_id", shop_id)
        return result

    queue_item = result
    customer_name = queue_item.get("customer_name") or "customer"
    return {
        "message": f"Now serving {customer_name}",
        "queue_item": queue_item,
        "shop_id": shop_id,
        "status": queue_item.get("status") or "serving",
    }


def get_wait_time(shop_id: int, queue_item_id: Optional[int] = None) -> Dict[str, Any]:
    """Get wait time estimate through the booking MCP service."""
    result = _get_booking_client().get_wait_time(shop_id, queue_item_id)
    if result.get("error"):
        return result
    if queue_item_id is not None:
        result.setdefault("shop_id", shop_id)
        return result
    return {
        "estimated_wait_minutes": result.get("estimated_wait_minutes", 0),
        "queue_length": result.get("queue_length", 0),
        "shop_id": result.get("shop_id", shop_id),
    }


def close_queue(shop_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
    """Close the active queue for a shop after owner approval via booking MCP."""
    result = _get_booking_client().close_queue(shop_id, reason)
    if result.get("error"):
        return result
    success = bool(result.get("success", True))
    if not success:
        return {"error": result.get("error") or "Failed to close queue", "shop_id": shop_id}
    return {
        "message": f"Queue closed. Reason: {reason or result.get('reason') or 'Not specified'}",
        "shop_id": result.get("shop_id", shop_id),
        "status": "closed",
        "closed_queues": result.get("closed_queues", 1),
    }


def open_queue(shop_id: int, name: str = "Main Queue") -> Dict[str, Any]:
    """Open or re-activate today's queue for a shop (creates a new queue if none exists today)."""
    result = _get_booking_client().open_queue(shop_id, name)
    if result.get("error"):
        return result
    action = result.get("action", "opened")
    return {
        "message": f"Queue {action} successfully",
        "shop_id": result.get("shop_id", shop_id),
        "queue_id": result.get("queue_id"),
        "status": "open",
        "action": action,
    }


def lock_queue_joins(shop_id: int, lock: bool = True, reason: Optional[str] = None) -> Dict[str, Any]:
    """Lock or unlock new customer joins without closing the queue.
    
    When locked=True: existing customers are still served, but no new joins accepted.
    When locked=False: queue re-opens to new joins.
    """
    result = _get_booking_client().lock_queue_joins(shop_id, lock, reason)
    if result.get("error"):
        return result
    accepting = result.get("accepting_joins", not lock)
    return {
        "message": f"Queue {'locked from new joins' if lock else 're-opened to new joins'}",
        "shop_id": result.get("shop_id", shop_id),
        "accepting_joins": accepting,
        "reason": reason,
    }


def search_services(shop_id: int, query: Optional[str] = None) -> Dict[str, Any]:
    """Search available services through the booking MCP service."""
    result = _get_booking_client().search_services(shop_id, query)
    if result.get("error"):
        return result
    return {
        "services": list(result.get("services") or []),
        "shop_id": result.get("shop_id", shop_id),
        "count": result.get("count"),
    }


def create_service(shop_id: int, name: str, cost: float,
                   duration_minutes: int = 30,
                   description: Optional[str] = None,
                   currency: str = "USD") -> Dict[str, Any]:
    """Create a new service through the booking MCP service."""
    result = _get_booking_client().create_service(
        shop_id,
        name,
        cost,
        duration_minutes=duration_minutes,
        description=description,
        currency=currency,
    )
    if result.get("error"):
        return result
    result.setdefault("shop_id", shop_id)
    return result


def update_service(shop_id: int, service_id: int,
                   name: Optional[str] = None,
                   cost: Optional[float] = None,
                   duration_minutes: Optional[int] = None,
                   description: Optional[str] = None,
                   is_active: Optional[bool] = None) -> Dict[str, Any]:
    """Update an existing service through the booking MCP service."""
    result = _get_booking_client().update_service(
        shop_id,
        service_id,
        name=name,
        cost=cost,
        duration_minutes=duration_minutes,
        description=description,
        is_active=is_active,
    )
    if result.get("error"):
        return result
    result.setdefault("shop_id", shop_id)
    return result


def delete_service(shop_id: int, service_id: int) -> Dict[str, Any]:
    """Soft-delete a service through the booking MCP service."""
    result = _get_booking_client().delete_service(shop_id, service_id)
    if result.get("error"):
        return result
    result.setdefault("shop_id", shop_id)
    return result


def book_appointment(
    shop_id: int,
    service_id: int,
    scheduled_start: str,
    customer_name: str,
    customer_phone: Optional[str] = None,
    customer_email: Optional[str] = None,
    employee_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Book an appointment through the booking MCP service."""
    result = _get_booking_client().book_appointment(
        shop_id,
        service_id,
        scheduled_start,
        customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email,
        employee_id=employee_id,
        notes=notes,
    )
    if result.get("error"):
        return result
    result.setdefault("shop_id", shop_id)
    return result


def list_appointments(
    shop_id: int,
    date: Optional[str] = None,
    status: Optional[str] = None,
    employee_id: Optional[int] = None,
) -> Dict[str, Any]:
    """List appointments through the booking MCP service."""
    result = _get_booking_client().list_appointments(shop_id, date=date, status=status, employee_id=employee_id)
    if result.get("error"):
        return result
    result.setdefault("shop_id", shop_id)
    result.setdefault("appointments", [])
    result.setdefault("count", len(result.get("appointments") or []))
    return result


def cancel_appointment(shop_id: int, appointment_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
    """Cancel an appointment through the booking MCP service."""
    result = _get_booking_client().cancel_appointment(shop_id, appointment_id, reason=reason)
    if result.get("error"):
        return result
    result.setdefault("shop_id", shop_id)
    return result


def get_available_slots(
    shop_id: int,
    service_id: int,
    date: str,
    employee_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Get available appointment slots through the booking MCP service."""
    result = _get_booking_client().get_available_slots(shop_id, service_id, date, employee_id=employee_id)
    if result.get("error"):
        return result
    result.setdefault("shop_id", shop_id)
    result.setdefault("date", date)
    result.setdefault("available_slots", [])
    return result
