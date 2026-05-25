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
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

import telegram_client as tgc
import notification_templates as tmpl
from notification_preferences import get_telegram_prefs

try:
    from observability.metrics import (
        notification_dispatch_total,
        notification_dispatch_duration,
    )
    _OBS_AVAILABLE = True
except Exception:
    _OBS_AVAILABLE = False

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

    _dispatch_start = time.perf_counter() if _OBS_AVAILABLE else None

    try:
        return await _dispatch_inner(result, channel, event_type, data, shop_id, template_fn, db)
    finally:
        if _OBS_AVAILABLE and _dispatch_start is not None:
            status = "sent" if result.get("sent") else (result.get("reason") or "failed")
            # Normalise long reason strings to a bounded label
            _KNOWN_STATUSES = {
                "sent", "failed", "not_connected", "disabled", "bot_not_configured",
                "no_address", "ses_not_configured", "sns_not_configured",
                "shop_not_found", "channel_not_implemented",
            }
            norm_status = status if status in _KNOWN_STATUSES else "failed"
            notification_dispatch_total.labels(
                channel=channel,
                event_type=event_type,
                status=norm_status,
            ).inc()
            notification_dispatch_duration.labels(channel=channel).observe(
                time.perf_counter() - _dispatch_start
            )


async def _dispatch_inner(
    result: dict[str, Any],
    channel: str,
    event_type: str,
    data: dict[str, Any],
    shop_id: int,
    template_fn: Any,
    db: Session,
) -> dict[str, Any]:

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

    if channel == "email":
        from modules.shops.models import Shop
        import services.aws_client as aws

        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            result["reason"] = "shop_not_found"
            return result

        to_email = getattr(shop, "email", None)
        if not to_email:
            result["reason"] = "shop_email_not_set"
            _log(shop_id, channel, event_type, "", "no_address", db)
            return result

        if not aws.is_ses_configured():
            result["reason"] = "email_not_configured"
            return result

        text, _ = template_fn(data)
        subject = _EMAIL_SUBJECTS.get(event_type, "ZeroQwait notification")
        ok = await aws.send_email(to_email, subject, text, email_type=event_type)
        status = "sent" if ok else "failed"
        _log(shop_id, channel, event_type, text, status, db)
        result["sent"] = ok
        result["reason"] = None if ok else "ses_send_error"
        return result

    if channel == "sms":
        from modules.shops.models import Shop
        import services.aws_client as aws

        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            result["reason"] = "shop_not_found"
            return result

        phone = getattr(shop, "phone", None)
        if not phone:
            result["reason"] = "shop_phone_not_set"
            _log(shop_id, channel, event_type, "", "no_address", db)
            return result

        if not aws.is_sns_configured():
            result["reason"] = "sns_not_configured"
            return result

        text, _ = template_fn(data)
        ok = await aws.send_sms(phone, text)
        status = "sent" if ok else "failed"
        _log(shop_id, channel, event_type, text, status, db)
        result["sent"] = ok
        result["reason"] = None if ok else "sns_send_error"
        return result

    result["reason"] = f"channel_not_implemented:{channel}"
    return result


# ── Email subject lines ───────────────────────────────────────────────────────

_EMAIL_SUBJECTS: dict[str, str] = {
    "morning_briefing":         "☀️ Your ZeroQwait morning briefing",
    "commitment_reminder":      "📌 Commitment reminder from ZeroQwait",
    "appointment_confirmation":  "✅ New appointment booked",
    "revenue_alert":             "💰 Revenue alert from ZeroQwait",
    "staff_absence":             "⚠️ Staff absence alert",
    "agent_escalation":          "🔔 Action required — ZeroQwait",
    "sentiment_alert":           "😟 Customer sentiment alert",
    "booking_confirmed":         "✅ Booking confirmed",
    "reminder_24h":              "⏰ Appointment reminder — tomorrow",
    "reminder_1h":               "⏰ Appointment reminder — 1 hour away",
    "youre_next":                "🎉 You're next in queue!",
    "receipt":                   "🧾 Your ZeroQwait receipt",
    "low_stock_alert":           "⚠️ Low stock alert",
}


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
    from shared.secrets import getenv

    _own_db = db is None
    _db = _SL() if _own_db else db
    try:
        row = _db.execute(
            _sql_text("""
                SELECT
                    a.id, a.shop_id, a.customer_name, a.customer_phone, a.customer_email,
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
        if row[6]:  # public_token
            frontend_url = (getenv("FRONTEND_URL", "https://zeroqwait.com") or "https://zeroqwait.com").rstrip("/")
            cancel_url = f"{frontend_url}/book/cancel/{row[6]}"

        data: dict[str, Any] = {
            "customer_name": row[2] or "Customer",
            "service_name": row[7] or "appointment",
            "shop_name": row[8] or "the shop",
            "scheduled_time": row[5].strftime("%A, %b %d at %I:%M %p") if row[5] else "your scheduled time",
            "cancel_url": cancel_url,
        }
        if extra_vars:
            data.update(extra_vars)

        customer_email = row[4]
        if customer_email and template_key in {"booking_confirmed", "reminder_24h", "reminder_1h"}:
            from services.brevo_email import (
                is_brevo_configured,
                sendBookingConfirmation,
                sendBookingReminder,
            )

            if is_brevo_configured():
                details = {
                    "shop_name": data["shop_name"],
                    "service_name": data["service_name"],
                    "scheduled_time": data["scheduled_time"],
                    "status_url": data.get("cancel_url", ""),
                    "cancel_url": data.get("cancel_url", ""),
                    "reminder_window": "24 hours away" if template_key == "reminder_24h" else "1 hour away",
                }
                if template_key == "booking_confirmed":
                    ok = await sendBookingConfirmation(customer_email, data["customer_name"], details)
                else:
                    ok = await sendBookingReminder(customer_email, data["customer_name"], details)
                return {
                    "sent": ok,
                    "channel": "email",
                    "reason": None if ok else "brevo_send_error",
                    "shop_id": row[1],
                }

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
                    s.name  AS shop_name,
                    sc.email AS customer_email,
                    a.customer_email AS appointment_email
                FROM pos_transactions t
                LEFT JOIN shop_customers sc ON sc.id = t.customer_id
                LEFT JOIN appointments a ON a.id = t.appointment_id
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

        customer_email = txn[9] or txn[10]
        if customer_email:
            from services.brevo_email import is_brevo_configured, sendPaymentReceipt

            if is_brevo_configured():
                ok = await sendPaymentReceipt(
                    customer_email,
                    data["customer_name"],
                    data["total"],
                    "",
                )
                result = {
                    "sent": ok,
                    "channel": "email",
                    "reason": None if ok else "brevo_send_error",
                    "shop_id": txn[1],
                }

                if ok:
                    _db.execute(
                        _sql_text("UPDATE pos_transactions SET receipt_sent = TRUE WHERE id = :txn_id"),
                        {"txn_id": pos_transaction_id},
                    )
                    _db.commit()

                return result

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
