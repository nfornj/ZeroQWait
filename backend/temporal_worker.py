from __future__ import annotations

import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

from agents.heartbeat_activities import list_active_shop_ids_activity, refresh_shop_briefing_activity
from agents.heartbeat_workflows import AllShopBriefingsWorkflow, ShopBriefingWorkflow
from agents.shop_ops_activities import (
    close_shop_queue_activity,
    get_shops_approaching_close_activity,
    get_shops_due_to_close_activity,
    get_shops_due_to_open_activity,
    open_shop_queue_activity,
    pre_close_intelligence_activity,
)
from agents.shop_ops_workflows import (
    AllShopsEveningCloseWorkflow,
    AllShopsMorningOpenWorkflow,
    AllShopsPreCloseWorkflow,
    ShopEveningCloseWorkflow,
    ShopMorningOpenWorkflow,
    ShopPreCloseWorkflow,
)
from agents.soul_updater import update_shop_soul_activity
from agents.soul_workflows import (
    AllShopsSoulEvolutionWorkflow,
    ShopSoulEvolutionWorkflow,
)
from agents.commitment_workflows import (
    CommitmentResolverWorkflow,
    list_due_commitments_activity,
    resolve_commitment_activity,
)
from agents.custom_schedule_workflow import (
    CustomShopScheduleWorkflow,
    execute_custom_schedule_activity,
)
from agents.payroll_workflows import (
    AnnualPayrollResetWorkflow,
    HiringWorkflow,
    PayrollRunWorkflow,
    RemittanceReminderWorkflow,
    TipPoolWorkflow,
    annual_ytd_reset_activity,
    approve_payroll_batch_activity,
    draft_payroll_activity,
    hiring_activity,
    remittance_reminder_activity,
    split_tip_pool_activity,
)
from agents.temporal_config import TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE, TEMPORAL_TASK_QUEUE
from agents.temporal_schedules import (
    ensure_brain_schedules,
    ensure_briefing_schedules,
    ensure_payroll_schedules,
    ensure_shop_ops_schedules,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE)
    if os.getenv("TEMPORAL_BOOTSTRAP_SCHEDULES", "true").strip().lower() in {"1", "true", "yes", "on"}:
        await ensure_briefing_schedules(client)
        await ensure_shop_ops_schedules(client)
        await ensure_brain_schedules(client)
        await ensure_payroll_schedules(client)
    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[
            ShopBriefingWorkflow,
            AllShopBriefingsWorkflow,
            # Shop operational scheduling workflows
            AllShopsMorningOpenWorkflow,
            AllShopsPreCloseWorkflow,
            AllShopsEveningCloseWorkflow,
            ShopMorningOpenWorkflow,
            ShopPreCloseWorkflow,
            ShopEveningCloseWorkflow,
            # Brain — SOUL, commitments, custom owner schedules
            ShopSoulEvolutionWorkflow,
            AllShopsSoulEvolutionWorkflow,
            CommitmentResolverWorkflow,
            CustomShopScheduleWorkflow,
            # Payroll workflows
            HiringWorkflow,
            PayrollRunWorkflow,
            RemittanceReminderWorkflow,
            TipPoolWorkflow,
            AnnualPayrollResetWorkflow,
        ],
        activities=[
            list_active_shop_ids_activity,
            refresh_shop_briefing_activity,
            # Shop operational scheduling activities
            get_shops_due_to_open_activity,
            get_shops_approaching_close_activity,
            get_shops_due_to_close_activity,
            open_shop_queue_activity,
            pre_close_intelligence_activity,
            close_shop_queue_activity,
            # Brain activities
            update_shop_soul_activity,
            list_due_commitments_activity,
            resolve_commitment_activity,
            execute_custom_schedule_activity,
            # Payroll activities
            hiring_activity,
            draft_payroll_activity,
            approve_payroll_batch_activity,
            remittance_reminder_activity,
            split_tip_pool_activity,
            annual_ytd_reset_activity,
        ],
    )
    logger.info("Temporal worker started on %s/%s queue=%s", TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE, TEMPORAL_TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())