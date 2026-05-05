"""inventory.py — Inventory specialist graph.

Follows the exact same planner/executor pattern as hr.py.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Sequence

from langchain_core.messages import BaseMessage

from .specialist_graph import build_specialist_runnable
from .tools import inventory_tools

logger = logging.getLogger(__name__)

OPERATION_ALIASES = {
    "add": "add_item",
    "create": "add_item",
    "new item": "add_item",
    "stock": "list_inventory",
    "inventory list": "list_inventory",
    "restock": "record_restock",
    "top up": "record_restock",
    "top-up": "record_restock",
    "use": "record_usage",
    "used": "record_usage",
    "consume": "record_usage",
    "adjust": "record_adjustment",
    "low stock": "get_low_stock_alerts",
    "alerts": "get_low_stock_alerts",
    "cogs": "get_cogs_report",
    "cost of goods": "get_cogs_report",
}

SUPPORTED_OPERATIONS = [
    "list_inventory",
    "add_item",
    "record_restock",
    "record_usage",
    "record_adjustment",
    "get_low_stock_alerts",
    "get_cogs_report",
]

PLANNER_INSTRUCTIONS = """\
- list_inventory: show all inventory items; arguments: include_inactive (bool, default false).
- add_item: add a new inventory item to tracking; requires name; optional: unit (piece/ml/g/kg/oz/litre/box), category, sku, initial_stock, reorder_threshold, cost_per_unit, supplier. Requires approval.
- record_restock: record receiving new stock for an existing item; requires item_name_or_id and quantity; optional: unit_cost, notes.
- record_usage: record internal usage/consumption of a supply; requires item_name_or_id and quantity; optional: notes.
- record_adjustment: manually adjust the stock level up or down; requires item_name_or_id and quantity (positive = add, negative = remove); requires approval.
- get_low_stock_alerts: list items at or below reorder threshold; no required arguments.
- get_cogs_report: summarize cost of goods sold (supply deductions + sales); optional: since_date (YYYY-MM-DD).
"""


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_text(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def _recent_text(messages: Sequence[BaseMessage]) -> str:
    recent = list(messages or [])[-6:]
    parts = []
    for m in recent:
        parts.append(_flatten_text(getattr(m, "content", None)))
    return " ".join(p for p in parts if p).strip()


def _resolve_item_id(shop_id: int, item_name_or_id: Any) -> Optional[int]:
    """Resolve an item name or id string to an integer item_id."""
    if item_name_or_id is None:
        return None
    # Direct integer or numeric string
    try:
        return int(item_name_or_id)
    except (TypeError, ValueError):
        pass
    # Name search
    from sqlalchemy import text
    from database import SessionLocal
    name_str = str(item_name_or_id).strip()
    with SessionLocal() as session:
        row = session.execute(
            text("""
                SELECT id FROM inventory_items
                WHERE shop_id = :shop_id AND LOWER(name) = LOWER(:name) AND is_active = TRUE
                LIMIT 1
            """),
            {"shop_id": shop_id, "name": name_str},
        ).fetchone()
        if row:
            return int(row[0])
        # Fuzzy contains search
        row = session.execute(
            text("""
                SELECT id FROM inventory_items
                WHERE shop_id = :shop_id AND LOWER(name) LIKE LOWER(:pattern) AND is_active = TRUE
                LIMIT 1
            """),
            {"shop_id": shop_id, "pattern": f"%{name_str}%"},
        ).fetchone()
        if row:
            return int(row[0])
    return None


def _normalize_operation(operation: str, plan: Dict[str, Any], messages: Sequence[BaseMessage]) -> str:
    op = str(operation or "").strip().lower()
    if op in OPERATION_ALIASES:
        op = OPERATION_ALIASES[op]
    if op in SUPPORTED_OPERATIONS:
        return op

    combined = f"{op} {_recent_text(messages)} {_flatten_text(plan)}".lower()

    if any(k in combined for k in ("add item", "new item", "create item", "track item", "add product", "add supply")):
        return "add_item"
    if any(k in combined for k in ("restock", "received", "top up", "received stock", "more stock", "stock in")):
        return "record_restock"
    if any(k in combined for k in ("used", "usage", "consume", "consumed", "applied", "used up")):
        return "record_usage"
    if any(k in combined for k in ("adjust", "correction", "correct stock", "stock count")):
        return "record_adjustment"
    if any(k in combined for k in ("low stock", "running low", "need to order", "alerts", "reorder")):
        return "get_low_stock_alerts"
    if any(k in combined for k in ("cogs", "cost of goods", "supply cost", "expense report")):
        return "get_cogs_report"
    return "list_inventory"


def _build_inventory_executor(shop_id: int):
    def executor(
        operation: str,
        arguments: Dict[str, Any],
        messages: Sequence[BaseMessage],
    ) -> Dict[str, Any]:
        op = _normalize_operation(operation, arguments, messages)

        if op == "list_inventory":
            return {
                "items": inventory_tools.list_inventory(
                    shop_id,
                    include_inactive=bool(arguments.get("include_inactive", False)),
                )
            }

        if op == "add_item":
            name = _optional_str(arguments.get("name"))
            if not name:
                return {"error": "add_item requires a name"}
            return {
                "requires_approval": True,
                "action": "add_item",
                "details": {
                    "name": name,
                    "unit": _optional_str(arguments.get("unit")) or "piece",
                    "category": _optional_str(arguments.get("category")),
                    "sku": _optional_str(arguments.get("sku")),
                    "initial_stock": _to_float(arguments.get("initial_stock")) or 0.0,
                    "reorder_threshold": _to_float(arguments.get("reorder_threshold")) or 0.0,
                    "cost_per_unit": _to_float(arguments.get("cost_per_unit")),
                    "supplier": _optional_str(arguments.get("supplier")),
                },
                "message": f"Adding inventory item '{name}' has been submitted for owner approval.",
            }

        if op in ("record_restock", "record_usage", "record_adjustment"):
            item_name_or_id = arguments.get("item_name_or_id") or arguments.get("item_id") or arguments.get("item")
            qty = _to_float(arguments.get("quantity"))
            if not item_name_or_id:
                return {"error": f"{op} requires item_name_or_id"}
            if qty is None:
                return {"error": f"{op} requires quantity"}

            item_id = _resolve_item_id(shop_id, item_name_or_id)
            if not item_id:
                return {"error": f"No inventory item found matching '{item_name_or_id}'"}

            notes = _optional_str(arguments.get("notes"))

            if op == "record_restock":
                return inventory_tools.record_restock(
                    shop_id, item_id, qty,
                    unit_cost=_to_float(arguments.get("unit_cost")),
                    notes=notes,
                )
            if op == "record_usage":
                return inventory_tools.record_usage(shop_id, item_id, qty, notes=notes)
            # record_adjustment — requires approval if large
            return {
                "requires_approval": True,
                "action": "record_adjustment",
                "details": {"item_id": item_id, "quantity": qty, "notes": notes},
                "message": f"Stock adjustment of {qty:+.2f} units for item #{item_id} submitted for approval.",
            }

        if op == "get_low_stock_alerts":
            alerts = inventory_tools.get_low_stock_alerts(shop_id)
            return {"alerts": alerts, "count": len(alerts)}

        if op == "get_cogs_report":
            return inventory_tools.get_cogs_report(shop_id, _optional_str(arguments.get("since_date")))

        return {"error": f"Unknown operation: {op}"}

    return executor


def _build_inventory_formatter(shop_id: int):
    def formatter(operation: str, result: Dict[str, Any]) -> str:
        if "error" in result:
            return f"I encountered an issue: {result['error']}"

        if result.get("requires_approval"):
            return (
                f"I've prepared a request to **{result['action'].replace('_', ' ')}**. "
                f"{result.get('message', 'Awaiting your approval.')}"
            )

        op = _normalize_operation(operation, result, [])

        if op == "list_inventory":
            items = result.get("items", [])
            if not items:
                return "No inventory items are being tracked yet. Say 'add item' to start."
            low = [i for i in items if i.get("is_low_stock")]
            lines = [f"**{i['name']}**: {i['current_stock']} {i['unit']} (threshold: {i['reorder_threshold']})" for i in items[:15]]
            summary = "\n".join(lines)
            low_note = f"\n\n⚠️ **{len(low)} item(s) below reorder threshold.**" if low else ""
            return f"**Inventory ({len(items)} items):**\n{summary}{low_note}"

        if op in ("record_restock",):
            return (
                f"Restocked item #{result.get('item_id')}. "
                f"New stock: **{result.get('new_stock')}** units."
            )

        if op in ("record_usage",):
            return (
                f"Usage recorded for item #{result.get('item_id')}. "
                f"New stock: **{result.get('new_stock')}** units."
            )

        if op == "get_low_stock_alerts":
            alerts = result.get("alerts", [])
            if not alerts:
                return "All inventory items are above their reorder thresholds. ✅"
            lines = [
                f"• **{a['name']}**: {a['current_stock']} {a['unit']} remaining (need {a['reorder_threshold']})"
                for a in alerts
            ]
            return f"⚠️ **{len(alerts)} low-stock alert(s):**\n" + "\n".join(lines)

        if op == "get_cogs_report":
            return (
                f"**Cost of Goods Sold:** ${result.get('total_cogs', 0):.2f} "
                f"across {result.get('total_movements', 0)} movement(s)"
                + (f" since {result['since']}" if result.get("since") else "")
            )

        return str(result)

    return formatter


def create_inventory_runnable(shop_id: int):
    """Build a LangGraph-backed inventory specialist for the given shop."""
    return build_specialist_runnable(
        agent_name="inventory",
        shop_id=shop_id,
        supported_operations=SUPPORTED_OPERATIONS,
        planner_instructions=PLANNER_INSTRUCTIONS,
        executor=_build_inventory_executor(shop_id),
        formatter=_build_inventory_formatter(shop_id),
        operation_normalizer=lambda op, plan, msgs: _normalize_operation(op, plan, msgs),
        fast_plan_builder=None,
    )
