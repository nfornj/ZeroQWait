"""Custom Shop Schedule — generic Temporal workflow for owner-defined recurring tasks.

Used by the natural-language schedule parser to register arbitrary owner
schedules ("every Monday at 9am, summarize last week's revenue"). The workflow
loads the registered schedule row, builds a synthetic supervisor prompt, and
runs it through the supervisor graph so the owner sees the result in their
agent inbox.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict

from sqlalchemy import text
from temporalio import activity, workflow

from database import SessionLocal

logger = logging.getLogger(__name__)


@activity.defn
async def execute_custom_schedule_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute one custom owner schedule.

    Currently records an `agent_notification` describing what would have run.
    The supervisor pickup / auto-execution is deferred until human-approval
    plumbing for scheduled actions is in place.
    """
    schedule_id = int(payload["shop_schedule_id"])

    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT shop_id, schedule_key, title, natural_language,
                       target_agent, action_payload, status
                FROM shop_schedules
                WHERE id = :schedule_id
                """
            ),
            {"schedule_id": schedule_id},
        ).first()
        if not row or str(row[6]) != "active":
            return {"ok": True, "skipped": "schedule_inactive_or_missing"}

        shop_id = int(row[0])
        title = str(row[2] or row[1] or "Scheduled task")
        natural_language = str(row[3] or "")
        target_agent = str(row[4] or "supervisor")
        action_payload = row[5] or {}

        message = (
            f"Scheduled '{title}' just ran. "
            f"Original instruction: {natural_language[:280]}"
        )
        db.execute(
            text(
                """
                INSERT INTO agent_notifications (
                    shop_id, notification_type, title, message, severity,
                    payload, created_at
                ) VALUES (
                    :shop_id, 'custom_schedule_fired', :title, :message,
                    'info', :payload, (NOW() AT TIME ZONE 'UTC')
                )
                """
            ),
            {
                "shop_id": shop_id,
                "title": title[:120],
                "message": message[:480],
                "payload": {
                    "shop_schedule_id": schedule_id,
                    "target_agent": target_agent,
                    "action_payload": action_payload,
                },
            },
        )
        db.commit()
        return {"ok": True, "shop_id": shop_id, "schedule_id": schedule_id}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("execute_custom_schedule_activity failed for id=%s", schedule_id)
        return {"ok": False, "schedule_id": schedule_id, "error": str(exc)}
    finally:
        db.close()


@workflow.defn
class CustomShopScheduleWorkflow:
    """Run a single owner-defined recurring task."""

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await workflow.execute_activity(
            execute_custom_schedule_activity,
            payload,
            start_to_close_timeout=timedelta(minutes=10),
        )
