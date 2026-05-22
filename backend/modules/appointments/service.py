"""Appointment service — CRUD and business logic."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from database import SessionLocal
from .models import Appointment, AppointmentStatus


def _status_value(value) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


class AppointmentService:
    """Tenant-scoped appointment operations."""

    def get_session(self) -> Session:
        return SessionLocal()

    def _to_dict(self, appt: Appointment) -> Dict:
        return {
            "id": appt.id,
            "shop_id": appt.shop_id,
            "customer_id": appt.customer_id,
            "service_id": appt.service_id,
            "employee_id": appt.employee_id,
            "customer_name": appt.customer_name,
            "customer_phone": appt.customer_phone,
            "customer_email": appt.customer_email,
            "scheduled_start": str(appt.scheduled_start) if appt.scheduled_start else None,
            "scheduled_end": str(appt.scheduled_end) if appt.scheduled_end else None,
            "actual_start": str(appt.actual_start) if appt.actual_start else None,
            "actual_end": str(appt.actual_end) if appt.actual_end else None,
            "status": appt.status.value if appt.status else None,
            "service_cost": appt.service_cost,
            "notes": appt.notes,
            "cancelled_at": str(appt.cancelled_at) if appt.cancelled_at else None,
            "cancel_reason": appt.cancel_reason,
            "created_at": str(appt.created_at) if appt.created_at else None,
        }

    # ── Create ────────────────────────────────────────────────────

    def book_appointment(
        self,
        shop_id: int,
        customer_name: str,
        scheduled_start: datetime,
        service_id: Optional[int] = None,
        employee_id: Optional[int] = None,
        customer_phone: Optional[str] = None,
        customer_email: Optional[str] = None,
        duration_minutes: int = 30,
        notes: Optional[str] = None,
        service_cost: float = 0.0,
    ) -> Dict:
        session = self.get_session()
        try:
            scheduled_end = scheduled_start + timedelta(minutes=duration_minutes)

            # Conflict check: overlapping appointments for same employee
            if employee_id:
                conflict = session.query(Appointment).filter(
                    Appointment.shop_id == shop_id,
                    Appointment.employee_id == employee_id,
                    Appointment.status.in_([
                        AppointmentStatus.SCHEDULED,
                        AppointmentStatus.CONFIRMED,
                        AppointmentStatus.IN_PROGRESS,
                    ]),
                    Appointment.scheduled_start < scheduled_end,
                    Appointment.scheduled_end > scheduled_start,
                ).first()
                if conflict:
                    return {"error": "Employee has a conflicting appointment at that time"}

            appt = Appointment(
                shop_id=shop_id,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_email=customer_email,
                service_id=service_id,
                employee_id=employee_id,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                service_cost=service_cost,
                notes=notes,
            )
            session.add(appt)
            session.commit()
            session.refresh(appt)
            return self._to_dict(appt)
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()

    # ── Read ──────────────────────────────────────────────────────

    def get_appointment(self, shop_id: int, appointment_id: int) -> Optional[Dict]:
        session = self.get_session()
        try:
            appt = session.query(Appointment).filter(
                Appointment.id == appointment_id,
                Appointment.shop_id == shop_id,
            ).first()
            return self._to_dict(appt) if appt else None
        finally:
            session.close()

    def list_appointments(
        self,
        shop_id: int,
        date: Optional[datetime] = None,
        status: Optional[str] = None,
        employee_id: Optional[int] = None,
        customer_phone: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        session = self.get_session()
        try:
            q = session.query(Appointment).filter(Appointment.shop_id == shop_id)

            if date:
                day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)
                q = q.filter(
                    Appointment.scheduled_start >= day_start,
                    Appointment.scheduled_start < day_end,
                )

            if status:
                try:
                    status_enum = AppointmentStatus(status)
                    q = q.filter(Appointment.status == status_enum)
                except ValueError:
                    pass

            if employee_id:
                q = q.filter(Appointment.employee_id == employee_id)

            if customer_phone:
                q = q.filter(Appointment.customer_phone == customer_phone)

            appts = q.order_by(Appointment.scheduled_start).limit(limit).all()
            return [self._to_dict(a) for a in appts]
        finally:
            session.close()

    def get_todays_appointments(self, shop_id: int) -> List[Dict]:
        now = datetime.utcnow()
        return self.list_appointments(shop_id, date=now)

    def get_upcoming_appointments(self, shop_id: int, hours: int = 24) -> List[Dict]:
        session = self.get_session()
        try:
            now = datetime.utcnow()
            cutoff = now + timedelta(hours=hours)
            appts = session.query(Appointment).filter(
                Appointment.shop_id == shop_id,
                Appointment.scheduled_start >= now,
                Appointment.scheduled_start <= cutoff,
                Appointment.status.in_([
                    AppointmentStatus.SCHEDULED,
                    AppointmentStatus.CONFIRMED,
                ]),
            ).order_by(Appointment.scheduled_start).all()
            return [self._to_dict(a) for a in appts]
        finally:
            session.close()

    # ── Update ────────────────────────────────────────────────────

    def update_status(
        self, shop_id: int, appointment_id: int, new_status: str, reason: Optional[str] = None,
    ) -> Dict:
        session = self.get_session()
        try:
            appt = session.query(Appointment).filter(
                Appointment.id == appointment_id,
                Appointment.shop_id == shop_id,
            ).first()
            if not appt:
                return {"error": "Appointment not found"}

            try:
                status_enum = AppointmentStatus(new_status)
            except ValueError:
                return {"error": f"Invalid status: {new_status}"}

            previous_status = _status_value(appt.status)
            appt.status = status_enum

            if status_enum == AppointmentStatus.CANCELLED:
                appt.cancelled_at = datetime.utcnow()
                appt.cancel_reason = reason
            elif status_enum == AppointmentStatus.IN_PROGRESS:
                appt.actual_start = datetime.utcnow()
            elif status_enum == AppointmentStatus.COMPLETED:
                appt.actual_end = datetime.utcnow()
                if previous_status != AppointmentStatus.COMPLETED.value and appt.service_id:
                    from agents.tools.inventory_tools import deduct_service_supplies

                    deduct_service_supplies(
                        shop_id=shop_id,
                        service_id=int(appt.service_id),
                        appointment_id=appointment_id,
                        session=session,
                    )
            elif status_enum == AppointmentStatus.CHECKED_IN:
                pass  # just the status flip

            session.commit()
            session.refresh(appt)
            return self._to_dict(appt)
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()

    def reschedule(
        self,
        shop_id: int,
        appointment_id: int,
        new_start: datetime,
        duration_minutes: Optional[int] = None,
    ) -> Dict:
        session = self.get_session()
        try:
            old = session.query(Appointment).filter(
                Appointment.id == appointment_id,
                Appointment.shop_id == shop_id,
            ).first()
            if not old:
                return {"error": "Appointment not found"}

            if old.status in (AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED):
                return {"error": f"Cannot reschedule a {old.status.value} appointment"}

            # Cancel old
            old.status = AppointmentStatus.CANCELLED
            old.cancelled_at = datetime.utcnow()
            old.cancel_reason = "Rescheduled"
            session.commit()

            # Create new
            dur = duration_minutes or (
                int((old.scheduled_end - old.scheduled_start).total_seconds() / 60)
                if old.scheduled_end and old.scheduled_start
                else 30
            )
            session.close()
            return self.book_appointment(
                shop_id=shop_id,
                customer_name=old.customer_name,
                scheduled_start=new_start,
                service_id=old.service_id,
                employee_id=old.employee_id,
                customer_phone=old.customer_phone,
                customer_email=old.customer_email,
                duration_minutes=dur,
                notes=old.notes,
                service_cost=old.service_cost,
            )
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            try:
                session.close()
            except Exception:
                pass

    # ── Availability ──────────────────────────────────────────────

    def get_available_slots(
        self,
        shop_id: int,
        date: datetime,
        service_id: Optional[int] = None,
        employee_id: Optional[int] = None,
        slot_duration_minutes: int = 30,
        business_start_hour: int = 9,
        business_end_hour: int = 18,
    ) -> List[Dict]:
        """Return available time slots for a given day."""
        session = self.get_session()
        try:
            day_start = date.replace(hour=business_start_hour, minute=0, second=0, microsecond=0)
            day_end = date.replace(hour=business_end_hour, minute=0, second=0, microsecond=0)

            filters = [
                Appointment.shop_id == shop_id,
                Appointment.scheduled_start >= day_start,
                Appointment.scheduled_start < day_end,
                Appointment.status.in_([
                    AppointmentStatus.SCHEDULED,
                    AppointmentStatus.CONFIRMED,
                    AppointmentStatus.IN_PROGRESS,
                ]),
            ]
            if employee_id:
                filters.append(Appointment.employee_id == employee_id)

            booked = session.query(Appointment).filter(and_(*filters)).order_by(
                Appointment.scheduled_start
            ).all()

            booked_ranges = [
                (b.scheduled_start, b.scheduled_end or b.scheduled_start + timedelta(minutes=slot_duration_minutes))
                for b in booked
            ]

            slots = []
            cursor = day_start
            while cursor + timedelta(minutes=slot_duration_minutes) <= day_end:
                slot_end = cursor + timedelta(minutes=slot_duration_minutes)
                conflict = any(s < slot_end and e > cursor for s, e in booked_ranges)
                if not conflict:
                    slots.append({
                        "start": str(cursor),
                        "end": str(slot_end),
                        "available": True,
                    })
                cursor += timedelta(minutes=slot_duration_minutes)

            return slots
        finally:
            session.close()


appointment_service = AppointmentService()
