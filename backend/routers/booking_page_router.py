"""booking_page_router.py — Owner management of public_booking_pages."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from database import SessionLocal
from shared.auth_utils import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/booking-page", tags=["booking-page"])


def _assert_owner(shop_id: int, current_user: dict) -> None:
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT owner_id FROM shops WHERE id = :shop_id"),
            {"shop_id": shop_id},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Shop not found")
    if row[0] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not your shop")


class BookingPageUpsert(BaseModel):
    is_enabled: bool = True
    title: Optional[str] = None
    welcome_message: Optional[str] = None
    max_advance_days: int = Field(30, ge=1, le=365)
    min_advance_hours: int = Field(1, ge=0, le=72)
    require_phone: bool = True
    require_email: bool = False


@router.get("/shop/{shop_id}")
def get_booking_page(
    shop_id: int,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    with SessionLocal() as session:
        row = session.execute(
            text("""
                SELECT id, shop_id, is_enabled, title, welcome_message,
                       max_advance_days, min_advance_hours, require_phone, require_email,
                       created_at, updated_at
                FROM public_booking_pages
                WHERE shop_id = :shop_id
            """),
            {"shop_id": shop_id},
        ).fetchone()
        if not row:
            return {"exists": False, "shop_id": shop_id}
        return {
            "id": row[0], "shop_id": row[1], "is_enabled": row[2],
            "title": row[3], "welcome_message": row[4],
            "max_advance_days": row[5], "min_advance_hours": row[6],
            "require_phone": row[7], "require_email": row[8],
        }


@router.put("/shop/{shop_id}")
def upsert_booking_page(
    shop_id: int,
    body: BookingPageUpsert,
    current_user: dict = Depends(get_current_user),
):
    """Create or update the public booking page for a shop."""
    _assert_owner(shop_id, current_user)
    with SessionLocal() as session:
        row = session.execute(
            text("""
                INSERT INTO public_booking_pages
                    (shop_id, is_enabled, title, welcome_message,
                     max_advance_days, min_advance_hours, require_phone, require_email,
                     created_at, updated_at)
                VALUES
                    (:shop_id, :enabled, :title, :welcome,
                     :max_days, :min_hours, :req_phone, :req_email,
                     NOW(), NOW())
                ON CONFLICT (shop_id) DO UPDATE SET
                    is_enabled      = EXCLUDED.is_enabled,
                    title           = EXCLUDED.title,
                    welcome_message = EXCLUDED.welcome_message,
                    max_advance_days = EXCLUDED.max_advance_days,
                    min_advance_hours = EXCLUDED.min_advance_hours,
                    require_phone   = EXCLUDED.require_phone,
                    require_email   = EXCLUDED.require_email,
                    updated_at      = NOW()
                RETURNING id, shop_id, is_enabled
            """),
            {
                "shop_id": shop_id,
                "enabled": body.is_enabled,
                "title": body.title,
                "welcome": body.welcome_message,
                "max_days": body.max_advance_days,
                "min_hours": body.min_advance_hours,
                "req_phone": body.require_phone,
                "req_email": body.require_email,
            },
        ).fetchone()
        session.commit()

        # Get the shop slug for the booking URL
        slug_row = session.execute(
            text("SELECT slug FROM shops WHERE id = :shop_id"),
            {"shop_id": shop_id},
        ).fetchone()

    slug = slug_row[0] if slug_row else None
    return {
        "id": row[0],
        "shop_id": row[1],
        "is_enabled": row[2],
        "booking_url": f"/book/{slug}" if slug else None,
    }
