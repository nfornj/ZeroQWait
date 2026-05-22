from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlalchemy import text

from database import SessionLocal


_VERTICAL_INVENTORY_ITEMS: Dict[str, list[Dict[str, Any]]] = {
    "barbershop": [
        {"name": "Barber Shampoo", "unit": "ml", "category": "consumable", "initial_stock": 5000, "reorder_threshold": 1000, "cost_per_unit": 0.02},
        {"name": "Styling Product", "unit": "ml", "category": "consumable", "initial_stock": 3000, "reorder_threshold": 600, "cost_per_unit": 0.04},
        {"name": "Beard Oil", "unit": "ml", "category": "consumable", "initial_stock": 1500, "reorder_threshold": 300, "cost_per_unit": 0.06},
        {"name": "Shave Cream", "unit": "ml", "category": "consumable", "initial_stock": 3000, "reorder_threshold": 500, "cost_per_unit": 0.03},
        {"name": "Aftershave", "unit": "ml", "category": "consumable", "initial_stock": 2000, "reorder_threshold": 400, "cost_per_unit": 0.05},
        {"name": "Hair Color", "unit": "g", "category": "consumable", "initial_stock": 2000, "reorder_threshold": 400, "cost_per_unit": 0.08},
    ],
    "salon": [
        {"name": "Salon Shampoo", "unit": "ml", "category": "consumable", "initial_stock": 8000, "reorder_threshold": 1500, "cost_per_unit": 0.02},
        {"name": "Salon Conditioner", "unit": "ml", "category": "consumable", "initial_stock": 8000, "reorder_threshold": 1500, "cost_per_unit": 0.02},
        {"name": "Styling Product", "unit": "ml", "category": "consumable", "initial_stock": 4000, "reorder_threshold": 800, "cost_per_unit": 0.04},
        {"name": "Heat Protectant", "unit": "ml", "category": "consumable", "initial_stock": 2500, "reorder_threshold": 500, "cost_per_unit": 0.05},
        {"name": "Hair Color", "unit": "g", "category": "consumable", "initial_stock": 5000, "reorder_threshold": 800, "cost_per_unit": 0.09},
        {"name": "Developer", "unit": "ml", "category": "consumable", "initial_stock": 6000, "reorder_threshold": 1000, "cost_per_unit": 0.03},
        {"name": "Lightener", "unit": "g", "category": "consumable", "initial_stock": 5000, "reorder_threshold": 800, "cost_per_unit": 0.07},
        {"name": "Toner", "unit": "ml", "category": "consumable", "initial_stock": 2500, "reorder_threshold": 500, "cost_per_unit": 0.06},
        {"name": "Keratin Solution", "unit": "ml", "category": "consumable", "initial_stock": 3000, "reorder_threshold": 500, "cost_per_unit": 0.12},
        {"name": "Deep Conditioning Mask", "unit": "ml", "category": "consumable", "initial_stock": 2500, "reorder_threshold": 400, "cost_per_unit": 0.07},
        {"name": "Scalp Treatment Serum", "unit": "ml", "category": "consumable", "initial_stock": 1500, "reorder_threshold": 250, "cost_per_unit": 0.11},
        {"name": "Perm Solution", "unit": "ml", "category": "consumable", "initial_stock": 2000, "reorder_threshold": 400, "cost_per_unit": 0.08},
        {"name": "Relaxer Cream", "unit": "ml", "category": "consumable", "initial_stock": 2000, "reorder_threshold": 400, "cost_per_unit": 0.08},
        {"name": "Acrylic Powder", "unit": "g", "category": "consumable", "initial_stock": 3000, "reorder_threshold": 500, "cost_per_unit": 0.05},
        {"name": "Gel Polish", "unit": "ml", "category": "consumable", "initial_stock": 2000, "reorder_threshold": 400, "cost_per_unit": 0.05},
        {"name": "Nail Polish", "unit": "ml", "category": "consumable", "initial_stock": 2000, "reorder_threshold": 400, "cost_per_unit": 0.03},
        {"name": "Dip Powder", "unit": "g", "category": "consumable", "initial_stock": 2000, "reorder_threshold": 400, "cost_per_unit": 0.05},
        {"name": "Nail Glue", "unit": "ml", "category": "consumable", "initial_stock": 1000, "reorder_threshold": 200, "cost_per_unit": 0.06},
        {"name": "Pedicure Soak", "unit": "ml", "category": "consumable", "initial_stock": 2000, "reorder_threshold": 300, "cost_per_unit": 0.02},
        {"name": "Base Coat", "unit": "ml", "category": "consumable", "initial_stock": 1000, "reorder_threshold": 200, "cost_per_unit": 0.03},
        {"name": "Top Coat", "unit": "ml", "category": "consumable", "initial_stock": 1000, "reorder_threshold": 200, "cost_per_unit": 0.03},
    ],
}

