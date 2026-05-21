"""inventory_tools.py — Data-access layer for Inventory management.

All DB access uses SessionLocal() + text() (SQLAlchemy 2.0 compatible).
Quantities are stored as NUMERIC(10,2) — returned as float.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from database import SessionLocal

logger = logging.getLogger(__name__)


# ── Read operations ────────────────────────────────────────────────────────────

def list_inventory(shop_id: int, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Return all inventory items for a shop."""
    where_active = "" if include_inactive else " AND is_active = TRUE"
    with SessionLocal() as session:
        rows = session.execute(
            text(f"""
                SELECT id, shop_id, name, sku, category, unit,
                       current_stock, reorder_threshold, cost_per_unit,
                       retail_price_cents, supplier, is_active, created_at, updated_at,
                       CASE WHEN current_stock <= reorder_threshold THEN TRUE ELSE FALSE END AS is_low_stock
                FROM inventory_items
                WHERE shop_id = :shop_id{where_active}
                ORDER BY category NULLS LAST, name
            """),
            {"shop_id": shop_id},
        ).fetchall()
        return [_item_row(r) for r in rows]


def get_item(shop_id: int, item_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single inventory item."""
    with SessionLocal() as session:
        row = session.execute(
            text("""
                SELECT id, shop_id, name, sku, category, unit,
                       current_stock, reorder_threshold, cost_per_unit,
                       retail_price_cents, supplier, is_active, created_at, updated_at,
                       CASE WHEN current_stock <= reorder_threshold THEN TRUE ELSE FALSE END AS is_low_stock
                FROM inventory_items
                WHERE id = :item_id AND shop_id = :shop_id
            """),
            {"item_id": item_id, "shop_id": shop_id},
        ).fetchone()
        return _item_row(row) if row else None


def get_low_stock_alerts(shop_id: int) -> List[Dict[str, Any]]:
    """Return items at or below their reorder threshold."""
    with SessionLocal() as session:
        rows = session.execute(
            text("""
                SELECT id, name, unit, current_stock, reorder_threshold, supplier
                FROM inventory_items
                WHERE shop_id = :shop_id
                  AND is_active = TRUE
                  AND current_stock <= reorder_threshold
                ORDER BY (reorder_threshold - current_stock) DESC
            """),
            {"shop_id": shop_id},
        ).fetchall()
        return [
            {
                "id": r[0],
                "name": r[1],
                "unit": r[2],
                "current_stock": float(r[3] or 0),
                "reorder_threshold": float(r[4] or 0),
                "shortfall": float((r[4] or 0) - (r[3] or 0)),
                "supplier": r[5],
            }
            for r in rows
        ]


def get_cogs_report(shop_id: int, since_date: Optional[str] = None) -> Dict[str, Any]:
    """Cost of Goods Sold report — total cost of service_deduction + sale movements."""
    date_filter = "AND created_at >= :since" if since_date else ""
    params: Dict[str, Any] = {"shop_id": shop_id}
    if since_date:
        params["since"] = since_date

    with SessionLocal() as session:
        row = session.execute(
            text(f"""
                SELECT
                    COALESCE(SUM(ABS(quantity) * COALESCE(unit_cost, 0)), 0) AS total_cogs,
                    COUNT(*) AS total_movements
                FROM inventory_movements
                WHERE shop_id = :shop_id
                  AND movement_type IN ('service_deduction', 'sale')
                  AND quantity < 0
                  {date_filter}
            """),
            params,
        ).fetchone()
        return {
            "total_cogs": float(row[0] or 0),
            "total_movements": int(row[1] or 0),
            "since": since_date,
        }


def get_movement_history(shop_id: int, item_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Last N movements for a specific item."""
    with SessionLocal() as session:
        rows = session.execute(
            text("""
                SELECT m.id, m.movement_type, m.quantity, m.stock_after,
                       m.notes, m.appointment_id, m.created_at,
                       u.username AS created_by_username
                FROM inventory_movements m
                LEFT JOIN users u ON u.id = m.created_by
                WHERE m.shop_id = :shop_id AND m.item_id = :item_id
                ORDER BY m.created_at DESC
                LIMIT :lim
            """),
            {"shop_id": shop_id, "item_id": item_id, "lim": limit},
        ).fetchall()
        return [
            {
                "id": r[0],
                "movement_type": r[1],
                "quantity": float(r[2] or 0),
                "stock_after": float(r[3]) if r[3] is not None else None,
                "notes": r[4],
                "appointment_id": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
                "created_by": r[7],
            }
            for r in rows
        ]


# ── Write operations ───────────────────────────────────────────────────────────

def add_item(
    shop_id: int,
    name: str,
    unit: str = "piece",
    category: Optional[str] = None,
    sku: Optional[str] = None,
    initial_stock: float = 0.0,
    reorder_threshold: float = 0.0,
    cost_per_unit: Optional[float] = None,
    retail_price_cents: Optional[int] = None,
    supplier: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new inventory item. Returns the created record."""
    with SessionLocal() as session:
        row = session.execute(
            text("""
                INSERT INTO inventory_items
                    (shop_id, name, sku, category, unit, current_stock,
                     reorder_threshold, cost_per_unit, retail_price_cents,
                     supplier, is_active, created_at, updated_at)
                VALUES
                    (:shop_id, :name, :sku, :category, :unit, :stock,
                     :threshold, :cost, :retail,
                     :supplier, TRUE, NOW(), NOW())
                RETURNING id, shop_id, name, sku, category, unit,
                          current_stock, reorder_threshold, cost_per_unit,
                          retail_price_cents, supplier, is_active, created_at, updated_at,
                          CASE WHEN current_stock <= reorder_threshold THEN TRUE ELSE FALSE END AS is_low_stock
            """),
            {
                "shop_id": shop_id,
                "name": name,
                "sku": sku,
                "category": category,
                "unit": unit,
                "stock": initial_stock,
                "threshold": reorder_threshold,
                "cost": cost_per_unit,
                "retail": retail_price_cents,
                "supplier": supplier,
            },
        ).fetchone()
        session.commit()
        return _item_row(row)


def _record_movement(
    session,
    shop_id: int,
    item_id: int,
    movement_type: str,
    quantity: float,
    notes: Optional[str],
    appointment_id: Optional[int],
    created_by: Optional[int],
    unit_cost: Optional[float],
) -> float:
    """Internal helper: update current_stock and insert movement row. Returns new stock."""
    new_stock_row = session.execute(
        text("""
            UPDATE inventory_items
            SET current_stock = current_stock + :qty,
                updated_at = NOW()
            WHERE id = :item_id AND shop_id = :shop_id
            RETURNING current_stock
        """),
        {"qty": quantity, "item_id": item_id, "shop_id": shop_id},
    ).fetchone()
    if not new_stock_row:
        raise ValueError(f"Inventory item {item_id} not found in shop {shop_id}")
    new_stock = float(new_stock_row[0])

    session.execute(
        text("""
            INSERT INTO inventory_movements
                (shop_id, item_id, movement_type, quantity, stock_after,
                 unit_cost, notes, appointment_id, created_by, created_at)
            VALUES
                (:shop_id, :item_id, :mvt, :qty, :stock_after,
                 :unit_cost, :notes, :appt, :created_by, NOW())
        """),
        {
            "shop_id": shop_id,
            "item_id": item_id,
            "mvt": movement_type,
            "qty": quantity,
            "stock_after": new_stock,
            "unit_cost": unit_cost,
            "notes": notes,
            "appt": appointment_id,
            "created_by": created_by,
        },
    )
    return new_stock


def record_restock(
    shop_id: int,
    item_id: int,
    quantity: float,
    unit_cost: Optional[float] = None,
    notes: Optional[str] = None,
    created_by: Optional[int] = None,
) -> Dict[str, Any]:
    """Add stock (positive quantity)."""
    if quantity <= 0:
        raise ValueError("Restock quantity must be positive")
    with SessionLocal() as session:
        new_stock = _record_movement(
            session, shop_id, item_id, "restock", quantity,
            notes, None, created_by, unit_cost,
        )
        session.commit()
    return {"item_id": item_id, "new_stock": new_stock, "movement": "restock", "quantity_added": quantity}


def record_usage(
    shop_id: int,
    item_id: int,
    quantity: float,
    notes: Optional[str] = None,
    appointment_id: Optional[int] = None,
    created_by: Optional[int] = None,
) -> Dict[str, Any]:
    """Record internal usage (negative quantity)."""
    if quantity <= 0:
        raise ValueError("Usage quantity must be positive")
    with SessionLocal() as session:
        new_stock = _record_movement(
            session, shop_id, item_id, "usage", -quantity,
            notes, appointment_id, created_by, None,
        )
        session.commit()
    return {"item_id": item_id, "new_stock": new_stock, "movement": "usage", "quantity_used": quantity}


def record_adjustment(
    shop_id: int,
    item_id: int,
    quantity: float,
    notes: Optional[str] = None,
    created_by: Optional[int] = None,
) -> Dict[str, Any]:
    """Manual stock adjustment (positive or negative)."""
    with SessionLocal() as session:
        new_stock = _record_movement(
            session, shop_id, item_id, "adjustment", quantity,
            notes, None, created_by, None,
        )
        session.commit()
    return {"item_id": item_id, "new_stock": new_stock, "movement": "adjustment", "quantity_delta": quantity}


def deduct_service_supplies(
    shop_id: int,
    service_id: int,
    appointment_id: Optional[int] = None,
    created_by: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Deduct supplies_used amounts defined on the service from inventory.

    Returns list of deduction results, one per supply.
    """
    import json as _json
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT supplies_used FROM shop_services WHERE id = :sid AND shop_id = :shop_id"),
            {"sid": service_id, "shop_id": shop_id},
        ).fetchone()

    if not row:
        return []
    raw = row[0]
    supplies: List[Dict[str, Any]] = []
    if isinstance(raw, str):
        try:
            supplies = _json.loads(raw)
        except Exception:
            supplies = []
    elif isinstance(raw, list):
        supplies = raw

    results = []
    for supply in supplies:
        item_id = supply.get("item_id")
        qty = float(supply.get("quantity", 0))
        if not item_id or qty <= 0:
            continue
        try:
            result = record_usage(
                shop_id, item_id, qty,
                notes=f"Auto-deducted for service #{service_id}",
                appointment_id=appointment_id,
                created_by=created_by,
            )
            result["supply_item_id"] = item_id
            results.append(result)
        except Exception as exc:
            logger.warning("deduct_service_supplies: item %d failed: %s", item_id, exc)
    return results


# ── Helpers ────────────────────────────────────────────────────────────────────

def _item_row(row) -> Dict[str, Any]:
    if row is None:
        return {}
    keys = [
        "id", "shop_id", "name", "sku", "category", "unit",
        "current_stock", "reorder_threshold", "cost_per_unit",
        "retail_price_cents", "supplier", "is_active", "created_at", "updated_at",
        "is_low_stock",
    ]
    d: Dict[str, Any] = {}
    for i, k in enumerate(keys):
        try:
            val = row[i]
        except (IndexError, KeyError):
            try:
                val = getattr(row, k)
            except AttributeError:
                val = None
        if k in ("current_stock", "reorder_threshold", "cost_per_unit") and val is not None:
            val = float(val)
        d[k] = val
    return d
