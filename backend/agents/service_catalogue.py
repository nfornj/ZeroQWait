"""service_catalogue.py — Data access layer for the Service Catalogue.

All DB access uses SessionLocal() + text() (SQLAlchemy 2.0 compatible).
All amounts are stored in cents (integer) and returned in cents.
HST is 13% (Ontario) — applied only on hst_applicable services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from database import SessionLocal

logger = logging.getLogger(__name__)

HST_RATE = 0.13  # Ontario HST (13%)

# ── Default seed services per vertical ────────────────────────────────────────
VERTICAL_DEFAULTS: Dict[str, List[Dict[str, Any]]] = {
    "barbershop": [
        {"name": "Haircut", "duration_minutes": 30, "price_cents": 3000, "category": "hair", "hst_applicable": False},
        {"name": "Beard Trim", "duration_minutes": 20, "price_cents": 2000, "category": "beard", "hst_applicable": False},
        {"name": "Haircut + Beard", "duration_minutes": 45, "price_cents": 4500, "category": "combo", "hst_applicable": False},
        {"name": "Shape Up / Lineup", "duration_minutes": 20, "price_cents": 2500, "category": "hair", "hst_applicable": False},
        {"name": "Kids Haircut (12 & under)", "duration_minutes": 20, "price_cents": 2000, "category": "hair", "hst_applicable": False},
        {"name": "Hot Towel Shave", "duration_minutes": 30, "price_cents": 3500, "category": "beard", "hst_applicable": False},
    ],
    "salon": [
        {"name": "Women's Haircut & Blowout", "duration_minutes": 60, "price_cents": 6500, "category": "hair", "hst_applicable": False},
        {"name": "Men's Haircut", "duration_minutes": 30, "price_cents": 3500, "category": "hair", "hst_applicable": False},
        {"name": "Full Colour", "duration_minutes": 120, "price_cents": 12000, "category": "colour", "hst_applicable": True},
        {"name": "Highlights (Full Head)", "duration_minutes": 150, "price_cents": 14000, "category": "colour", "hst_applicable": True},
        {"name": "Keratin Treatment", "duration_minutes": 180, "price_cents": 20000, "category": "treatment", "hst_applicable": True},
        {"name": "Blowout", "duration_minutes": 45, "price_cents": 4500, "category": "style", "hst_applicable": False},
    ],
    "nail_salon": [
        {"name": "Basic Manicure", "duration_minutes": 30, "price_cents": 2500, "category": "manicure", "hst_applicable": True},
        {"name": "Gel Manicure", "duration_minutes": 45, "price_cents": 3500, "category": "manicure", "hst_applicable": True},
        {"name": "Basic Pedicure", "duration_minutes": 45, "price_cents": 3500, "category": "pedicure", "hst_applicable": True},
        {"name": "Spa Pedicure", "duration_minutes": 60, "price_cents": 4500, "category": "pedicure", "hst_applicable": True},
        {"name": "Acrylic Full Set", "duration_minutes": 90, "price_cents": 5500, "category": "enhancements", "hst_applicable": True},
        {"name": "Gel Polish Change", "duration_minutes": 30, "price_cents": 2500, "category": "manicure", "hst_applicable": True},
    ],
}


# ── Read operations ────────────────────────────────────────────────────────────

def list_services(shop_id: int, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Return all services for a shop, optionally including inactive ones."""
    with SessionLocal() as session:
        where_active = "" if include_inactive else " AND is_active = TRUE"
        rows = session.execute(
            text(f"""
                SELECT id, shop_id, name, description, duration_minutes,
                       price_cents, hst_applicable, staff_ids, supplies_used,
                       category, is_active, created_at
                FROM shop_services
                WHERE shop_id = :shop_id{where_active}
                ORDER BY category NULLS LAST, name
            """),
            {"shop_id": shop_id},
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def get_service(shop_id: int, service_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single service by ID (must belong to shop)."""
    with SessionLocal() as session:
        row = session.execute(
            text("""
                SELECT id, shop_id, name, description, duration_minutes,
                       price_cents, hst_applicable, staff_ids, supplies_used,
                       category, is_active, created_at
                FROM shop_services
                WHERE id = :service_id AND shop_id = :shop_id
            """),
            {"service_id": service_id, "shop_id": shop_id},
        ).fetchone()
        return _row_to_dict(row) if row else None


def get_services_for_public(shop_id: int) -> List[Dict[str, Any]]:
    """Return active services visible to customers booking online — omit staff/supply details."""
    with SessionLocal() as session:
        rows = session.execute(
            text("""
                SELECT id, name, description, duration_minutes,
                       price_cents, hst_applicable, category
                FROM shop_services
                WHERE shop_id = :shop_id AND is_active = TRUE
                ORDER BY category NULLS LAST, name
            """),
            {"shop_id": shop_id},
        ).fetchall()
        return [
            {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "duration_minutes": r[3],
                "price_cents": r[4],
                "price_display": _format_price(r[4]),
                "hst_applicable": r[5],
                "category": r[6],
            }
            for r in rows
        ]


# ── Write operations ───────────────────────────────────────────────────────────

def create_service(
    shop_id: int,
    name: str,
    duration_minutes: int = 30,
    price_cents: int = 0,
    description: Optional[str] = None,
    hst_applicable: bool = True,
    category: Optional[str] = None,
    staff_ids: Optional[List[int]] = None,
    supplies_used: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create a new service for the shop. Returns the created record."""
    import json as _json
    staff = staff_ids or []
    supplies = supplies_used or []
    with SessionLocal() as session:
        row = session.execute(
            text("""
                INSERT INTO shop_services
                    (shop_id, name, description, duration_minutes, price_cents,
                     hst_applicable, category, staff_ids, supplies_used, is_active, created_at)
                VALUES
                    (:shop_id, :name, :desc, :dur, :price,
                     :hst, :category, :staff_ids, :supplies, TRUE, NOW())
                RETURNING id, shop_id, name, description, duration_minutes,
                          price_cents, hst_applicable, staff_ids, supplies_used,
                          category, is_active, created_at
            """),
            {
                "shop_id": shop_id,
                "name": name,
                "desc": description,
                "dur": duration_minutes,
                "price": price_cents,
                "hst": hst_applicable,
                "category": category,
                "staff_ids": staff,
                "supplies": _json.dumps(supplies),
            },
        ).fetchone()
        session.commit()
        return _row_to_dict(row)


def update_service(shop_id: int, service_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Partial update of a service. Only provided fields are changed."""
    import json as _json
    allowed = {
        "name", "description", "duration_minutes", "price_cents",
        "hst_applicable", "category", "staff_ids", "supplies_used", "is_active",
    }
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return get_service(shop_id, service_id)

    set_clauses = []
    params: Dict[str, Any] = {"service_id": service_id, "shop_id": shop_id}
    for k, v in fields.items():
        set_clauses.append(f"{k} = :{k}")
        if k == "supplies_used" and isinstance(v, (list, dict)):
            params[k] = _json.dumps(v)
        elif k == "staff_ids" and isinstance(v, list):
            params[k] = v
        else:
            params[k] = v

    with SessionLocal() as session:
        row = session.execute(
            text(f"""
                UPDATE shop_services
                SET {', '.join(set_clauses)}
                WHERE id = :service_id AND shop_id = :shop_id
                RETURNING id, shop_id, name, description, duration_minutes,
                          price_cents, hst_applicable, staff_ids, supplies_used,
                          category, is_active, created_at
            """),
            params,
        ).fetchone()
        session.commit()
        return _row_to_dict(row) if row else None


def deactivate_service(shop_id: int, service_id: int) -> bool:
    """Soft-delete a service (sets is_active = FALSE). Returns True if found and updated."""
    with SessionLocal() as session:
        result = session.execute(
            text("""
                UPDATE shop_services
                SET is_active = FALSE
                WHERE id = :service_id AND shop_id = :shop_id
            """),
            {"service_id": service_id, "shop_id": shop_id},
        )
        session.commit()
        return (result.rowcount or 0) > 0


def seed_default_services(shop_id: int, shop_type: str) -> List[Dict[str, Any]]:
    """Seed the catalogue with sensible defaults for the shop vertical.

    Idempotent — does nothing if the shop already has services.
    Returns the list of newly created services (empty if already seeded).
    """
    # Check if shop already has services
    with SessionLocal() as session:
        count = session.execute(
            text("SELECT COUNT(*) FROM shop_services WHERE shop_id = :shop_id"),
            {"shop_id": shop_id},
        ).scalar()
        if (count or 0) > 0:
            return []

    vertical_key = _normalize_vertical(shop_type)
    defaults = VERTICAL_DEFAULTS.get(vertical_key, VERTICAL_DEFAULTS["barbershop"])

    created = []
    for svc in defaults:
        try:
            record = create_service(
                shop_id=shop_id,
                name=svc["name"],
                duration_minutes=svc.get("duration_minutes", 30),
                price_cents=svc.get("price_cents", 0),
                hst_applicable=svc.get("hst_applicable", True),
                category=svc.get("category"),
            )
            created.append(record)
        except Exception as exc:
            logger.warning("seed_default_services: failed to create '%s': %s", svc["name"], exc)

    logger.info("seed_default_services: seeded %d services for shop %d (%s)", len(created), shop_id, vertical_key)
    return created


def estimate_wait_time(shop_id: int, service_id: Optional[int] = None) -> Dict[str, Any]:
    """Estimate current queue wait based on people ahead and average service duration."""
    with SessionLocal() as session:
        # Count people currently queued
        waiting = session.execute(
            text("""
                SELECT COUNT(qi.id)
                FROM queues q
                JOIN queue_items qi ON qi.queue_id = q.id
                WHERE q.shop_id = :shop_id
                  AND q.is_active = TRUE
                  AND qi.status IN ('waiting', 'called')
            """),
            {"shop_id": shop_id},
        ).scalar() or 0

        # Get service duration
        avg_duration: int = 30
        if service_id:
            dur = session.execute(
                text("SELECT duration_minutes FROM shop_services WHERE id = :id AND shop_id = :shop_id"),
                {"id": service_id, "shop_id": shop_id},
            ).scalar()
            if dur:
                avg_duration = int(dur)
        else:
            dur = session.execute(
                text("SELECT AVG(duration_minutes) FROM shop_services WHERE shop_id = :shop_id AND is_active = TRUE"),
                {"shop_id": shop_id},
            ).scalar()
            if dur:
                avg_duration = int(dur)

    estimated_minutes = int(waiting) * avg_duration
    return {
        "people_waiting": int(waiting),
        "avg_service_minutes": avg_duration,
        "estimated_wait_minutes": estimated_minutes,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> Dict[str, Any]:
    import json as _json
    if row is None:
        return {}
    keys = [
        "id", "shop_id", "name", "description", "duration_minutes",
        "price_cents", "hst_applicable", "staff_ids", "supplies_used",
        "category", "is_active", "created_at",
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
        if k == "supplies_used" and isinstance(val, str):
            try:
                val = _json.loads(val)
            except Exception:
                val = []
        d[k] = val

    # Convenience: add price_display and hst_amount
    pc = d.get("price_cents") or 0
    d["price_display"] = _format_price(pc)
    if d.get("hst_applicable"):
        d["hst_amount_cents"] = round(pc * HST_RATE)
        d["total_with_hst_cents"] = pc + d["hst_amount_cents"]
    else:
        d["hst_amount_cents"] = 0
        d["total_with_hst_cents"] = pc

    return d


def _format_price(price_cents: Optional[int]) -> str:
    if price_cents is None:
        return "Price TBD"
    dollars = price_cents / 100
    return f"${dollars:.2f}"


def _normalize_vertical(shop_type: str) -> str:
    t = (shop_type or "").lower()
    if any(k in t for k in ("barber", "fade", "cuts", "cut")):
        return "barbershop"
    if any(k in t for k in ("salon", "hair", "beauty", "stylist")):
        return "salon"
    if any(k in t for k in ("nail", "mani", "pedi")):
        return "nail_salon"
    return "barbershop"