_SERVICE_SUPPLY_QUANTITIES: Dict[str, Dict[str, list[tuple[str, float]]]] = {
    "barbershop": {
        "Haircut": [("Barber Shampoo", 10.0), ("Styling Product", 3.0)],
        "Classic Haircut": [("Barber Shampoo", 10.0), ("Styling Product", 3.0)],
        "Classic Cut": [("Barber Shampoo", 10.0), ("Styling Product", 3.0)],
        "Men's Haircut": [("Barber Shampoo", 10.0), ("Styling Product", 3.0)],
        "Skin Fade": [("Barber Shampoo", 8.0), ("Styling Product", 3.0)],
        "Fade": [("Barber Shampoo", 8.0), ("Styling Product", 3.0)],
        "Buzz Cut": [("Barber Shampoo", 6.0), ("Styling Product", 2.0)],
        "Kids Haircut (Under 12)": [("Barber Shampoo", 6.0), ("Styling Product", 2.0)],
        "Kids Cut": [("Barber Shampoo", 6.0), ("Styling Product", 2.0)],
        "Beard Trim": [("Beard Oil", 2.0)],
        "Beard Lineup": [("Beard Oil", 1.0)],
        "Mustache Trim": [("Beard Oil", 1.0)],
        "Hot Towel Shave": [("Shave Cream", 8.0), ("Aftershave", 2.0)],
        "Shave": [("Shave Cream", 6.0), ("Aftershave", 2.0)],
        "Head Shave": [("Shave Cream", 8.0), ("Aftershave", 2.0)],
        "Hair + Beard Combo": [("Barber Shampoo", 10.0), ("Styling Product", 3.0), ("Beard Oil", 2.0)],
        "Hair & Beard Combo": [("Barber Shampoo", 10.0), ("Styling Product", 3.0), ("Beard Oil", 2.0)],
        "Hair Color": [("Hair Color", 35.0), ("Developer", 35.0)],
    },
    "salon": {
        "Women's Haircut & Blowout": [("Salon Shampoo", 15.0), ("Salon Conditioner", 15.0), ("Heat Protectant", 5.0), ("Styling Product", 5.0)],
        "Women's Cut": [("Salon Shampoo", 12.0), ("Salon Conditioner", 12.0), ("Styling Product", 4.0)],
        "Cut & Style": [("Salon Shampoo", 12.0), ("Salon Conditioner", 12.0), ("Styling Product", 4.0)],
        "Cut and Style": [("Salon Shampoo", 12.0), ("Salon Conditioner", 12.0), ("Styling Product", 4.0)],
        "Trim": [("Salon Shampoo", 8.0), ("Salon Conditioner", 8.0), ("Styling Product", 3.0)],
        "Men's Haircut": [("Salon Shampoo", 8.0), ("Styling Product", 3.0)],
        "Men's Cut": [("Salon Shampoo", 8.0), ("Styling Product", 3.0)],
        "Blowout": [("Salon Shampoo", 10.0), ("Salon Conditioner", 10.0), ("Heat Protectant", 5.0), ("Styling Product", 5.0)],
        "Shampoo & Style": [("Salon Shampoo", 10.0), ("Salon Conditioner", 10.0), ("Heat Protectant", 5.0), ("Styling Product", 5.0)],
        "Full Colour": [("Hair Color", 60.0), ("Developer", 60.0), ("Salon Shampoo", 15.0), ("Salon Conditioner", 15.0)],
        "Hair Coloring": [("Hair Color", 60.0), ("Developer", 60.0), ("Salon Shampoo", 15.0), ("Salon Conditioner", 15.0)],
        "Color Root Touch-up": [("Hair Color", 40.0), ("Developer", 40.0), ("Salon Shampoo", 10.0), ("Salon Conditioner", 10.0)],
        "Color Correction": [("Hair Color", 80.0), ("Developer", 80.0), ("Salon Shampoo", 15.0), ("Salon Conditioner", 15.0)],
        "Highlights (Full Head)": [("Lightener", 80.0), ("Developer", 80.0), ("Toner", 30.0), ("Salon Shampoo", 15.0), ("Salon Conditioner", 15.0)],
        "Highlights": [("Lightener", 60.0), ("Developer", 60.0), ("Toner", 20.0), ("Salon Shampoo", 12.0), ("Salon Conditioner", 12.0)],
        "Balayage": [("Lightener", 80.0), ("Developer", 80.0), ("Toner", 30.0), ("Salon Shampoo", 15.0), ("Salon Conditioner", 15.0)],
        "Ombre": [("Lightener", 70.0), ("Developer", 70.0), ("Toner", 25.0), ("Salon Shampoo", 12.0), ("Salon Conditioner", 12.0)],
        "Toner": [("Toner", 20.0), ("Developer", 20.0)],
        "Keratin Treatment": [("Keratin Solution", 45.0), ("Salon Shampoo", 15.0), ("Salon Conditioner", 15.0)],
        "Deep Condition": [("Deep Conditioning Mask", 20.0), ("Salon Shampoo", 10.0)],
        "Scalp Treatment": [("Scalp Treatment Serum", 15.0), ("Salon Shampoo", 10.0)],
        "Perm": [("Perm Solution", 45.0), ("Salon Shampoo", 12.0), ("Salon Conditioner", 12.0)],
        "Relaxer": [("Relaxer Cream", 45.0), ("Salon Shampoo", 12.0), ("Salon Conditioner", 12.0)],
        "Acrylic Set": [("Acrylic Powder", 18.0), ("Nail Glue", 2.0), ("Top Coat", 1.0)],
        "Basic Manicure": [("Nail Polish", 3.0), ("Base Coat", 1.0), ("Top Coat", 1.0)],
        "Manicure": [("Nail Polish", 3.0), ("Base Coat", 1.0), ("Top Coat", 1.0)],
        "Gel Nails": [("Gel Polish", 4.0), ("Base Coat", 1.0), ("Top Coat", 1.0)],
        "Dip Powder": [("Dip Powder", 10.0), ("Base Coat", 1.0), ("Top Coat", 1.0)],
        "Nail Art": [("Gel Polish", 2.0), ("Top Coat", 1.0)],
        "Nail Repair": [("Nail Glue", 1.0), ("Acrylic Powder", 3.0), ("Top Coat", 1.0)],
        "Pedicure": [("Pedicure Soak", 8.0), ("Nail Polish", 3.0), ("Base Coat", 1.0), ("Top Coat", 1.0)],
        "Spa Pedicure": [("Pedicure Soak", 10.0), ("Nail Polish", 3.0), ("Base Coat", 1.0), ("Top Coat", 1.0)],
        "Polish Change": [("Nail Polish", 2.0), ("Top Coat", 1.0)],
    },
}


