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
from agents.soul_workflows import AllShopsSoulEvolutionWorkflow
from agents.commitment_workflows import CommitmentResolverWorkflow
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
                id=f"{schedule_id}-${{SCHEDULED_TIME}}",
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
                id=f"{schedule_id}-${{SCHEDULED_TIME}}",
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


# ─── Brain schedules (SOUL evolution + commitment sweep) ─────────────────────

DEFAULT_SOUL_EVOLUTION_CRON = "0 3 * * *"        # nightly 03:00
DEFAULT_COMMITMENT_SWEEP_CRON = "*/15 * * * *"   # every 15 minutes


async def ensure_brain_schedules(client: Client) -> None:
    """Bootstrap the persistent agent-brain schedules.

    Two schedules:
      * `zeroqwait-soul-evolution`         → nightly fan-out of SOUL updates
      * `zeroqwait-commitment-sweep`       → every 15 min, fires due commitments
    """
    timezone = os.getenv("TEMPORAL_BRIEFING_TIMEZONE", DEFAULT_TIMEZONE)

    soul_cron = os.getenv("TEMPORAL_SOUL_EVOLUTION_CRON", DEFAULT_SOUL_EVOLUTION_CRON)
    soul_schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            AllShopsSoulEvolutionWorkflow.run,
            {"reason": "scheduled"},
            id="zeroqwait-soul-evolution-${SCHEDULED_TIME}",
            task_queue=TEMPORAL_TASK_QUEUE,
            execution_timeout=timedelta(minutes=45),
        ),
        spec=ScheduleSpec(
            cron_expressions=[soul_cron],
            time_zone_name=timezone,
        ),
        policy=SchedulePolicy(
            overlap=ScheduleOverlapPolicy.SKIP,
            catchup_window=timedelta(hours=2),
            pause_on_failure=False,
        ),
        state=ScheduleState(
            note="Nightly: evolve every active shop's SOUL from recent activity.",
            paused=False,
        ),
    )
    await _create_or_skip(
        client,
        "zeroqwait-soul-evolution",
        soul_schedule,
        "Nightly SOUL evolution for all active shops.",
    )

    commitment_cron = os.getenv("TEMPORAL_COMMITMENT_SWEEP_CRON", DEFAULT_COMMITMENT_SWEEP_CRON)
    commitment_schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            CommitmentResolverWorkflow.run,
            {"trigger": "periodic"},
            id="zeroqwait-commitment-sweep-${SCHEDULED_TIME}",
            task_queue=TEMPORAL_TASK_QUEUE,
            execution_timeout=timedelta(minutes=5),
        ),
        spec=ScheduleSpec(
            cron_expressions=[commitment_cron],
            time_zone_name=timezone,
        ),
        policy=SchedulePolicy(
            overlap=ScheduleOverlapPolicy.SKIP,
            catchup_window=timedelta(minutes=30),
            pause_on_failure=False,
        ),
        state=ScheduleState(
            note="Every 15 min: notify owners about due commitments.",
            paused=False,
        ),
    )
    await _create_or_skip(
        client,
        "zeroqwait-commitment-sweep",
        commitment_schedule,
        "Periodic commitment sweep.",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Payroll schedules
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_PAYROLL_ANNUAL_RESET_CRON = "1 0 1 1 *"   # Jan 1 at 00:01
DEFAULT_PAYROLL_REMITTANCE_CRON  = "0 9 * * *"    # Daily 09:00 — check remittances
DEFAULT_PAYROLL_REMITTANCE_DAYS  = 3               # Warn when due within 3 days


async def ensure_payroll_schedules(client: Client) -> None:
    """Register recurring payroll-related Temporal schedules (idempotent)."""
    from agents.payroll_workflows import AnnualPayrollResetWorkflow, RemittanceReminderWorkflow

    timezone = os.getenv("TEMPORAL_BRIEFING_TIMEZONE", DEFAULT_TIMEZONE)

    # 1 — Annual YTD reset (Jan 1)
    annual_cron = os.getenv("TEMPORAL_PAYROLL_ANNUAL_RESET_CRON", DEFAULT_PAYROLL_ANNUAL_RESET_CRON)
    annual_schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            AnnualPayrollResetWorkflow.run,
            {"new_year": 0},   # worker resolves year at runtime
            id="zeroqwait-payroll-annual-reset-${SCHEDULED_TIME}",
            task_queue=TEMPORAL_TASK_QUEUE,
            execution_timeout=timedelta(minutes=30),
        ),
        spec=ScheduleSpec(
            cron_expressions=[annual_cron],
            time_zone_name=timezone,
        ),
        policy=SchedulePolicy(
            overlap=ScheduleOverlapPolicy.SKIP,
            catchup_window=timedelta(hours=2),
            pause_on_failure=True,
        ),
        state=ScheduleState(
            note="Jan 1: reset YTD accumulators for all active shops.",
            paused=False,
        ),
    )
    await _create_or_skip(
        client,
        "zeroqwait-payroll-annual-reset",
        annual_schedule,
        "Annual YTD reset for all active shops.",
    )

    # 2 — Daily remittance reminder
    remittance_cron = os.getenv("TEMPORAL_PAYROLL_REMITTANCE_CRON", DEFAULT_PAYROLL_REMITTANCE_CRON)
    days_ahead = int(os.getenv("TEMPORAL_PAYROLL_REMITTANCE_DAYS", str(DEFAULT_PAYROLL_REMITTANCE_DAYS)))
    remittance_schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            RemittanceReminderWorkflow.run,
            {"days_ahead": days_ahead},
            id="zeroqwait-payroll-remittance-${SCHEDULED_TIME}",
            task_queue=TEMPORAL_TASK_QUEUE,
            execution_timeout=timedelta(minutes=15),
        ),
        spec=ScheduleSpec(
            cron_expressions=[remittance_cron],
            time_zone_name=timezone,
        ),
        policy=SchedulePolicy(
            overlap=ScheduleOverlapPolicy.SKIP,
            catchup_window=timedelta(hours=4),
            pause_on_failure=False,
        ),
        state=ScheduleState(
            note="Daily 09:00: remind owners of remittances due within 3 days.",
            paused=False,
        ),
    )
    await _create_or_skip(
        client,
        "zeroqwait-payroll-remittance-reminder",
        remittance_schedule,
        "Daily remittance due-soon reminder for all active shops.",
    )