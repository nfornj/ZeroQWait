"""Appointment router — scheduling, availability, and smart load balancing."""

from datetime import datetime, timedelta, date, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from modules.appointments.service import appointment_service
from modules.appointments.schemas import (
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentResponse,
)
from modules.appointments.models import AppointmentStatus
from shared.auth_utils import get_current_user, get_current_user_optional
from permissions import check_shop_access
from websocket_manager import manager
from db_interface import db_interface
from database import SessionLocal

router = APIRouter()


# ── Schemas for request/response ──────────────────────────────────

class BookAppointmentRequest(BaseModel):
    service_id: Optional[int] = None
    employee_id: Optional[int] = None
    customer_name: str
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    scheduled_start: datetime
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None


class RescheduleRequest(BaseModel):
    new_start: datetime
    duration_minutes: Optional[int] = None


class EmployeeDayAvailability(BaseModel):
    employee_id: int
    username: str
    is_clocked_in: bool
    shift_start: Optional[datetime] = None
    appointments_today: int
    next_available_slot: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────

def _get_service_details(service_id: int) -> dict:
    """Fetch service to get duration and cost."""
    session = SessionLocal()
    try:
        from modules.shops.models import ShopService
        svc = session.query(ShopService).filter(ShopService.id == service_id).first()
        if svc:
            return {
                "duration_minutes": svc.duration_minutes or 30,
                "cost": svc.cost or 0.0,
                "name": svc.name,
            }
        return {}
    finally:
        session.close()


def _auto_assign_employee(shop_id: int, scheduled_start: datetime, scheduled_end: datetime) -> Optional[int]:
    """
    Intelligently assign the best employee for a time slot.
    Strategy:
      1. Get all active employees for the shop
      2. Get clocked-in employees (prefer them)
      3. Check each for conflicts at the requested time
      4. Pick the one with the fewest appointments that day
    """
    session = SessionLocal()
    try:
        from modules.employees.models import ShopEmployee, EmployeeShift
        from modules.appointments.models import Appointment, AppointmentStatus as AS

        # Get active employees for this shop
        employees = session.query(ShopEmployee).filter(
            ShopEmployee.shop_id == shop_id,
            ShopEmployee.is_active == True,
        ).all()

        if not employees:
            return None

        day_start = scheduled_start.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        best_employee = None
        min_load = float("inf")

        for emp in employees:
            user_id = emp.user_id

            # Check for conflicts
            conflict = session.query(Appointment).filter(
                Appointment.shop_id == shop_id,
                Appointment.employee_id == user_id,
                Appointment.status.in_([AS.SCHEDULED, AS.CONFIRMED, AS.IN_PROGRESS]),
                Appointment.scheduled_start < scheduled_end,
                Appointment.scheduled_end > scheduled_start,
            ).first()

            if conflict:
                continue

            # Count appointments for the day (load)
            day_count = session.query(Appointment).filter(
                Appointment.shop_id == shop_id,
                Appointment.employee_id == user_id,
                Appointment.scheduled_start >= day_start,
                Appointment.scheduled_start < day_end,
                Appointment.status.in_([AS.SCHEDULED, AS.CONFIRMED, AS.IN_PROGRESS]),
            ).count()

            # Also count walk-in queue items being served
            from modules.queues.models import QueueItem, QueueStatus
            queue_load = session.query(QueueItem).filter(
                QueueItem.assigned_employee_id == user_id,
                QueueItem.status.in_([QueueStatus.WAITING, QueueStatus.BEING_SERVED]),
            ).count()

            total_load = day_count + queue_load

            if total_load < min_load:
                min_load = total_load
                best_employee = user_id

        return best_employee
    finally:
        session.close()


def _normalize_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


async def _broadcast_appointment_update(shop_id: int, event_type: str, data: dict):
    """Push appointment events to shop owner via WebSocket."""
    payload = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }
    await manager.broadcast(str(shop_id), payload)


# ── Public: Customer books an appointment ─────────────────────────