def normalize_vertical(shop_type: str) -> str:
    value = (shop_type or "").lower()
    if any(token in value for token in ("barber", "fade", "cuts", "cut")):
        return "barbershop"
    if any(token in value for token in ("salon", "hair", "beauty", "stylist")):
        return "salon"
    return "barbershop"


def ensure_inventory_items(
    shop_id: int,
    shop_type: str,
    *,
    session=None,
) -> Dict[str, int]:
    own_session = session is None
    db = session or SessionLocal()
    vertical = normalize_vertical(shop_type)
    templates = _VERTICAL_INVENTORY_ITEMS.get(vertical, [])
    if not templates:
        return {}

    try:
        rows = db.execute(
            text("SELECT id, name FROM inventory_items WHERE shop_id = :shop_id"),
            {"shop_id": shop_id},
        ).fetchall()
        item_ids = {str(row[1]).strip().lower(): int(row[0]) for row in rows}

        for item in templates:
            key = item["name"].strip().lower()
            if key in item_ids:
                continue

            created = db.execute(
                text(
                    """
                    INSERT INTO inventory_items (
                        shop_id, name, sku, category, unit, current_stock,
                        reorder_threshold, cost_per_unit, supplier, is_active,
                        created_at, updated_at
                    ) VALUES (
                        :shop_id, :name, :sku, :category, :unit, :current_stock,
                        :reorder_threshold, :cost_per_unit, :supplier, TRUE,
                        NOW(), NOW()
                    )
                    RETURNING id
                    """
                ),
                {
                    "shop_id": shop_id,
                    "name": item["name"],
                    "sku": item.get("sku") or f"{vertical[:3].upper()}-{item['name'].upper().replace(' ', '-')}",
                    "category": item.get("category"),
                    "unit": item.get("unit", "piece"),
                    "current_stock": item.get("initial_stock", 0),
                    "reorder_threshold": item.get("reorder_threshold", 0),
                    "cost_per_unit": item.get("cost_per_unit"),
                    "supplier": item.get("supplier") or "Default seeded supplier",
                },
            ).fetchone()
            item_ids[key] = int(created[0])

        if own_session:
            db.commit()
        return item_ids
    except Exception:
        if own_session:
            db.rollback()
        raise
    finally:
        if own_session:
            db.close()


