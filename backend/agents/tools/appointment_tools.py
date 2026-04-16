"""Appointment agent tools — plain async functions called by Receptionist sub-agent."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from modules.appointments.service import appointment_service


def _parse_scheduled_start(scheduled_start: str) -> datetime:
    """Parse an ISO-8601 datetime string into a datetime object."""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(scheduled_start, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse scheduled_start: {scheduled_start!r}")


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
    """Book an appointment for a customer.

    Args:
        shop_id: The shop to book at.
        service_id: ID of the service being booked.
        scheduled_start: ISO-8601 datetime string for the appointment start.
        customer_name: Customer's full name.
        customer_phone: Optional phone number.
        customer_email: Optional email address.
        employee_id: Optional preferred employee to perform the service.
        notes: Optional booking notes.
    """
    try:
        parsed_start = _parse_scheduled_start(scheduled_start) if isinstance(scheduled_start, str) else scheduled_start
        result = appointment_service.book_appointment(
            shop_id=shop_id,
            service_id=service_id,
            scheduled_start=parsed_start,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            employee_id=employee_id,
            notes=notes,
        )
        return result
    except Exception as e:
        return {"error": str(e)}


def list_appointments(
    shop_id: int,
    date: Optional[str] = None,
    status: Optional[str] = None,
    employee_id: Optional[int] = None,
) -> Dict[str, Any]:
    """List appointments for a shop with optional filters.

    Args:
        shop_id: The shop whose appointments to list.
        date: Optional ISO date string to filter by day.
        status: Optional status filter (scheduled, confirmed, completed, cancelled, etc.).
        employee_id: Optional employee filter.
    """
    try:
        if date:
            appointments = appointment_service.list_appointments(
                shop_id=shop_id,
                date=date,
                status=status,
                employee_id=employee_id,
            )
        else:
            appointments = appointment_service.get_todays_appointments(shop_id)
        return {"appointments": appointments, "shop_id": shop_id, "count": len(appointments)}
    except Exception as e:
        return {"error": str(e)}


def get_upcoming_appointments(shop_id: int, limit: int = 10) -> Dict[str, Any]:
    """Get upcoming appointments for a shop.

    Args:
        shop_id: The shop whose upcoming appointments to list.
        limit: Maximum number of results.
    """
    try:
        appointments = appointment_service.get_upcoming_appointments(shop_id, limit=limit)
        return {"appointments": appointments, "shop_id": shop_id, "count": len(appointments)}
    except Exception as e:
        return {"error": str(e)}


def cancel_appointment(
    shop_id: int,
    appointment_id: int,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Cancel an existing appointment.

    Args:
        shop_id: The shop ID.
        appointment_id: The appointment to cancel.
        reason: Optional cancellation reason.
    """
    try:
        result = appointment_service.update_status(
            shop_id=shop_id,
            appointment_id=appointment_id,
            new_status="cancelled",
            cancel_reason=reason,
        )
        return result if result else {"error": "Appointment not found"}
    except Exception as e:
        return {"error": str(e)}


def reschedule_appointment(
    shop_id: int,
    appointment_id: int,
    new_start: str,
) -> Dict[str, Any]:
    """Reschedule an existing appointment to a new time.

    Args:
        shop_id: The shop ID.
        appointment_id: The appointment to reschedule.
        new_start: New ISO-8601 datetime string.
    """
    try:
        result = appointment_service.reschedule(
            shop_id=shop_id,
            appointment_id=appointment_id,
            new_start=new_start,
        )
        return result
    except Exception as e:
        return {"error": str(e)}


def get_available_slots(
    shop_id: int,
    service_id: int,
    date: str,
    employee_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Get available appointment slots for a given day and service.

    Args:
        shop_id: The shop ID.
        service_id: The service (determines slot duration).
        date: ISO date string (YYYY-MM-DD).
        employee_id: Optional employee filter.
    """
    try:
        slots = appointment_service.get_available_slots(
            shop_id=shop_id,
            service_id=service_id,
            date=date,
            employee_id=employee_id,
        )
        return {"available_slots": slots, "shop_id": shop_id, "date": date}
    except Exception as e:
        return {"error": str(e)}
