"""notification_dispatcher.py — Route notification events to the correct channel.

Usage:
    from notification_dispatcher import dispatch

    result = await dispatch(
        shop_id=42,
        event_type="agent_escalation",
        data={
            "question": "Customer Sarah is requesting a full refund. What should I do?",
            "action_id": "abc-123",
            "context": "She visited twice this month. Total spend: $65.",
        },
        db=db,
    )

Supported event_type values:
    morning_briefing, commitment_reminder, appointment_confirmation,
    revenue_alert, staff_absence, agent_escalation, sentiment_alert

The dispatcher:
  1. Resolves the shop's notification preferences
  2. Renders the message via notification_templates
  3. Sends via telegram_client
  4. Logs the attempt to the notification_log table (best-effort)
  5. Returns a result dict: {"sent": bool, "channel": str, "reason": str | None}
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

import telegram_client as tgc
import notification_templates as tmpl
from notification_preferences import get_telegram_prefs

logger = logging.getLogger(__name__)

# Map event_type → template function
_TEMPLATE_MAP = {
    "morning_briefing": tmpl.morning_briefing,
    "commitment_reminder": tmpl.commitment_reminder,
    "appointment_confirmation": tmpl.appointment_confirmation,
    "revenue_alert": tmpl.revenue_alert,
    "staff_absence": tmpl.staff_absence,
    "agent_escalation": tmpl.agent_escalation,
    "sentiment_alert": tmpl.sentiment_alert,
    # Critical 5 additions
    "booking_confirmed": tmpl.booking_confirmed,
    "reminder_24h": tmpl.reminder_24h,
    "reminder_1h": tmpl.reminder_1h,
    "youre_next": tmpl.youre_next,
    "receipt": tmpl.receipt,
    "low_stock_alert": tmpl.low_stock_alert,
}


async def dispatch(
    shop_id: int,
    event_type: str,
    data: dict[str, Any],
    db: Session,
    channel: str = "telegram",
) -> dict[str, Any]:
    """Dispatch a notification for the given shop and event type.

    Returns a result dict:
        {
            "sent": bool,
            "channel": str,
            "reason": str | None,   # None on success; error label on failure
            "shop_id": int,
        }
    """
    result: dict[str, Any] = {
        "sent": False,
        "channel": channel,
        "reason": None,
        "shop_id": shop_id,
    }

    template_fn = _TEMPLATE_MAP.get(event_type)
    if template_fn is None:
        result["reason"] = f"unknown_event_type:{event_type}"
        logger.warning("notification_dispatcher: unknown event_type '%s'", event_type)
        return result

    if channel == "telegram":
        prefs = get_telegram_prefs(shop_id, db)

        if not prefs:
            result["reason"] = "shop_not_found"
            return result

        if not prefs.connected or not prefs.chat_id:
            result["reason"] = "telegram_not_connected"
            _log(shop_id, channel, event_type, "", "not_connected", db)
            return result

        if not prefs.enabled:
            result["reason"] = "telegram_disabled"
            _log(shop_id, channel, event_type, "", "disabled", db)
            return result

        if not tgc.is_configured():
            result["reason"] = "bot_not_configured"
            return result

        text, buttons = template_fn(data)

        ok = await (
            tgc.send_with_buttons(prefs.chat_id, text, buttons)
            if buttons
            else tgc.send_text(prefs.chat_id, text)
        )

        status = "sent" if ok else "failed"
        _log(shop_id, channel, event_type, text, status, db)

        result["sent"] = ok
        result["reason"] = None if ok else "telegram_api_error"
        return result

    # Future channels (SMS, email, push) — stubs
    result["reason"] = f"channel_not_implemented:{channel}"
    return result


# ── Internal ──────────────────────────────────────────────────────────────────

def _log(
    shop_id: int,
    channel: str,
    event_type: str,
    message: str,
    status: str,
    db: Session,
) -> None:
    """Insert a row into notification_log.  Silently ignores failures."""
    try:
        from sqlalchemy import text as _sql_text
        from database import engine

        with engine.connect() as conn:
            conn.execute(
                _sql_text(
                    """
                    INSERT INTO notification_log
                        (shop_id, channel, event_type, message_text, status, sent_at)
                    VALUES
                        (:shop_id, :channel, :event_type, :message_text, :status, :sent_at)
                    """
                ),
                {
                    "shop_id": shop_id,
                    "channel": channel,
                    "event_type": event_type,
                    "message_text": message[:2000],   # truncate to column size
                    "status": status,
                    "sent_at": datetime.now(timezone.utc),
                },
            )
            conn.commit()
    except Exception as exc:
        logger.warning("notification_log write failed: %s", exc)


# ── High-level helpers (Critical 5) ──────────────────────────────────────────

async def send_appointment_notification(
    appointment_id: int,
    template_key: str,
    extra_vars: Optional[dict[str, Any]] = None,
    db: Optional[Session] = None,
) -> dict[str, Any]:
    """Dispatch a notification to the customer on an appointment.

    Looks up appointment, customer Telegram chat (if any), and shop details,
    then sends the appropriate template.  Falls back gracefully if customer has
    no Telegram connection.
    """
    from sqlalchemy import text as _sql_text
    from database import SessionLocal as _SL

    _own_db = db is None
    _db = _SL() if _own_db else db
    try:
        row = _db.execute(
            _sql_text("""
                SELECT
                    a.id, a.shop_id, a.customer_name, a.customer_phone,
                    a.scheduled_start, a.public_token,
                    ss.name AS service_name,
                    s.name  AS shop_name
                FROM appointments a
                LEFT JOIN shop_services ss ON ss.id = a.service_id
                LEFT JOIN shops s ON s.id = a.shop_id
                WHERE a.id = :appt_id
            """),
            {"appt_id": appointment_id},
        ).fetchone()

        if not row:
            return {"sent": False, "reason": "appointment_not_found"}

        cancel_url = ""
        if row[5]:  # public_token
            cancel_url = f"/book/cancel/{row[5]}"

        data: dict[str, Any] = {
            "customer_name": row[2] or "Customer",
            "service_name": row[6] or "appointment",
            "shop_name": row[7] or "the shop",
            "scheduled_time": row[4].strftime("%A, %b %d at %I:%M %p") if row[4] else "your scheduled time",
            "cancel_url": cancel_url,
        }
        if extra_vars:
            data.update(extra_vars)

        # Route to shop owner's Telegram (owner is notified, not the customer)
        # Customer Telegram notifications require a separate handshake — future scope.
        return await dispatch(
            shop_id=row[1],
            event_type=template_key,
            data=data,
            db=_db,
        )
    finally:
        if _own_db:
            _db.close()


async def send_receipt_notification(
    pos_transaction_id: int,
    db: Optional[Session] = None,
) -> dict[str, Any]:
    """Dispatch a receipt notification after a POS checkout is completed."""
    from sqlalchemy import text as _sql_text
    from database import SessionLocal as _SL

    _own_db = db is None
    _db = _SL() if _own_db else db
    try:
        txn = _db.execute(
            _sql_text("""
                SELECT
                    t.id, t.shop_id, t.subtotal_cents, t.hst_cents,
                    t.tip_cents, t.total_cents, t.payment_method,
                    sc.name AS customer_name,
                    s.name  AS shop_name
                FROM pos_transactions t
                LEFT JOIN shop_customers sc ON sc.id = t.customer_id
                LEFT JOIN shops s ON s.id = t.shop_id
                WHERE t.id = :txn_id
            """),
            {"txn_id": pos_transaction_id},
        ).fetchone()

        if not txn:
            return {"sent": False, "reason": "transaction_not_found"}

        lines_rows = _db.execute(
            _sql_text("""
                SELECT description, quantity, unit_price_cents
                FROM pos_transaction_lines
                WHERE transaction_id = :txn_id
                ORDER BY id
            """),
            {"txn_id": pos_transaction_id},
        ).fetchall()

        items = [
            f"{r[0]} × {r[1]:.0f} — ${(r[1] * r[2] / 100):.2f}"
            for r in lines_rows
        ]

        data: dict[str, Any] = {
            "customer_name": txn[7] or "Customer",
            "shop_name": txn[8] or "the shop",
            "subtotal": (txn[2] or 0) / 100,
            "hst": (txn[3] or 0) / 100,
            "tip": (txn[4] or 0) / 100,
            "total": (txn[5] or 0) / 100,
            "payment_method": txn[6] or "cash",
            "items": items,
        }

        result = await dispatch(
            shop_id=txn[1],
            event_type="receipt",
            data=data,
            db=_db,
        )

        # Mark receipt as sent
        if result.get("sent"):
            _db.execute(
                _sql_text("UPDATE pos_transactions SET receipt_sent = TRUE WHERE id = :txn_id"),
                {"txn_id": pos_transaction_id},
            )
            _db.commit()

        return result
    finally:
        if _own_db:
            _db.close()