def build_service_supply_map(
    shop_id: int,
    shop_type: str,
    *,
    session=None,
) -> Dict[str, list[Dict[str, Any]]]:
    own_session = session is None
    db = session or SessionLocal()
    try:
        vertical = normalize_vertical(shop_type)
        item_ids = ensure_inventory_items(shop_id, shop_type, session=db)
        templates = _SERVICE_SUPPLY_QUANTITIES.get(vertical, {})
        service_map: Dict[str, list[Dict[str, Any]]] = {}
        for service_name, items in templates.items():
            mapped_items: list[Dict[str, Any]] = []
            for item_name, quantity in items:
                item_id = item_ids.get(item_name.strip().lower())
                if item_id is None:
                    continue
                mapped_items.append({"item_id": int(item_id), "quantity": float(quantity)})
            if mapped_items:
                service_map[service_name] = mapped_items
        if own_session:
            db.commit()
        return service_map
    except Exception:
        if own_session:
            db.rollback()
        raise
    finally:
        if own_session:
            db.close()


def sync_shop_service_supplies(
    shop_id: int,
    shop_type: str,
    *,
    include_existing: bool = False,
    session=None,
) -> Dict[str, Any]:
    own_session = session is None
    db = session or SessionLocal()
    try:
        item_ids = ensure_inventory_items(shop_id, shop_type, session=db)
        service_map = build_service_supply_map(shop_id, shop_type, session=db)
        rows = db.execute(
            text(
                """
                SELECT id, name, supplies_used
                FROM shop_services
                WHERE shop_id = :shop_id AND is_active = TRUE
                """
            ),
            {"shop_id": shop_id},
        ).fetchall()

        updated = 0
        skipped = 0
        matched = 0

        for row in rows:
            service_id = int(row[0])
            service_name = str(row[1])
            supplies_used = row[2]
            target = service_map.get(service_name)
            if not target:
                continue

            matched += 1
            has_existing = bool(supplies_used)
            if has_existing and not include_existing:
                skipped += 1
                continue

            db.execute(
                text(
                    "UPDATE shop_services SET supplies_used = :supplies_used WHERE id = :service_id"
                ),
                {
                    "service_id": service_id,
                    "supplies_used": json.dumps([
                        {"item_id": int(item["item_id"]), "quantity": item["quantity"]}
                        for item in target
                    ]),
                },
            )
            updated += 1

        if own_session:
            db.commit()
        return {
            "shop_id": shop_id,
            "vertical": normalize_vertical(shop_type),
            "matched_services": matched,
            "updated_services": updated,
            "skipped_services": skipped,
            "inventory_items_available": len(item_ids),
        }
    except Exception:
        if own_session:
            db.rollback()
        raise
    finally:
        if own_session:
            db.close()