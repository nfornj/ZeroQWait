"""SOUL evolution Temporal workflow — fans out the SOUL updater to all active shops.

Triggered nightly by the brain schedule (see `temporal_schedules.ensure_brain_schedules`).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from agents.heartbeat_activities import list_active_shop_ids_activity
    from agents.soul_updater import update_shop_soul_activity


@workflow.defn
class ShopSoulEvolutionWorkflow:
    """Evolve a single shop's SOUL."""

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await workflow.execute_activity(
            update_shop_soul_activity,
            payload,
            start_to_close_timeout=timedelta(minutes=5),
        )


@workflow.defn
class AllShopsSoulEvolutionWorkflow:
    """Evolve every active shop's SOUL once per invocation."""

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        reason = str(payload.get("reason") or "scheduled")
        force = bool(payload.get("force") or False)

        shops: List[Dict[str, Any]] = await workflow.execute_activity(
            list_active_shop_ids_activity,
            start_to_close_timeout=timedelta(minutes=2),
        )
        if not shops:
            return {"ok": True, "evolved": 0, "skipped": "no active shops"}

        results: List[Dict[str, Any]] = []
        for shop in shops:
            try:
                result = await workflow.execute_activity(
                    update_shop_soul_activity,
                    {"shop_id": shop["shop_id"], "reason": reason, "force": force},
                    start_to_close_timeout=timedelta(minutes=5),
                )
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                results.append({"ok": False, "shop_id": shop["shop_id"], "error": str(exc)})

        return {
            "ok": True,
            "shop_count": len(shops),
            "evolved": sum(1 for r in results if r.get("ok") and not r.get("skipped")),
            "skipped": sum(1 for r in results if r.get("ok") and r.get("skipped")),
            "failed": sum(1 for r in results if not r.get("ok")),
            "results": results,
        }
