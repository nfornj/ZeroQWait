"""inventory.py — Inventory specialist graph.

Follows the exact same planner/executor pattern as hr.py.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Dict, Optional, Sequence

from langchain_core.messages import BaseMessage

from integrations.odoo_client import odoo_client
from .specialist_graph import build_specialist_runnable
from .tools import inventory_tools
from .tools.odoo_tools import _get_odoo_company_id

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
    # Odoo-backed operations
    "check stock": "check_stock",
    "stock check": "check_stock",
    "barcode": "check_stock",
    "receive": "receive_stock",
    "adjust_stock": "adjust_stock",
    "low_stock_alert": "low_stock_alert",
}

SUPPORTED_OPERATIONS = [
    "list_inventory",
    "add_item",
    "record_restock",
    "record_usage",
    "record_adjustment",
    "get_low_stock_alerts",
    "get_cogs_report",
    # Odoo-backed operations (fall back to local DB when Odoo is not configured)
    "check_stock",
    "receive_stock",
    "adjust_stock",
    "low_stock_alert",
]

PLANNER_INSTRUCTIONS = """\
- list_inventory: show all inventory items; arguments: include_inactive (bool, default false).
- add_item: add a new inventory item to tracking; requires name; optional: unit (piece/ml/g/kg/oz/litre/box), category, sku, initial_stock, reorder_threshold, cost_per_unit, supplier. Requires approval.
- record_restock: record receiving new stock for an existing item; requires item_name_or_id and quantity; optional: unit_cost, notes.
- record_usage: record internal usage/consumption of a supply; requires item_name_or_id and quantity; optional: notes.
- record_adjustment: manually adjust the stock level up or down; requires item_name_or_id and quantity (positive = add, negative = remove); requires approval.
- get_low_stock_alerts: list items at or below reorder threshold; no required arguments.
- get_cogs_report: summarize cost of goods sold (supply deductions + sales); optional: since_date (YYYY-MM-DD).
- check_stock: look up a product by barcode or product_id in Odoo ERP; requires barcode OR product_id.
- receive_stock: add received stock quantity for an Odoo product; requires product_id and quantity; optional: notes.
- adjust_stock: apply a signed quantity adjustment to an Odoo product; requires product_id and qty_delta (positive=add, negative=remove) and reason. Requires approval.
- low_stock_alert: fetch low-stock items from Odoo ERP; optional: threshold (default 5).
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
    if any(k in combined for k in ("barcode", "scan", "check stock", "stock check", "product lookup")):
        return "check_stock"
    if any(k in combined for k in ("receive stock", "receive_stock", "stock received", "goods in")):
        return "receive_stock"
    if "adjust_stock" in combined or "stock adjustment" in combined:
        return "adjust_stock"
    if "low_stock_alert" in combined:
        return "low_stock_alert"
    return "list_inventory"


