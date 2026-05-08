"""appointment_workflows.py — Temporal workflows and activities for appointment reminders
and inventory alerts (Critical 5 additions).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)

_RETRY = RetryPolicy(maximum_attempts=3)


# ─────────────────────────────────────────────────────────────────────────────
# Activities
# ─────────────────────────────────────────────────────────────────────────────

# Re-export from the dedicated module so existing imports keep working.
from .temporal_inventory_activities import check_low_stock_activity  # noqa: F401


@activity.defn
async def send_inventory_alert_activity(shop_id: int) -> bool:
    """Dispatch a low-stock Telegram alert to the shop owner and return True on success."""
    from agents.tools.inventory_tools import get_low_stock_alerts
    from database import SessionLocal
    from notification_dispatcher import dispatch

    try:
        items = get_low_stock_alerts(shop_id)
        if not items:
            return False

        # Get shop name for the message
        from sqlalchemy import text
        with SessionLocal() as db:
            row = db.execute(text("SELECT name FROM shops WHERE id = :sid"), {"sid": shop_id}).fetchone()
            shop_name = row[0] if row else "your shop"

            result = await dispatch(
                shop_id=shop_id,
                event_type="low_stock_alert",
                data={"shop_name": shop_name, "alerts": items},
                db=db,
            )
        return result.get("sent", False)
    except Exception as exc:
        logger.warning("send_inventory_alert_activity shop=%d error=%s", shop_id, exc)
        return False


@activity.defn
async def send_reminder_activity(appointment_id: int, template_key: str) -> bool:
    """Dispatch an appointment reminder notification and mark the flag in the DB."""
    from database import SessionLocal
    from notification_dispatcher import send_appointment_notification
    from sqlalchemy import text

    try:
        with SessionLocal() as db:
            result = await send_appointment_notification(
                appointment_id=appointment_id,
                template_key=template_key,
                db=db,
            )

        sent = result.get("sent", False)
        if sent:
            # Mark the reminder flag so we don't re-send
            col = "reminder_24h_sent" if template_key == "reminder_24h" else "reminder_1h_sent"
            with SessionLocal() as db:
                db.execute(
                    text(f"UPDATE appointments SET {col} = TRUE WHERE id = :appt_id"),  # noqa: S608
                    {"appt_id": appointment_id},
                )
                db.commit()
        return sent
    except Exception as exc:
        logger.warning("send_reminder_activity appt=%d error=%s", appointment_id, exc)
        return False


@activity.defn
async def mark_no_show_activity(appointment_id: int) -> bool:
    """Mark an appointment as no_show if it passed start time with status='scheduled'."""
    from database import SessionLocal
    from sqlalchemy import text

    try:
        with SessionLocal() as db:
            row = db.execute(
                text("""
                    SELECT id, status, scheduled_start
                    FROM appointments WHERE id = :appt_id
                """),
                {"appt_id": appointment_id},
            ).fetchone()

            if not row or row[1] not in ("scheduled", "confirmed"):
                return False

            # Only mark as no-show if appointment was > 15 min ago
            start = row[2]
            if start and (datetime.now(timezone.utc) - start.replace(tzinfo=timezone.utc)) < timedelta(minutes=15):
                return False

            db.execute(
                text("UPDATE appointments SET status = 'no_show', updated_at = NOW() WHERE id = :appt_id"),
                {"appt_id": appointment_id},
            )
            db.commit()
        return True
    except Exception as exc:
        logger.warning("mark_no_show_activity appt=%d error=%s", appointment_id, exc)
        return False


@activity.defn
async def get_unsent_reminders_activity(hours_ahead: int, template_key: str) -> List[int]:
    """Return appointment IDs that need a reminder for the given template."""
    from database import SessionLocal
    from sqlalchemy import text

    col = "reminder_24h_sent" if template_key == "reminder_24h" else "reminder_1h_sent"
    window_start = timedelta(hours=hours_ahead - 1)
    window_end = timedelta(hours=hours_ahead + 1)

    try:
        with SessionLocal() as db:
            rows = db.execute(
                text(f"""
                    SELECT id FROM appointments
                    WHERE status IN ('scheduled', 'confirmed')
                      AND {col} = FALSE
                      AND scheduled_start BETWEEN NOW() + :ws AND NOW() + :we
                """),  # noqa: S608
                {"ws": window_start, "we": window_end},
            ).fetchall()
        return [r[0] for r in rows]
    except Exception as exc:
        logger.warning("get_unsent_reminders_activity error=%s", exc)
        return []


@activity.defn
async def get_overdue_appointments_activity() -> List[int]:
    """Return appointment IDs that are overdue (scheduled but not started, > 15 min past)."""
    from database import SessionLocal
    from sqlalchemy import text

    try:
        with SessionLocal() as db:
            rows = db.execute(
                text("""
                    SELECT id FROM appointments
                    WHERE status IN ('scheduled', 'confirmed')
                      AND scheduled_start < NOW() - INTERVAL '15 minutes'
                """),
            ).fetchall()
        return [r[0] for r in rows]
    except Exception as exc:
        logger.warning("get_overdue_appointments_activity error=%s", exc)
        return []


@activity.defn
async def list_shop_ids_with_inventory_activity() -> List[int]:
    """Return shop IDs that have at least one active inventory item."""
    from database import SessionLocal
    from sqlalchemy import text

    try:
        with SessionLocal() as db:
            rows = db.execute(
                text("SELECT DISTINCT shop_id FROM inventory_items WHERE is_active = TRUE"),
            ).fetchall()
        return [r[0] for r in rows]
    except Exception as exc:
        logger.warning("list_shop_ids_with_inventory_activity error=%s", exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Workflows
# ─────────────────────────────────────────────────────────────────────────────

@workflow.defn
class AppointmentReminderWorkflow:
    """Sweep appointments and send 24h and 1h reminders."""

    @workflow.run
    async def run(self) -> None:
        # 24-hour reminders
        appt_ids_24h = await workflow.execute_activity(
            get_unsent_reminders_activity,
            args=[24, "reminder_24h"],
            schedule_to_close_timeout=timedelta(minutes=5),
            retry_policy=_RETRY,
        )
        for appt_id in appt_ids_24h:
            await workflow.execute_activity(
                send_reminder_activity,
                args=[appt_id, "reminder_24h"],
                schedule_to_close_timeout=timedelta(minutes=2),
                retry_policy=_RETRY,
            )

        # 1-hour reminders
        appt_ids_1h = await workflow.execute_activity(
            get_unsent_reminders_activity,
            args=[1, "reminder_1h"],
            schedule_to_close_timeout=timedelta(minutes=5),
            retry_policy=_RETRY,
        )
        for appt_id in appt_ids_1h:
            await workflow.execute_activity(
                send_reminder_activity,
                args=[appt_id, "reminder_1h"],
                schedule_to_close_timeout=timedelta(minutes=2),
                retry_policy=_RETRY,
            )


@workflow.defn
class NoShowCheckWorkflow:
    """Sweep overdue appointments and mark them as no-show."""

    @workflow.run
    async def run(self) -> None:
        appt_ids = await workflow.execute_activity(
            get_overdue_appointments_activity,
            schedule_to_close_timeout=timedelta(minutes=5),
            retry_policy=_RETRY,
        )
        for appt_id in appt_ids:
            await workflow.execute_activity(
                mark_no_show_activity,
                args=[appt_id],
                schedule_to_close_timeout=timedelta(minutes=2),
                retry_policy=_RETRY,
            )


@workflow.defn
class LowStockAlertWorkflow:
    """Check one shop for low stock and dispatch an alert if needed."""

    @workflow.run
    async def run(self, shop_id: int) -> None:
        items = await workflow.execute_activity(
            check_low_stock_activity,
            args=[shop_id],
            schedule_to_close_timeout=timedelta(minutes=5),
            retry_policy=_RETRY,
        )
        if items:
            await workflow.execute_activity(
                send_inventory_alert_activity,
                args=[shop_id],
                schedule_to_close_timeout=timedelta(minutes=3),
                retry_policy=_RETRY,
            )


@workflow.defn
class WeeklyInventoryReportWorkflow:
    """Weekly sweep: check all shops with inventory and fire low-stock alerts."""

    @workflow.run
    async def run(self) -> None:
        shop_ids = await workflow.execute_activity(
            list_shop_ids_with_inventory_activity,
            schedule_to_close_timeout=timedelta(minutes=5),
            retry_policy=_RETRY,
        )
        for shop_id in shop_ids:
            await workflow.execute_activity(
                send_inventory_alert_activity,
                args=[shop_id],
                schedule_to_close_timeout=timedelta(minutes=3),
                retry_policy=_RETRY,
            )
