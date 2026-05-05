"""services_router.py — REST endpoints for the Service Catalogue.

All write endpoints require owner authentication and ownership of the shop.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from database import SessionLocal
from shared.auth_utils import get_current_user
from agents import service_catalogue as svc_cat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/services", tags=["services"])


# ── Request / Response models ──────────────────────────────────────────────────

class ServiceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    duration_minutes: int = Field(30, ge=5, le=480)
    price_cents: int = Field(0, ge=0)
    description: Optional[str] = None
    hst_applicable: bool = True
    category: Optional[str] = None
    staff_ids: Optional[List[int]] = None
    supplies_used: Optional[List[Dict[str, Any]]] = None


class ServiceUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    duration_minutes: Optional[int] = Field(None, ge=5, le=480)
    price_cents: Optional[int] = Field(None, ge=0)
    description: Optional[str] = None
    hst_applicable: Optional[bool] = None
    category: Optional[str] = None
    staff_ids: Optional[List[int]] = None
    supplies_used: Optional[List[Dict[str, Any]]] = None
    is_active: Optional[bool] = None


# ── Helper: assert owner of shop ──────────────────────────────────────────────

def _assert_owner(shop_id: int, current_user: dict) -> None:
    with SessionLocal() as session:
        from sqlalchemy import text
        row = session.execute(
            text("SELECT owner_id FROM shops WHERE id = :shop_id"),
            {"shop_id": shop_id},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Shop not found")
    if row[0] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not your shop")


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/shop/{shop_id}")
def list_services(
    shop_id: int,
    include_inactive: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    """List all services for a shop (owner view — includes inactive when requested)."""
    _assert_owner(shop_id, current_user)
    return {"services": svc_cat.list_services(shop_id, include_inactive=include_inactive)}


@router.get("/shop/{shop_id}/public")
def list_services_public(shop_id: int):
    """Public endpoint — active services visible to customers. No auth required."""
    return {"services": svc_cat.get_services_for_public(shop_id)}


@router.get("/shop/{shop_id}/{service_id}")
def get_service(
    shop_id: int,
    service_id: int,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    service = svc_cat.get_service(shop_id, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.post("/shop/{shop_id}", status_code=201)
def create_service(
    shop_id: int,
    body: ServiceCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    try:
        service = svc_cat.create_service(
            shop_id=shop_id,
            name=body.name,
            duration_minutes=body.duration_minutes,
            price_cents=body.price_cents,
            description=body.description,
            hst_applicable=body.hst_applicable,
            category=body.category,
            staff_ids=body.staff_ids,
            supplies_used=body.supplies_used,
        )
        return service
    except Exception as exc:
        logger.exception("create_service failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create service")


@router.patch("/shop/{shop_id}/{service_id}")
def update_service(
    shop_id: int,
    service_id: int,
    body: ServiceUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    updates = body.model_dump(exclude_none=True)
    result = svc_cat.update_service(shop_id, service_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Service not found")
    return result


@router.delete("/shop/{shop_id}/{service_id}", status_code=204)
def deactivate_service(
    shop_id: int,
    service_id: int,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    ok = svc_cat.deactivate_service(shop_id, service_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Service not found")


@router.post("/shop/{shop_id}/seed", status_code=201)
def seed_services(
    shop_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Seed default services for the shop's vertical. No-op if services already exist."""
    _assert_owner(shop_id, current_user)
    with SessionLocal() as session:
        from sqlalchemy import text
        shop_row = session.execute(
            text("SELECT shop_type FROM shops WHERE id = :shop_id"),
            {"shop_id": shop_id},
        ).fetchone()
    if not shop_row:
        raise HTTPException(status_code=404, detail="Shop not found")
    created = svc_cat.seed_default_services(shop_id, shop_row[0] or "barbershop")
    return {"seeded": len(created), "services": created}


@router.get("/shop/{shop_id}/wait-time")
def estimate_wait(
    shop_id: int,
    service_id: Optional[int] = Query(None),
):
    """Public — estimated wait time in minutes for this shop (no auth needed)."""
    return svc_cat.estimate_wait_time(shop_id, service_id)
