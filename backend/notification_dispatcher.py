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
