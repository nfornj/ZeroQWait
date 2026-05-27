"""pos_agent.py — Point-of-Sale specialist graph.

Follows the exact same planner/executor pattern as hr.py and inventory.py.
POS checkout sessions are stored in Redis with a 2-hour TTL.
All monetary amounts are integer cents. HST = 13% on hst_applicable lines.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from langchain_core.messages import BaseMessage
from sqlalchemy import text

from .specialist_graph import build_specialist_runnable
from database import SessionLocal
from redis_client import get_redis_client

logger = logging.getLogger(__name__)

HST_RATE = 0.13
SESSION_TTL = 7200  # 2 hours in seconds
_LOCAL_SESSIONS: Dict[str, tuple[float, Dict[str, Any]]] = {}

OPERATION_ALIASES = {
    "ring up": "add_line_item",
    "ring": "add_line_item",
    "charge": "add_line_item",
    "sale": "complete_checkout",
    "pay": "complete_checkout",
    "paid": "complete_checkout",
    "done": "complete_checkout",
    "bill": "calculate_totals",
    "total": "calculate_totals",
    "refund": "process_refund",
    "void": "process_refund",
    "eod": "end_of_day_summary",
    "end of day": "end_of_day_summary",
    "daily summary": "end_of_day_summary",
    "tip": "add_tip",
    "discount": "apply_discount",
    "remove": "remove_line_item",
    "delete": "remove_line_item",
    "new checkout": "start_checkout",
    "open checkout": "start_checkout",
    "checkout": "start_checkout",
}

SUPPORTED_OPERATIONS = [
    "start_checkout",
    "add_line_item",
    "remove_line_item",
    "add_tip",
    "apply_discount",
    "calculate_totals",
    "complete_checkout",
    "process_refund",
    "end_of_day_summary",
]

PLANNER_INSTRUCTIONS = """\
- start_checkout: open a new POS session; optional: customer_name, employee_id.
- add_line_item: add a service or item to the open session; requires session_id and either service_id (for shop services) or item_id (for inventory items) or a free-text description; optional: quantity (default 1), unit_price_cents (overrides catalogue price if provided), hst_applicable (bool).
- remove_line_item: remove a line from the open session; requires session_id and line_index (0-based).
- add_tip: add a tip amount to the session; requires session_id and tip_cents.
- apply_discount: apply a discount (percentage or flat); requires session_id; provide either discount_pct (0-100) or discount_cents.
- calculate_totals: show the running total for the open session; requires session_id.
- complete_checkout: finalize the session and record the transaction; requires session_id; optional: payment_method (cash|card|e-transfer|other), send_receipt (bool).
- process_refund: process a full or partial refund on a completed transaction; requires transaction_id; optional: reason, amount_cents (partial refund).
- end_of_day_summary: show today's POS totals: number of transactions, gross revenue, HST collected, tips, and top services.
"""


# ── Redis session helpers ─────────────────────────────────────────────────────

def _session_key(shop_id: int, session_id: str) -> str:
    return f"pos_session:{shop_id}:{session_id}"


def _load_session(shop_id: int, session_id: str) -> Optional[Dict[str, Any]]:
    key = _session_key(shop_id, session_id)
    r = get_redis_client()
    raw = r.get(key)
    if raw is None:
        local = _LOCAL_SESSIONS.get(key)
        if local is None:
            return None
        expires_at, data = local
        if expires_at < time.time():
            _LOCAL_SESSIONS.pop(key, None)
            return None
        return data
    _LOCAL_SESSIONS.pop(key, None)
    if isinstance(raw, dict):
        return raw
    return json.loads(raw)


def _save_session(shop_id: int, session_id: str, data: Dict[str, Any]) -> None:
    key = _session_key(shop_id, session_id)
    r = get_redis_client()
    if not r.set(key, data, ttl=SESSION_TTL):
        _LOCAL_SESSIONS[key] = (time.time() + SESSION_TTL, data)


def _delete_session(shop_id: int, session_id: str) -> None:
    key = _session_key(shop_id, session_id)
    _LOCAL_SESSIONS.pop(key, None)
    r = get_redis_client()
    r.delete(key)


def _new_session(shop_id: int, customer_name: Optional[str], employee_id: Optional[int]) -> tuple[str, Dict[str, Any]]:
    sid = str(uuid.uuid4())
    data: Dict[str, Any] = {
        "session_id": sid,
        "shop_id": shop_id,
        "customer_name": customer_name,
        "employee_id": employee_id,
        "lines": [],
        "tip_cents": 0,
        "discount_cents": 0,
        "discount_pct": 0,
        "status": "open",
        "created_at": datetime.utcnow().isoformat(),
    }
    _save_session(shop_id, sid, data)
    return sid, data


def _calculate_totals(session_data: Dict[str, Any]) -> Dict[str, int]:
    subtotal = sum(ln.get("line_total_cents", 0) for ln in session_data.get("lines", []))
    hst = sum(
        round(ln.get("line_total_cents", 0) * HST_RATE)
        for ln in session_data.get("lines", [])
        if ln.get("hst_applicable", True)
    )
    tip = session_data.get("tip_cents", 0)

    # Discount applied on subtotal before HST
    discount = session_data.get("discount_cents", 0)
    if session_data.get("discount_pct", 0):
        discount = max(discount, round(subtotal * session_data["discount_pct"] / 100))

    effective_subtotal = max(0, subtotal - discount)
    # Recalculate HST after discount (pro-rated)
    if subtotal > 0:
        discount_ratio = 1 - (discount / subtotal)
        hst = round(hst * discount_ratio)

    total = effective_subtotal + hst + tip
    return {
        "subtotal_cents": effective_subtotal,
        "hst_cents": hst,
        "tip_cents": tip,
        "discount_cents": discount,
        "total_cents": total,
    }


def _resolve_shop_employee_id(session, shop_id: int, employee_id: Optional[int]) -> Optional[int]:
    if employee_id is None:
        return None
    row = session.execute(
        text("""
            SELECT id
            FROM shop_employees
            WHERE shop_id = :shop_id AND id = :employee_id
        """),
        {"shop_id": shop_id, "employee_id": employee_id},
    ).fetchone()
    if row:
        return row[0]
    row = session.execute(
        text("""
            SELECT id
            FROM shop_employees
            WHERE shop_id = :shop_id AND user_id = :employee_id
        """),
        {"shop_id": shop_id, "employee_id": employee_id},
    ).fetchone()
    return row[0] if row else None


# ── Executor ──────────────────────────────────────────────────────────────────

def _build_pos_executor(shop_id: int):
    def _executor(operation: str, args: Dict[str, Any]) -> Dict[str, Any]:
        op = operation.strip().lower()

        if op == "start_checkout":
            sid, data = _new_session(
                shop_id,
                customer_name=args.get("customer_name"),
                employee_id=args.get("employee_id"),
            )
            return {"session_id": sid, "status": "open", "lines": [], "totals": _calculate_totals(data)}

        if op == "add_line_item":
            sid = args.get("session_id")
            if not sid:
                return {"error": "session_id is required"}
            sess = _load_session(shop_id, sid)
            if not sess:
                return {"error": f"POS session '{sid}' not found or expired"}

            quantity = float(args.get("quantity", 1))
            unit_price_cents = args.get("unit_price_cents")
            hst_applicable = args.get("hst_applicable", True)
            description = args.get("description", "")

            # Resolve service
            if args.get("service_id"):
                with SessionLocal() as session:
                    row = session.execute(
                        text("SELECT name, price_cents, hst_applicable FROM shop_services WHERE id = :sid AND shop_id = :shop_id"),
                        {"sid": args["service_id"], "shop_id": shop_id},
                    ).fetchone()
                if row:
                    description = description or row[0]
                    unit_price_cents = unit_price_cents if unit_price_cents is not None else (row[1] or 0)
                    hst_applicable = row[2] if args.get("hst_applicable") is None else hst_applicable
                else:
                    return {"error": f"Service {args['service_id']} not found"}

            # Resolve inventory item
            elif args.get("item_id"):
                with SessionLocal() as session:
                    row = session.execute(
                        text("SELECT name, retail_price_cents FROM inventory_items WHERE id = :iid AND shop_id = :shop_id"),
                        {"iid": args["item_id"], "shop_id": shop_id},
                    ).fetchone()
                if row:
                    description = description or row[0]
                    unit_price_cents = unit_price_cents if unit_price_cents is not None else (row[1] or 0)
                else:
                    return {"error": f"Item {args['item_id']} not found"}

            if unit_price_cents is None:
                return {"error": "unit_price_cents is required when no service_id or item_id is provided"}

            line_total = round(quantity * unit_price_cents)
            line = {
                "description": description,
                "service_id": args.get("service_id"),
                "item_id": args.get("item_id"),
                "quantity": quantity,
                "unit_price_cents": int(unit_price_cents),
                "hst_applicable": bool(hst_applicable),
                "line_total_cents": line_total,
            }
            sess["lines"].append(line)
            _save_session(shop_id, sid, sess)
            return {"session_id": sid, "lines_count": len(sess["lines"]), "line_added": line, "totals": _calculate_totals(sess)}

        if op == "remove_line_item":
            sid = args.get("session_id")
            idx = args.get("line_index")
            if not sid or idx is None:
                return {"error": "session_id and line_index are required"}
            sess = _load_session(shop_id, sid)
            if not sess:
                return {"error": "POS session not found or expired"}
            lines = sess.get("lines", [])
            if idx < 0 or idx >= len(lines):
                return {"error": f"line_index {idx} is out of range"}
            removed = lines.pop(idx)
            _save_session(shop_id, sid, sess)
            return {"session_id": sid, "removed": removed, "totals": _calculate_totals(sess)}

        if op == "add_tip":
            sid = args.get("session_id")
            tip = int(args.get("tip_cents", 0))
            if not sid:
                return {"error": "session_id is required"}
            sess = _load_session(shop_id, sid)
            if not sess:
                return {"error": "POS session not found or expired"}
            sess["tip_cents"] = tip
            _save_session(shop_id, sid, sess)
            return {"session_id": sid, "tip_cents": tip, "totals": _calculate_totals(sess)}

        if op == "apply_discount":
            sid = args.get("session_id")
            if not sid:
                return {"error": "session_id is required"}
            sess = _load_session(shop_id, sid)
            if not sess:
                return {"error": "POS session not found or expired"}
            if args.get("discount_pct") is not None:
                sess["discount_pct"] = float(args["discount_pct"])
                sess["discount_cents"] = 0
            elif args.get("discount_cents") is not None:
                sess["discount_cents"] = int(args["discount_cents"])
                sess["discount_pct"] = 0
            else:
                return {"error": "Provide discount_pct or discount_cents"}
            _save_session(shop_id, sid, sess)
            return {"session_id": sid, "totals": _calculate_totals(sess)}

        if op == "calculate_totals":
            sid = args.get("session_id")
            if not sid:
                return {"error": "session_id is required"}
            sess = _load_session(shop_id, sid)
            if not sess:
                return {"error": "POS session not found or expired"}
            return {"session_id": sid, "lines": sess["lines"], "totals": _calculate_totals(sess)}

        if op == "complete_checkout":
            sid = args.get("session_id")
            if not sid:
                return {"error": "session_id is required"}
            sess = _load_session(shop_id, sid)
            if not sess:
                return {"error": "POS session not found or expired"}
            if not sess.get("lines"):
                return {"error": "Cannot complete an empty checkout"}

            payment_method = args.get("payment_method", "cash")
            totals = _calculate_totals(sess)

            with SessionLocal() as session:
                employee_id = _resolve_shop_employee_id(session, shop_id, sess.get("employee_id"))
                txn = session.execute(
                    text("""
                        INSERT INTO pos_transactions
                            (shop_id, employee_id, subtotal_cents, hst_cents, tip_cents,
                             discount_cents, total_cents, payment_method, status, completed_at,
                             created_at, updated_at)
                        VALUES
                            (:shop_id, :emp_id, :sub, :hst, :tip,
                             :disc, :total, :method, 'complete', NOW(),
                             NOW(), NOW())
                        RETURNING id
                    """),
                    {
                        "shop_id": shop_id,
                        "emp_id": employee_id,
                        "sub": totals["subtotal_cents"],
                        "hst": totals["hst_cents"],
                        "tip": totals["tip_cents"],
                        "disc": totals["discount_cents"],
                        "total": totals["total_cents"],
                        "method": payment_method,
                    },
                ).fetchone()
                txn_id = txn[0]

                for ln in sess["lines"]:
                    session.execute(
                        text("""
                            INSERT INTO pos_transaction_lines
                                (transaction_id, service_id, item_id, description,
                                 quantity, unit_price_cents, hst_applicable, line_total_cents, created_at)
                            VALUES
                                (:txn_id, :svc_id, :item_id, :desc,
                                 :qty, :unit, :hst_app, :total, NOW())
                        """),
                        {
                            "txn_id": txn_id,
                            "svc_id": ln.get("service_id"),
                            "item_id": ln.get("item_id"),
                            "desc": ln.get("description", ""),
                            "qty": ln.get("quantity", 1),
                            "unit": ln.get("unit_price_cents", 0),
                            "hst_app": ln.get("hst_applicable", True),
                            "total": ln.get("line_total_cents", 0),
                        },
                    )
                session.commit()

            # Invalidate session in Redis
            _delete_session(shop_id, sid)

            # Fire-and-forget receipt notification
            if args.get("send_receipt", False):
                try:
                    import asyncio
                    from notification_dispatcher import send_receipt_notification
                    with SessionLocal() as db:
                        asyncio.get_event_loop().run_until_complete(
                            send_receipt_notification(txn_id, db)
                        )
                except Exception as exc:
                    logger.warning("pos receipt notification failed (non-fatal): %s", exc)

            return {
                "transaction_id": txn_id,
                "totals": totals,
                "payment_method": payment_method,
                "status": "complete",
                "message": f"Transaction #{txn_id} completed. Total: ${totals['total_cents']/100:.2f}.",
            }

        if op == "process_refund":
            txn_id = args.get("transaction_id")
            if not txn_id:
                return {"error": "transaction_id is required"}
            reason = args.get("reason", "owner_request")
            with SessionLocal() as session:
                row = session.execute(
                    text("SELECT id, shop_id, total_cents, status FROM pos_transactions WHERE id = :txn_id AND shop_id = :shop_id"),
                    {"txn_id": txn_id, "shop_id": shop_id},
                ).fetchone()
                if not row:
                    return {"error": f"Transaction #{txn_id} not found"}
                if row[3] == "refunded":
                    return {"error": "Transaction is already refunded"}
                if row[3] not in ("complete",):
                    return {"error": f"Cannot refund a transaction with status '{row[3]}'"}

                session.execute(
                    text("UPDATE pos_transactions SET status = 'refunded', notes = :reason, updated_at = NOW() WHERE id = :txn_id"),
                    {"txn_id": txn_id, "reason": reason},
                )
                session.commit()
            return {"transaction_id": txn_id, "status": "refunded", "amount_cents": row[2]}

        if op == "end_of_day_summary":
            with SessionLocal() as session:
                summary = session.execute(
                    text("""
                        SELECT
                            COUNT(*) AS txn_count,
                            COALESCE(SUM(total_cents),0) AS gross_cents,
                            COALESCE(SUM(hst_cents),0) AS hst_collected,
                            COALESCE(SUM(tip_cents),0) AS tips_cents,
                            COALESCE(SUM(subtotal_cents),0) AS subtotal_cents
                        FROM pos_transactions
                        WHERE shop_id = :shop_id
                          AND DATE(completed_at) = CURRENT_DATE
                          AND status = 'complete'
                    """),
                    {"shop_id": shop_id},
                ).fetchone()

                top_services = session.execute(
                    text("""
                        SELECT l.description, COUNT(*) as sold, SUM(l.line_total_cents) as revenue
                        FROM pos_transaction_lines l
                        JOIN pos_transactions t ON t.id = l.transaction_id
                        WHERE t.shop_id = :shop_id
                          AND DATE(t.completed_at) = CURRENT_DATE
                          AND t.status = 'complete'
                        GROUP BY l.description
                        ORDER BY revenue DESC
                        LIMIT 5
                    """),
                    {"shop_id": shop_id},
                ).fetchall()

            return {
                "date": datetime.utcnow().date().isoformat(),
                "transactions": int(summary[0]),
                "gross_cents": int(summary[1]),
                "gross_display": f"${summary[1]/100:.2f}",
                "hst_cents": int(summary[2]),
                "hst_display": f"${summary[2]/100:.2f}",
                "tips_cents": int(summary[3]),
                "tips_display": f"${summary[3]/100:.2f}",
                "subtotal_cents": int(summary[4]),
                "top_services": [
                    {"description": r[0], "sold": r[1], "revenue_display": f"${r[2]/100:.2f}"}
                    for r in top_services
                ],
            }

        return {"error": f"Unknown operation: {operation}"}

    return _executor


# ── Formatter ─────────────────────────────────────────────────────────────────

def _build_pos_formatter(shop_id: int):
    def _fmt(operation: str, result: Dict[str, Any]) -> str:
        if result.get("error"):
            return f"⚠️ {result['error']}"

        op = operation.strip().lower()

        if op == "start_checkout":
            return f"✅ New checkout session started. Session ID: `{result['session_id']}`\nYou can now add items."

        if op == "add_line_item":
            ln = result.get("line_added", {})
            t = result.get("totals", {})
            return (
                f"Added: **{ln.get('description','item')}** × {ln.get('quantity',1):.0f} — ${(ln.get('line_total_cents',0))/100:.2f}\n"
                f"Running total: **${t.get('total_cents',0)/100:.2f}**"
                + (f" (incl. HST ${t.get('hst_cents',0)/100:.2f})" if t.get("hst_cents") else "")
            )

        if op == "remove_line_item":
            removed = result.get("removed", {})
            t = result.get("totals", {})
            return f"Removed: {removed.get('description','item')}. New total: **${t.get('total_cents',0)/100:.2f}**"

        if op == "add_tip":
            t = result.get("totals", {})
            return f"Tip set to **${result.get('tip_cents',0)/100:.2f}**. New total: **${t.get('total_cents',0)/100:.2f}**"

        if op == "apply_discount":
            t = result.get("totals", {})
            return f"Discount applied. New total: **${t.get('total_cents',0)/100:.2f}** (saved ${t.get('discount_cents',0)/100:.2f})"

        if op == "calculate_totals":
            t = result.get("totals", {})
            lines = result.get("lines", [])
            parts = [f"**{ln.get('description','item')} × {ln.get('quantity',1):.0f}** — ${ln.get('line_total_cents',0)/100:.2f}" for ln in lines]
            return (
                "\n".join(parts) + "\n\n"
                + f"Subtotal: ${t.get('subtotal_cents',0)/100:.2f}\n"
                + (f"HST: ${t.get('hst_cents',0)/100:.2f}\n" if t.get("hst_cents") else "")
                + (f"Tip: ${t.get('tip_cents',0)/100:.2f}\n" if t.get("tip_cents") else "")
                + (f"Discount: -${t.get('discount_cents',0)/100:.2f}\n" if t.get("discount_cents") else "")
                + f"**Total: ${t.get('total_cents',0)/100:.2f}**"
            )

        if op == "complete_checkout":
            t = result.get("totals", {})
            return (
                f"✅ **Checkout complete!** Transaction #{result.get('transaction_id')}\n"
                f"Total: **${t.get('total_cents',0)/100:.2f}** paid by {result.get('payment_method','cash')}."
            )

        if op == "process_refund":
            return f"💸 Refund processed for transaction #{result.get('transaction_id')}. Amount: ${result.get('amount_cents',0)/100:.2f}"

        if op == "end_of_day_summary":
            top = result.get("top_services", [])
            top_lines = "\n".join(f"  • {s['description']}: {s['sold']} sold — {s['revenue_display']}" for s in top)
            return (
                f"📊 **End-of-Day Summary — {result.get('date','today')}**\n\n"
                f"Transactions: **{result.get('transactions',0)}**\n"
                f"Gross Revenue: **{result.get('gross_display','$0.00')}**\n"
                f"HST Collected: {result.get('hst_display','$0.00')}\n"
                f"Tips: {result.get('tips_display','$0.00')}\n"
                + (f"\nTop services:\n{top_lines}" if top_lines else "")
            )

        return str(result)

    return _fmt


# ── Operation normalizer ──────────────────────────────────────────────────────

def _normalize_pos_operation(operation: str, plan: Any, messages: Sequence[BaseMessage]) -> str:
    op = operation.strip().lower()
    return OPERATION_ALIASES.get(op, op)


# ── Entry point ───────────────────────────────────────────────────────────────

def create_pos_runnable(shop_id: int):
    """Build and return the POS specialist runnable for the given shop."""
    return build_specialist_runnable(
        shop_id=shop_id,
        supported_operations=SUPPORTED_OPERATIONS,
        planner_instructions=PLANNER_INSTRUCTIONS,
        build_executor=_build_pos_executor,
        build_formatter=_build_pos_formatter,
        operation_normalizer=_normalize_pos_operation,
    )
