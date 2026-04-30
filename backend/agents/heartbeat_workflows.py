from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from agents.heartbeat_activities import (
        list_active_shop_ids_activity,
        refresh_shop_briefing_activity,
    )


@workflow.defn
class ShopBriefingWorkflow:
    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await workflow.execute_activity(
            refresh_shop_briefing_activity,
            payload,
            start_to_close_timeout=timedelta(minutes=5),
        )


@workflow.defn
class AllShopBriefingsWorkflow:
    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        briefing_type = str(payload.get("briefing_type") or "morning")
        shops: List[Dict[str, Any]] = await workflow.execute_activity(
            list_active_shop_ids_activity,
            start_to_close_timeout=timedelta(minutes=2),
        )
        results: List[Dict[str, Any]] = []
        for shop in shops:
            result = await workflow.execute_activity(
                refresh_shop_briefing_activity,
                {"shop_id": shop["shop_id"], "briefing_type": briefing_type},
                start_to_close_timeout=timedelta(minutes=5),
            )
            results.append(result)
        return {"ok": True, "briefing_type": briefing_type, "shop_count": len(shops), "results": results}