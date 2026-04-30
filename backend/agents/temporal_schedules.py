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
from agents.shop_ops_workflows import (
    AllShopsEveningCloseWorkflow,
    AllShopsMorningOpenWorkflow,
    AllShopsPreCloseWorkflow,
)
from agents.temporal_config import TEMPORAL_TASK_QUEUE

logger = logging.getLogger(__name__)


DEFAULT_MORNING_CRON = "0 8 * * *"
DEFAULT_EVENING_CRON = "0 20 * * *"
DEFAULT_TIMEZONE = "UTC"

# Shop ops schedules fire every 30 min so the ±5 min window in each activity
# catches each shop at the right time regardless of their local timezone.
DEFAULT_SHOP_OPS_CRON = "*/30 * * * *"


def _schedule_payload(briefing_type: str) -> Dict[str, Any]:
    return {"briefing_type": briefing_type, "delivery": "dashboard_notification"}


async def _create_or_skip(client: Client, schedule_id: str, schedule: Schedule, note: str) -> None:
    """Create a Temporal schedule, logging and skipping if it already exists."""
    try:
        await client.create_schedule(schedule_id, schedule, static_summary=note)
        logger.info("Created Temporal schedule %s", schedule_id)
    except RPCError as exc:
        if exc.status == RPCStatusCode.ALREADY_EXISTS:
            logger.info("Temporal schedule %s already exists; leaving it unchanged", schedule_id)
            return
        raise


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
        await _create_or_skip(client, schedule_id, schedule, str(config["note"]))


async def ensure_shop_ops_schedules(client: Client) -> None:
    """Bootstrap the three intelligent shop operational schedules.

    All three fire every 30 minutes.  The activities inside each workflow use
    a ±5 min window to match each shop's configured local open/close time, so
    this single global cadence handles shops in any timezone without per-shop
    schedules.
    """
    shop_ops_cron = os.getenv("TEMPORAL_SHOP_OPS_CRON", DEFAULT_SHOP_OPS_CRON)
    timezone = os.getenv("TEMPORAL_BRIEFING_TIMEZONE", DEFAULT_TIMEZONE)

    specs: list[tuple[str, Any, str]] = [
        (
            "zeroqwait-shop-morning-open",
            AllShopsMorningOpenWorkflow.run,
            "Every 30 min: opens queues for shops whose open_time ≈ now (local TZ).",
        ),
        (
            "zeroqwait-shop-pre-close",
            AllShopsPreCloseWorkflow.run,
            "Every 30 min: runs pre-close intelligence for shops approaching close time.",
        ),
        (
            "zeroqwait-shop-evening-close",
            AllShopsEveningCloseWorkflow.run,
            "Every 30 min: closes queues for shops whose close_time ≈ now (local TZ).",
        ),
    ]

    for schedule_id, workflow_fn, note in specs:
        schedule = Schedule(
            action=ScheduleActionStartWorkflow(
                workflow_fn,
                {},
                task_queue=TEMPORAL_TASK_QUEUE,
                execution_timeout=timedelta(minutes=15),
            ),
            spec=ScheduleSpec(
                cron_expressions=[shop_ops_cron],
                time_zone_name=timezone,
            ),
            policy=SchedulePolicy(
                overlap=ScheduleOverlapPolicy.SKIP,
                catchup_window=timedelta(minutes=30),
                pause_on_failure=True,  # halt if open/close fails so we notice
            ),
            state=ScheduleState(note=note, paused=False),
        )
        await _create_or_skip(client, schedule_id, schedule, note)