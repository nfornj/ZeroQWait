from __future__ import annotations

import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

from agents.heartbeat_activities import list_active_shop_ids_activity, refresh_shop_briefing_activity
from agents.heartbeat_workflows import AllShopBriefingsWorkflow, ShopBriefingWorkflow
from agents.temporal_config import TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE, TEMPORAL_TASK_QUEUE
from agents.temporal_schedules import ensure_briefing_schedules

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE)
    if os.getenv("TEMPORAL_BOOTSTRAP_SCHEDULES", "true").strip().lower() in {"1", "true", "yes", "on"}:
        await ensure_briefing_schedules(client)
    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[ShopBriefingWorkflow, AllShopBriefingsWorkflow],
        activities=[list_active_shop_ids_activity, refresh_shop_briefing_activity],
    )
    logger.info("Temporal worker started on %s/%s queue=%s", TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE, TEMPORAL_TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())