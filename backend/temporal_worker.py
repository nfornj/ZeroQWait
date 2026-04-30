from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from agents.heartbeat_activities import list_active_shop_ids_activity, refresh_shop_briefing_activity
from agents.heartbeat_workflows import AllShopBriefingsWorkflow, ShopBriefingWorkflow
from agents.temporal_config import TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE, TEMPORAL_TASK_QUEUE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE)
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