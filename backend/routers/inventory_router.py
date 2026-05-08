"""inventory_router.py — REST endpoints for Inventory management."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from database import SessionLocal
from shared.auth_utils import get_current_user
from agents.tools import inventory_tools

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


# ── Helper ─────────────────────────────────────────────────────────────────────

def _assert_owner(shop_id: int, current_user: dict) -> None:
    from sqlalchemy import text
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT owner_id FROM shops WHERE id = :shop_id"),
            {"shop_id": shop_id},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Shop not found")
    if row[0] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not your shop")


# ── Request models ─────────────────────────────────────────────────────────────

class AddItemRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    unit: str = Field("piece", max_length=20)
    category: Optional[str] = None
    sku: Optional[str] = None
    initial_stock: float = Field(0.0, ge=0)
    reorder_threshold: float = Field(0.0, ge=0)
    cost_per_unit: Optional[float] = Field(None, ge=0)
    retail_price_cents: Optional[int] = Field(None, ge=0)
    supplier: Optional[str] = None


class MovementRequest(BaseModel):
    quantity: float = Field(..., gt=0)
    notes: Optional[str] = None
    unit_cost: Optional[float] = None  # for restock only
    appointment_id: Optional[int] = None  # for usage only


class AdjustmentRequest(BaseModel):
    quantity: float  # positive or negative
    notes: Optional[str] = None


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/shop/{shop_id}")
def list_inventory(
    shop_id: int,
    include_inactive: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    return {"items": inventory_tools.list_inventory(shop_id, include_inactive=include_inactive)}


@router.get("/shop/{shop_id}/alerts")
def low_stock_alerts(
    shop_id: int,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    alerts = inventory_tools.get_low_stock_alerts(shop_id)
    return {"alerts": alerts, "count": len(alerts)}


@router.get("/shop/{shop_id}/cogs")
def cogs_report(
    shop_id: int,
    since: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    return inventory_tools.get_cogs_report(shop_id, since)


@router.get("/shop/{shop_id}/{item_id}")
def get_item(
    shop_id: int,
    item_id: int,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    item = inventory_tools.get_item(shop_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/shop/{shop_id}/{item_id}/history")
def item_history(
    shop_id: int,
    item_id: int,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    return {"movements": inventory_tools.get_movement_history(shop_id, item_id, limit)}


@router.post("/shop/{shop_id}", status_code=201)
def add_item(
    shop_id: int,
    body: AddItemRequest,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    try:
        item = inventory_tools.add_item(
            shop_id=shop_id,
            name=body.name,
            unit=body.unit,
            category=body.category,
            sku=body.sku,
            initial_stock=body.initial_stock,
            reorder_threshold=body.reorder_threshold,
            cost_per_unit=body.cost_per_unit,
            retail_price_cents=body.retail_price_cents,
            supplier=body.supplier,
        )
        return item
    except Exception as exc:
        logger.exception("add_item failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to add inventory item")


@router.post("/shop/{shop_id}/{item_id}/restock")
def record_restock(
    shop_id: int,
    item_id: int,
    body: MovementRequest,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    try:
        return inventory_tools.record_restock(
            shop_id, item_id, body.quantity,
            unit_cost=body.unit_cost, notes=body.notes,
            created_by=current_user["id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/shop/{shop_id}/{item_id}/usage")
def record_usage(
    shop_id: int,
    item_id: int,
    body: MovementRequest,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    try:
        return inventory_tools.record_usage(
            shop_id, item_id, body.quantity,
            notes=body.notes,
            appointment_id=body.appointment_id,
            created_by=current_user["id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/shop/{shop_id}/{item_id}/adjust")
def record_adjustment(
    shop_id: int,
    item_id: int,
    body: AdjustmentRequest,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    try:
        return inventory_tools.record_adjustment(
            shop_id, item_id, body.quantity,
            notes=body.notes, created_by=current_user["id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