@router.post("/shop/{shop_id}/book", response_model=dict)
async def book_appointment(
    shop_id: int,
    req: BookAppointmentRequest,
):
    """
    Customer books an appointment at a shop.
    - Auto-assigns employee if none specified (smart load balancing)
    - Auto-calculates duration from service if not specified
    - Checks for conflicts
    """
    # Verify shop exists
    shop = db_interface.get_shop_by_id(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    scheduled_start = _normalize_utc_naive(req.scheduled_start)

    # Validate scheduled_start is in the future
    if scheduled_start < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=400, detail="Cannot book appointments in the past")

    # Get service details for duration and cost
    duration = req.duration_minutes or 30
    service_cost = 0.0
    if req.service_id:
        svc = _get_service_details(req.service_id)
        if not svc:
            raise HTTPException(status_code=404, detail="Service not found")
        if not req.duration_minutes:
            duration = svc["duration_minutes"]
        service_cost = svc["cost"]

    scheduled_end = scheduled_start + timedelta(minutes=duration)

    # Auto-assign employee if not specified
    employee_id = req.employee_id
    if not employee_id:
        employee_id = _auto_assign_employee(shop_id, scheduled_start, scheduled_end)
        if not employee_id:
            raise HTTPException(
                status_code=409,
                detail="No employees available at the requested time. Please choose a different time slot.",
            )

    result = appointment_service.book_appointment(
        shop_id=shop_id,
        customer_name=req.customer_name,
        scheduled_start=scheduled_start,
        service_id=req.service_id,
        employee_id=employee_id,
        customer_phone=req.customer_phone,
        customer_email=req.customer_email,
        duration_minutes=duration,
        notes=req.notes,
        service_cost=service_cost,
    )

    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])

    # Broadcast to shop owner
    await _broadcast_appointment_update(shop_id, "new_appointment", {
        "appointment_id": result["id"],
        "customer_name": req.customer_name,
        "scheduled_start": str(req.scheduled_start),
        "service_id": req.service_id,
        "employee_id": employee_id,
    })

    return result


# ── Public: Available slots ───────────────────────────────────────

