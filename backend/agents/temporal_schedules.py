from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import Any, Dict

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleState,
)
from temporalio.service import RPCError, RPCStatusCode

from agents.heartbeat_workflows import AllShopBriefingsWorkflow
from agents.temporal_config import TEMPORAL_TASK_QUEUE

logger = logging.getLogger(__name__)


DEFAULT_MORNING_CRON = "0 8 * * *"
DEFAULT_EVENING_CRON = "0 20 * * *"
DEFAULT_TIMEZONE = "UTC"


def _schedule_payload(briefing_type: str) -> Dict[str, Any]:
    return {"briefing_type": briefing_type, "delivery": "dashboard_notification"}


async def ensure_briefing_schedules(client: Client) -> None:
    timezone = os.getenv("TEMPORAL_BRIEFING_TIMEZONE", DEFAULT_TIMEZONE)
    schedules = {
        "zeroqwait-morning-briefing": {
            "briefing_type": "morning",
            "cron": os.getenv("TEMPORAL_MORNING_BRIEFING_CRON", DEFAULT_MORNING_CRON),
            "note": "Daily dashboard-only morning briefing for active shops.",
        },
        "zeroqwait-evening-wrap-up": {
            "briefing_type": "evening",
            "cron": os.getenv("TEMPORAL_EVENING_WRAP_UP_CRON", DEFAULT_EVENING_CRON),
            "note": "Daily dashboard-only evening wrap-up for active shops.",
        },
    }

    for schedule_id, config in schedules.items():
        workflow_type = str(config["briefing_type"])
        schedule = Schedule(
            action=ScheduleActionStartWorkflow(
                AllShopBriefingsWorkflow.run,
                _schedule_payload(workflow_type),
                task_queue=TEMPORAL_TASK_QUEUE,
                execution_timeout=timedelta(minutes=30),
            ),
            spec=ScheduleSpec(
                cron_expressions=[str(config["cron"])],
                time_zone_name=timezone,
            ),
            policy=SchedulePolicy(
                overlap=ScheduleOverlapPolicy.SKIP,
                catchup_window=timedelta(hours=1),
                pause_on_failure=False,
            ),
            state=ScheduleState(note=str(config["note"]), paused=False),
        )
        try:
            await client.create_schedule(
                schedule_id,
                schedule,
                static_summary=str(config["note"]),
            )
            logger.info("Created Temporal schedule %s (%s)", schedule_id, config["cron"])
        except RPCError as exc:
            if exc.status == RPCStatusCode.ALREADY_EXISTS:
                logger.info("Temporal schedule %s already exists; leaving it unchanged", schedule_id)
                continue
            raise