"""public_booking_router.py — No-auth public booking API.

Rate limited via Redis. All writes use public_token for cancel/confirm.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from database import SessionLocal
from redis_client import redis_client as _redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/book", tags=["public-booking"])

_RATE_LIMIT = 10   # requests
_RATE_WINDOW = 60  # seconds


def _rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    if not _redis_client.check_rate_limit(ip, limit=_RATE_LIMIT, window=_RATE_WINDOW):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait before trying again.")


# ── Request / Response models ──────────────────────────────────────────────────

class BookingRequest(BaseModel):
    service_id: int
    employee_id: Optional[int] = None
    customer_name: str = Field(..., min_length=1, max_length=100)
    customer_phone: Optional[str] = Field(None, max_length=30)
    customer_email: Optional[str] = Field(None, max_length=120)
    scheduled_start: datetime
    notes: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_booking_page(session, slug: str) -> Optional[Dict[str, Any]]:
    row = session.execute(
        text("""
            SELECT p.id, p.shop_id, p.is_enabled, p.title, p.welcome_message,
                   p.max_advance_days, p.min_advance_hours, p.require_phone, p.require_email,
                   s.name AS shop_name, s.slug
            FROM public_booking_pages p
            JOIN shops s ON s.id = p.shop_id
            WHERE s.slug = :slug AND s.is_active = TRUE
            LIMIT 1
        """),
        {"slug": slug},
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0], "shop_id": row[1], "is_enabled": row[2],
        "title": row[3], "welcome_message": row[4],
        "max_advance_days": row[5], "min_advance_hours": row[6],
        "require_phone": row[7], "require_email": row[8],
        "shop_name": row[9], "slug": row[10],
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/{slug}")
def booking_page_info(slug: str, request: Request, _=Depends(_rate_limit)):
    """Return booking page metadata + active services for a shop slug."""
    with SessionLocal() as session:
        page = _get_booking_page(session, slug)
        if not page:
            raise HTTPException(status_code=404, detail="Booking page not found")
        if not page["is_enabled"]:
            raise HTTPException(status_code=403, detail="Online booking is not enabled for this shop")

        services = session.execute(
            text("""
                SELECT id, name, description, duration_minutes, price_cents, hst_applicable, category
                FROM shop_services
                WHERE shop_id = :shop_id AND is_active = TRUE
                ORDER BY category NULLS LAST, name
            """),
            {"shop_id": page["shop_id"]},
        ).fetchall()

        page["services"] = [
            {
                "id": r[0], "name": r[1], "description": r[2],
                "duration_minutes": r[3],
                "price_cents": r[4],
                "price_display": f"${(r[4] or 0) / 100:.2f}",
                "hst_applicable": r[5],
                "category": r[6],
            }
            for r in services
        ]

    return page


@router.get("/{slug}/availability")
def get_availability(
    slug: str,
    service_id: int,
    date: str,
    request: Request,
    _=Depends(_rate_limit),
):
    """Return available time slots for a service on a given date (YYYY-MM-DD).

    Simple implementation: returns hourly slots during a shop's next available window,
    filtered against already-booked appointments.
    """
    with SessionLocal() as session:
        page = _get_booking_page(session, slug)
        if not page or not page["is_enabled"]:
            raise HTTPException(status_code=404, detail="Booking page not found or disabled")

        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")

        # Validate advance window
        now = datetime.utcnow()
        min_start = now + timedelta(hours=page["min_advance_hours"])
        max_start = now + timedelta(days=page["max_advance_days"])

        if datetime(target_date.year, target_date.month, target_date.day) > max_start:
            return {"available_slots": [], "reason": "Too far in advance"}

        # Get service duration
        svc = session.execute(
            text("SELECT duration_minutes FROM shop_services WHERE id = :sid AND shop_id = :shop_id AND is_active = TRUE"),
            {"sid": service_id, "shop_id": page["shop_id"]},
        ).fetchone()
        if not svc:
            raise HTTPException(status_code=404, detail="Service not found")
        duration = int(svc[0] or 30)

        # Get booked slots for that day
        booked = session.execute(
            text("""
                SELECT scheduled_start, scheduled_end
                FROM appointments
                WHERE shop_id = :shop_id
                  AND DATE(scheduled_start) = :target_date
                  AND status NOT IN ('cancelled', 'no_show')
            """),
            {"shop_id": page["shop_id"], "target_date": target_date},
        ).fetchall()
        booked_ranges = [(r[0], r[1]) for r in booked]

        # Generate 9am–6pm slots, filter conflicts
        slots = []
        slot_start = datetime(target_date.year, target_date.month, target_date.day, 9, 0)
        day_end = datetime(target_date.year, target_date.month, target_date.day, 18, 0)

        while slot_start + timedelta(minutes=duration) <= day_end:
            slot_end = slot_start + timedelta(minutes=duration)

            # Skip if before min_start
            if slot_start < min_start:
                slot_start += timedelta(minutes=30)
                continue

            # Check for conflict
            conflict = any(
                not (slot_end <= bs or slot_start >= be)
                for bs, be in booked_ranges
                if bs and be
            )
            if not conflict:
                slots.append({
                    "start": slot_start.isoformat(),
                    "end": slot_end.isoformat(),
                    "label": slot_start.strftime("%I:%M %p"),
                })

            slot_start += timedelta(minutes=30)

    return {"available_slots": slots, "date": date, "service_id": service_id}


@router.post("/{slug}/book", status_code=201)
def create_booking(
    slug: str,
    body: BookingRequest,
    request: Request,
    _=Depends(_rate_limit),
):
    """Create a new appointment from the public booking page."""
    with SessionLocal() as session:
        page = _get_booking_page(session, slug)
        if not page or not page["is_enabled"]:
            raise HTTPException(status_code=404, detail="Booking page not found or disabled")

        shop_id = page["shop_id"]

        # Validate service belongs to shop
        svc = session.execute(
            text("SELECT id, name, duration_minutes, price_cents FROM shop_services WHERE id = :sid AND shop_id = :shop_id AND is_active = TRUE"),
            {"sid": body.service_id, "shop_id": shop_id},
        ).fetchone()
        if not svc:
            raise HTTPException(status_code=404, detail="Service not found")

        # Validate advance window
        now = datetime.utcnow()
        min_start = now + timedelta(hours=page["min_advance_hours"])
        max_start = now + timedelta(days=page["max_advance_days"])

        if body.scheduled_start < min_start:
            raise HTTPException(status_code=400, detail="Booking too soon. Please select a later time.")
        if body.scheduled_start > max_start:
            raise HTTPException(status_code=400, detail="Booking too far in advance.")

        # Require phone if configured
        if page["require_phone"] and not body.customer_phone:
            raise HTTPException(status_code=400, detail="Phone number is required for booking.")
        if page["require_email"] and not body.customer_email:
            raise HTTPException(status_code=400, detail="Email address is required for booking.")

        duration = int(svc[2] or 30)
        scheduled_end = body.scheduled_start + timedelta(minutes=duration)

        # Check for double-booking
        conflict = session.execute(
            text("""
                SELECT id FROM appointments
                WHERE shop_id = :shop_id
                  AND status NOT IN ('cancelled', 'no_show')
                  AND scheduled_start < :end AND scheduled_end > :start
                LIMIT 1
            """),
            {"shop_id": shop_id, "start": body.scheduled_start, "end": scheduled_end},
        ).fetchone()
        if conflict:
            raise HTTPException(status_code=409, detail="This time slot is no longer available. Please choose another.")

        # Resolve or create customer record
        customer_id = None
        if body.customer_phone or body.customer_email:
            existing = session.execute(
                text("""
                    SELECT id FROM shop_customers
                    WHERE shop_id = :shop_id
                      AND (phone = :phone OR email = :email)
                    LIMIT 1
                """),
                {
                    "shop_id": shop_id,
                    "phone": body.customer_phone or "__none__",
                    "email": body.customer_email or "__none__",
                },
            ).fetchone()
            if existing:
                customer_id = existing[0]
            else:
                new_cust = session.execute(
                    text("""
                        INSERT INTO shop_customers (shop_id, name, phone, email, created_at)
                        VALUES (:shop_id, :name, :phone, :email, NOW())
                        RETURNING id
                    """),
                    {
                        "shop_id": shop_id,
                        "name": body.customer_name,
                        "phone": body.customer_phone,
                        "email": body.customer_email,
                    },
                ).fetchone()
                if new_cust:
                    customer_id = new_cust[0]

        public_token = secrets.token_urlsafe(24)

        appt = session.execute(
            text("""
                INSERT INTO appointments
                    (shop_id, customer_id, service_id, employee_id,
                     customer_name, customer_phone, customer_email,
                     scheduled_start, scheduled_end, status,
                     service_cost, notes, booking_source, public_token, created_at, updated_at)
                VALUES
                    (:shop_id, :customer_id, :service_id, :employee_id,
                     :customer_name, :customer_phone, :customer_email,
                     :start, :end, 'scheduled',
                     :cost, :notes, 'public', :token, NOW(), NOW())
                RETURNING id
            """),
            {
                "shop_id": shop_id,
                "customer_id": customer_id,
                "service_id": body.service_id,
                "employee_id": body.employee_id,
                "customer_name": body.customer_name,
                "customer_phone": body.customer_phone,
                "customer_email": body.customer_email,
                "start": body.scheduled_start,
                "end": scheduled_end,
                "cost": (svc[3] or 0) / 100,
                "notes": body.notes,
                "token": public_token,
            },
        ).fetchone()
        session.commit()

        appt_id = appt[0]
        logger.info("public_booking: created appointment %d for shop %d", appt_id, shop_id)

    # Fire-and-forget: notify shop owner on Telegram (best-effort)
    try:
        from notification_dispatcher import dispatch
        with SessionLocal() as db:
            asyncio.get_event_loop().run_until_complete(
                dispatch(
                    shop_id=shop_id,
                    event_type="appointment_confirmation",
                    data={
                        "customer_name": body.customer_name,
                        "service_name": svc[1],
                        "shop_name": page["shop_name"],
                        "scheduled_time": body.scheduled_start.strftime("%A, %b %d at %I:%M %p"),
                    },
                    db=db,
                )
            )
    except Exception as exc:
        logger.warning("public_booking: owner notification failed (non-fatal): %s", exc)

    # Fire-and-forget: send confirmation email + SMS to customer (best-effort)
    _frontend_url = os.getenv("FRONTEND_URL", "https://zeroqwait.com").rstrip("/")
    _appt_status_url = f"{_frontend_url}/appointment-status/{public_token}"
    _appt_date = body.scheduled_start.strftime("%A, %B %-d %Y")
    _appt_time = body.scheduled_start.strftime("%-I:%M %p")
    if body.customer_email:
        try:
            from services.queue_email import send_appointment_confirmation_email
            asyncio.get_event_loop().run_until_complete(
                send_appointment_confirmation_email(
                    customer_email=body.customer_email,
                    customer_name=body.customer_name,
                    shop_name=page["shop_name"],
                    service_name=svc[1],
                    scheduled_start=body.scheduled_start.isoformat(),
                    scheduled_date=_appt_date,
                    scheduled_time=_appt_time,
                    status_url=_appt_status_url,
                )
            )
        except Exception as exc:
            logger.warning("public_booking: customer email failed (non-fatal): %s", exc)
    if body.customer_phone:
        try:
            from services.queue_sms import send_appointment_confirmation_sms
            asyncio.get_event_loop().run_until_complete(
                send_appointment_confirmation_sms(
                    customer_phone=body.customer_phone,
                    customer_name=body.customer_name,
                    shop_name=page["shop_name"],
                    service_name=svc[1],
                    scheduled_date=_appt_date,
                    scheduled_time=_appt_time,
                    status_url=_appt_status_url,
                )
            )
        except Exception as exc:
            logger.warning("public_booking: customer SMS failed (non-fatal): %s", exc)

    return {
        "appointment_id": appt_id,
        "public_token": public_token,
        "scheduled_start": body.scheduled_start.isoformat(),
        "scheduled_end": scheduled_end.isoformat(),
        "service_name": svc[1],
        "shop_name": page["shop_name"],
        "message": "Your booking is confirmed! We look forward to seeing you.",
    }


@router.get("/cancel/{public_token}")
def cancel_booking(public_token: str, request: Request, _=Depends(_rate_limit)):
    """Cancel an appointment using the public_token from the booking confirmation."""
    with SessionLocal() as session:
        appt = session.execute(
            text("""
                SELECT id, shop_id, status, customer_name, scheduled_start
                FROM appointments
                WHERE public_token = :token
            """),
            {"token": public_token},
        ).fetchone()

        if not appt:
            raise HTTPException(status_code=404, detail="Booking not found")
        if appt[2] in ("cancelled", "completed", "no_show"):
            raise HTTPException(status_code=409, detail=f"Booking is already {appt[2]}")

        session.execute(
            text("""
                UPDATE appointments
                SET status = 'cancelled', cancelled_at = NOW(), cancel_reason = 'customer_request'
                WHERE id = :appt_id
            """),
            {"appt_id": appt[0]},
        )
        session.commit()

    logger.info("public_booking: cancelled appointment %d via public token", appt[0])
    return {
        "message": "Your booking has been cancelled.",
        "appointment_id": appt[0],
        "customer_name": appt[3],
    }


@router.get("/status/{public_token}")
def get_appointment_status(public_token: str, request: Request, _=Depends(_rate_limit)):
    """Return public-facing appointment status by public_token (no auth required)."""
    with SessionLocal() as session:
        row = session.execute(
            text("""
                SELECT
                    a.id,
                    a.status,
                    a.customer_name,
                    a.scheduled_start,
                    a.scheduled_end,
                    ss.name  AS service_name,
                    s.name   AS shop_name,
                    s.slug   AS shop_slug
                FROM appointments a
                JOIN shops s ON s.id = a.shop_id
                LEFT JOIN shop_services ss ON ss.id = a.service_id
                WHERE a.public_token = :token
                LIMIT 1
            """),
            {"token": public_token},
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appt_id, status, customer_name, scheduled_start, scheduled_end, service_name, shop_name, shop_slug = row
    return {
        "appointment_id": appt_id,
        "status": status,
        "customer_name": customer_name,
        "scheduled_start": scheduled_start.isoformat() if scheduled_start else None,
        "scheduled_end": scheduled_end.isoformat() if scheduled_end else None,
        "service_name": service_name,
        "shop_name": shop_name,
        "shop_slug": shop_slug,
    }