@router.get("/shop/{shop_id}/available-slots", response_model=list)
def get_available_slots(
    shop_id: int,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    service_id: Optional[int] = None,
    employee_id: Optional[int] = None,
):
    """
    Get available appointment time slots for a specific date.
    Considers existing appointments + walk-in queue load.
    """
    shop = db_interface.get_shop_by_id(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Get duration from service if provided
    slot_duration = 30
    if service_id:
        svc = _get_service_details(service_id)
        if svc:
            slot_duration = svc["duration_minutes"]

    slots = appointment_service.get_available_slots(
        shop_id=shop_id,
        date=target_date,
        service_id=service_id,
        employee_id=employee_id,
        slot_duration_minutes=slot_duration,
    )

    return slots


# ── Owner/Employee: List appointments ─────────────────────────────

@router.get("/shop/{shop_id}", response_model=list)
def list_shop_appointments(
    shop_id: int,
    date: Optional[str] = None,
    status: Optional[str] = None,
    employee_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    """List appointments for a shop (owner/employee view)."""
    check_shop_access(shop_id, current_user)

    target_date = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    return appointment_service.list_appointments(
        shop_id=shop_id,
        date=target_date,
        status=status,
        employee_id=employee_id,
    )


@router.get("/shop/{shop_id}/today", response_model=list)
def get_todays_appointments(
    shop_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Get today's appointments for a shop."""
    check_shop_access(shop_id, current_user)
    return appointment_service.get_todays_appointments(shop_id)


@router.get("/shop/{shop_id}/upcoming", response_model=list)
def get_upcoming_appointments(
    shop_id: int,
    hours: int = 24,
    current_user: dict = Depends(get_current_user),
):
    """Get upcoming appointments within N hours."""
    check_shop_access(shop_id, current_user)
    return appointment_service.get_upcoming_appointments(shop_id, hours=hours)


# ── Owner/Employee: Single appointment ────────────────────────────

@router.get("/{appointment_id}", response_model=dict)
def get_appointment(
    appointment_id: int,
    shop_id: int = Query(...),
    current_user: dict = Depends(get_current_user),
):
    """Get a single appointment by ID."""
    check_shop_access(shop_id, current_user)
    appt = appointment_service.get_appointment(shop_id, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appt


# ── Owner/Employee: Update status ─────────────────────────────────

@router.patch("/{appointment_id}/status", response_model=dict)
async def update_appointment_status(
    appointment_id: int,
    shop_id: int = Query(...),
    new_status: str = Query(...),
    reason: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Update appointment status.
    Valid transitions:
      SCHEDULED → CONFIRMED, CANCELLED, NO_SHOW
      CONFIRMED → CHECKED_IN, CANCELLED, NO_SHOW
      CHECKED_IN → IN_PROGRESS, CANCELLED
      IN_PROGRESS → COMPLETED, CANCELLED
    """
    check_shop_access(shop_id, current_user)

    result = appointment_service.update_status(shop_id, appointment_id, new_status, reason)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Broadcast status change
    await _broadcast_appointment_update(shop_id, "appointment_status_changed", {
        "appointment_id": appointment_id,
        "new_status": new_status,
        "updated_by": current_user.get("username"),
    })

    return result


# ── Owner: Reschedule ─────────────────────────────────────────────

@router.post("/{appointment_id}/reschedule", response_model=dict)
async def reschedule_appointment(
    appointment_id: int,
    req: RescheduleRequest,
    shop_id: int = Query(...),
    current_user: dict = Depends(get_current_user),
):
    """Reschedule an appointment (cancels old, creates new)."""
    check_shop_access(shop_id, current_user, require_owner=True)

    result = appointment_service.reschedule(
        shop_id=shop_id,
        appointment_id=appointment_id,
        new_start=req.new_start,
        duration_minutes=req.duration_minutes,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    await _broadcast_appointment_update(shop_id, "appointment_rescheduled", {
        "old_appointment_id": appointment_id,
        "new_appointment": result,
    })

    return result


# ── Employee availability for the day ─────────────────────────────

@router.get("/shop/{shop_id}/employee-availability", response_model=list)
def get_employee_availability(
    shop_id: int,
    date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Get employee availability status for a given day.
    Shows: clocked-in status, appointment count, next available slot.
    Used by the owner feed to surface 'Employee X is not available today'.
    """
    check_shop_access(shop_id, current_user)

    target_date = datetime.utcnow()
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

    session = SessionLocal()
    try:
        from modules.employees.models import ShopEmployee, EmployeeShift
        from modules.auth.models import User
        from modules.appointments.models import Appointment, AppointmentStatus as AS

        employees = session.query(ShopEmployee, User).join(
            User, ShopEmployee.user_id == User.id
        ).filter(
            ShopEmployee.shop_id == shop_id,
            ShopEmployee.is_active == True,
        ).all()

        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        result = []
        for emp, user in employees:
            # Check if clocked in
            active_shift = session.query(EmployeeShift).filter(
                EmployeeShift.user_id == user.id,
                EmployeeShift.shop_id == shop_id,
                EmployeeShift.clock_out == None,
            ).first()

            # Count today's appointments
            appt_count = session.query(Appointment).filter(
                Appointment.shop_id == shop_id,
                Appointment.employee_id == user.id,
                Appointment.scheduled_start >= day_start,
                Appointment.scheduled_start < day_end,
                Appointment.status.in_([AS.SCHEDULED, AS.CONFIRMED, AS.IN_PROGRESS]),
            ).count()

            # Find next available slot
            next_slot = None
            slots = appointment_service.get_available_slots(
                shop_id=shop_id,
                date=target_date,
                employee_id=user.id,
                slot_duration_minutes=30,
            )
            if slots:
                next_slot = slots[0]["start"]

            result.append({
                "employee_id": user.id,
                "username": user.username,
                "is_clocked_in": active_shift is not None,
                "shift_start": str(active_shift.clock_in) if active_shift else None,
                "appointments_today": appt_count,
                "next_available_slot": next_slot,
            })

        return result
    finally:
        session.close()


# ── Owner feed: Unavailable employees alert ───────────────────────

@router.get("/shop/{shop_id}/unavailable-employees", response_model=list)
def get_unavailable_employees(
    shop_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Returns employees who are NOT clocked in today.
    Used by the owner dashboard feed to show alerts like:
    'John and Sarah are not available today'
    """
    check_shop_access(shop_id, current_user)

    session = SessionLocal()
    try:
        from modules.employees.models import ShopEmployee, EmployeeShift
        from modules.auth.models import User

        employees = session.query(ShopEmployee, User).join(
            User, ShopEmployee.user_id == User.id
        ).filter(
            ShopEmployee.shop_id == shop_id,
            ShopEmployee.is_active == True,
        ).all()

        unavailable = []
        for emp, user in employees:
            active_shift = session.query(EmployeeShift).filter(
                EmployeeShift.user_id == user.id,
                EmployeeShift.shop_id == shop_id,
                EmployeeShift.clock_out == None,
            ).first()

            if not active_shift:
                unavailable.append({
                    "employee_id": user.id,
                    "username": user.username,
                    "email": user.email,
                })

        return unavailable
    finally:
        session.close()


# ── Customer: Check appointment by phone ──────────────────────────

@router.get("/shop/{shop_id}/my-appointments", response_model=list)
def get_customer_appointments(
    shop_id: int,
    phone: str = Query(..., description="Customer phone number"),
):
    """
    Customer checks their appointments by phone number.
    Public endpoint — no auth required.
    """
    return appointment_service.list_appointments(
        shop_id=shop_id,
        customer_phone=phone,
    )