def _build_inventory_executor(shop_id: int):
    def executor(
        operation: str,
        arguments: Dict[str, Any],
        messages: Sequence[BaseMessage],
    ) -> Dict[str, Any]:
        op = _normalize_operation(operation, arguments, messages)

        def _wants_csv(msgs: Sequence[BaseMessage]) -> bool:
            text = _recent_text(msgs).lower()
            return any(kw in text for kw in ("csv", "export", "download", "spreadsheet", "file"))

        def _items_to_csv(items: list, fieldnames: list) -> str:
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(items)
            return buf.getvalue()

        if op == "list_inventory":
            # Try local DB first; fall back to Odoo when local inventory table is missing
            try:
                items = inventory_tools.list_inventory(
                    shop_id,
                    include_inactive=bool(arguments.get("include_inactive", False)),
                )
                if items:
                    result: Dict[str, Any] = {"items": items, "source": "local"}
                    if _wants_csv(messages):
                        result["csv_content"] = _items_to_csv(
                            items,
                            ["name", "current_stock", "unit", "reorder_threshold", "category", "sku", "supplier"],
                        )
                        result["filename"] = "inventory.csv"
                    return result
            except Exception:
                pass
            # Odoo fallback
            company_id = _get_odoo_company_id(shop_id)
            if company_id and odoo_client.enabled:
                result2 = odoo_client.get_low_stock_items(company_id=company_id, threshold=999999)
                if "error" not in result2:
                    items = result2.get("items", [])
                    out: Dict[str, Any] = {"items": items, "source": "odoo"}
                    if _wants_csv(messages) and items:
                        out["csv_content"] = _items_to_csv(
                            items,
                            ["name", "qty_on_hand", "uom_id", "reorder_threshold"],
                        )
                        out["filename"] = "inventory.csv"
                    return out
            return {"items": [], "source": "none"}

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
            # Try local DB first; fall back to Odoo when local inventory table is missing
            try:
                alerts = inventory_tools.get_low_stock_alerts(shop_id)
                if alerts:
                    low_result: Dict[str, Any] = {"alerts": alerts, "count": len(alerts), "source": "local"}
                    if _wants_csv(messages):
                        low_result["csv_content"] = _items_to_csv(
                            alerts,
                            ["name", "current_stock", "unit", "reorder_threshold", "category", "supplier"],
                        )
                        low_result["filename"] = "low_stock_items.csv"
                    return low_result
            except Exception:
                pass
            # Odoo fallback
            company_id = _get_odoo_company_id(shop_id)
            if company_id and odoo_client.enabled:
                result = odoo_client.get_low_stock_items(company_id=company_id, threshold=5.0)
                if "error" not in result:
                    alerts = result.get("items", [])
                    low_out: Dict[str, Any] = {"alerts": alerts, "count": result.get("count", 0), "source": "odoo"}
                    if _wants_csv(messages) and alerts:
                        low_out["csv_content"] = _items_to_csv(
                            alerts,
                            ["name", "qty_on_hand", "uom_id", "reorder_threshold"],
                        )
                        low_out["filename"] = "low_stock_items.csv"
                    return low_out
            return {"alerts": [], "count": 0, "source": "none"}

        if op == "get_cogs_report":
            return inventory_tools.get_cogs_report(shop_id, _optional_str(arguments.get("since_date")))

        # ── Odoo-backed operations ────────────────────────────────

        if op == "check_stock":
            company_id = _get_odoo_company_id(shop_id)
            barcode = _optional_str(arguments.get("barcode"))
            product_id = _to_int(arguments.get("product_id"))
            if company_id and odoo_client.enabled:
                if barcode:
                    return odoo_client.get_product_by_barcode(barcode, company_id=company_id)
                if product_id:
                    # Reuse low-stock listing filtered by id as a product detail lookup
                    result = odoo_client.get_low_stock_items(company_id=company_id, threshold=999999)
                    items = [i for i in result.get("items", []) if i.get("id") == product_id]
                    return {"product": items[0]} if items else {"error": "not_found", "product_id": product_id}
                # Name-based search: get all products and filter by name
                query_name = _optional_str(arguments.get("name") or arguments.get("query") or arguments.get("product_name"))
                result = odoo_client.get_low_stock_items(company_id=company_id, threshold=999999)
                all_items = result.get("items", [])
                if query_name:
                    q = query_name.lower()
                    all_items = [i for i in all_items if q in str(i.get("name", "")).lower()]
                return {"items": all_items}
            # Local fallback: list inventory and filter by name/id
            try:
                return {"items": inventory_tools.list_inventory(shop_id, include_inactive=False)}
            except Exception:
                return {"items": [], "error": "Inventory table not available"}

        if op == "receive_stock":
            company_id = _get_odoo_company_id(shop_id)
            product_id = _to_int(arguments.get("product_id"))
            qty = _to_float(arguments.get("quantity"))
            if qty is None or qty <= 0:
                return {"error": "receive_stock requires a positive quantity"}
            if company_id and odoo_client.enabled and product_id:
                return odoo_client.receive_stock(
                    product_id, qty,
                    company_id=company_id,
                    notes=_optional_str(arguments.get("notes")) or "",
                )
            # Local fallback: record_restock
            item_id = product_id or _to_int(arguments.get("item_id"))
            if not item_id:
                item_id = _resolve_item_id(shop_id, arguments.get("item_name_or_id") or arguments.get("item"))
            if not item_id:
                return {"error": "receive_stock requires product_id (Odoo) or item_name_or_id (local)"}
            return inventory_tools.record_restock(shop_id, item_id, qty, notes=_optional_str(arguments.get("notes")))

        if op == "adjust_stock":
            company_id = _get_odoo_company_id(shop_id)
            product_id = _to_int(arguments.get("product_id"))
            qty_delta = _to_float(arguments.get("qty_delta") or arguments.get("quantity"))
            reason = _optional_str(arguments.get("reason")) or ""
            if qty_delta is None:
                return {"error": "adjust_stock requires qty_delta"}
            if company_id and odoo_client.enabled and product_id:
                return {
                    "requires_approval": True,
                    "action": "adjust_stock",
                    "details": {"product_id": product_id, "qty_delta": qty_delta, "reason": reason, "company_id": company_id},
                    "message": f"Stock adjustment of {qty_delta:+.2f} for product #{product_id} submitted for approval.",
                }
            # Local fallback: record_adjustment
            item_id = product_id or _resolve_item_id(shop_id, arguments.get("item_name_or_id") or arguments.get("item"))
            if not item_id:
                return {"error": "adjust_stock requires product_id (Odoo) or item_name_or_id (local)"}
            return {
                "requires_approval": True,
                "action": "record_adjustment",
                "details": {"item_id": item_id, "quantity": qty_delta, "notes": reason},
                "message": f"Stock adjustment of {qty_delta:+.2f} units submitted for approval.",
            }

        if op == "low_stock_alert":
            company_id = _get_odoo_company_id(shop_id)
            threshold = _to_float(arguments.get("threshold")) or 5.0
            if company_id and odoo_client.enabled:
                result = odoo_client.get_low_stock_items(company_id=company_id, threshold=threshold)
                if "error" not in result:
                    return {"alerts": result.get("items", []), "count": result.get("count", 0), "source": "odoo"}
            # Local fallback
            alerts = inventory_tools.get_low_stock_alerts(shop_id)
            return {"alerts": alerts, "count": len(alerts), "source": "local"}

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
            source = result.get("source", "")
            if not items:
                return "No inventory items are being tracked yet."
            low = [i for i in items if i.get("is_low_stock") or (float(i.get("qty_on_hand", i.get("current_stock", 1)) or 1) <= float(i.get("reorder_threshold", 5) or 5))]
            lines = []
            for i in items[:20]:
                name = i.get("name", "Unknown")
                qty = i.get("qty_on_hand", i.get("current_stock", "?"))
                unit = i.get("uom_id", i.get("unit", ""))
                threshold = i.get("reorder_threshold", "")
                threshold_note = f" (threshold: {threshold})" if threshold else ""
                lines.append(f"- **{name}**: {qty} {unit}{threshold_note}")
            summary = "\n".join(lines)
            source_note = " (from Odoo)" if source == "odoo" else ""
            low_note = f"\n\n⚠️ **{len(low)} item(s) below reorder threshold.**" if low else ""
            return f"**Products we carry{source_note} ({len(items)} items):**\n\n{summary}{low_note}"

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
            source = result.get("source", "")
            source_note = " (from Odoo)" if source == "odoo" else ""
            if not alerts:
                return f"All inventory items are above their reorder thresholds{source_note}. ✅"
            lines = []
            for a in alerts:
                name = a.get("name", "Unknown item")
                qty = a.get("qty_on_hand", a.get("current_stock", "?"))
                unit = a.get("uom_id", a.get("unit", ""))
                threshold = a.get("reorder_threshold", "")
                threshold_note = f" (threshold: {threshold})" if threshold else ""
                lines.append(f"- **{name}**: {qty} {unit} remaining{threshold_note}")
            csv_note = "\n\n_A CSV file has been attached below._" if result.get("csv_content") else ""
            return f"⚠️ **{len(alerts)} low-stock item(s){source_note}:**\n\n" + "\n".join(lines) + csv_note

        if op == "get_cogs_report":
            return (
                f"**Cost of Goods Sold:** ${result.get('total_cogs', 0):.2f} "
                f"across {result.get('total_movements', 0)} movement(s)"
                + (f" since {result['since']}" if result.get("since") else "")
            )

        if op == "check_stock":
            product = result.get("product")
            if product:
                return (
                    f"**{product.get('name')}** — "
                    f"on hand: {product.get('qty_on_hand', 'N/A')}, "
                    f"price: ${product.get('list_price', 0):.2f}"
                )
            items = result.get("items", [])
            if items:
                lines = [f"- **{i['name']}**: {i.get('qty_on_hand', '?')} {i.get('uom_id', '')}" for i in items[:10]]
                return "**Inventory items:**\n\n" + "\n".join(lines)
            return result.get("error") or "Product not found."

        if op == "receive_stock":
            if result.get("quant_id"):
                return f"Received **{result.get('qty_added')}** units — stock updated (quant #{result.get('quant_id')})."
            if result.get("new_stock") is not None:
                return f"Restocked item #{result.get('item_id')}. New stock: **{result.get('new_stock')}** units."
            return str(result)

        if op in ("adjust_stock",):
            if result.get("requires_approval"):
                return result.get("message", "Stock adjustment submitted for approval.")
            if result.get("quant_id") is not None:
                return f"Stock adjusted by {result.get('qty_delta'):+.2f} units (quant #{result.get('quant_id')})."
            return str(result)

        if op == "low_stock_alert":
            alerts = result.get("alerts", [])
            source = result.get("source", "")
            source_note = " (via Odoo)" if source == "odoo" else ""
            if not alerts:
                return f"All items are above their stock thresholds{source_note}. ✅"
            lines = [
                f"- **{a.get('name')}**: {a.get('qty_on_hand', a.get('current_stock', '?'))} remaining"
                for a in alerts
            ]
            return f"⚠️ **{len(alerts)} low-stock item(s){source_note}:**\n\n" + "\n".join(lines)

        return str(result)

    return formatter


def create_inventory_runnable(shop_id: int):
    """Build a LangGraph-backed inventory specialist for the given shop."""
    return build_specialist_runnable(
        agent_name="inventory",
        shop_id=shop_id,
        temperature=0.2,
        supported_operations=SUPPORTED_OPERATIONS,
        planner_instructions=PLANNER_INSTRUCTIONS,
        executor=_build_inventory_executor(shop_id),
        formatter=_build_inventory_formatter(shop_id),
        operation_normalizer=lambda op, plan, msgs: _normalize_operation(op, plan, msgs),
        fast_plan_builder=None,
    )
