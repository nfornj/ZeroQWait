"""Temporal workflows for intelligent shop operational scheduling.

Three workflow groups mirror the three operational schedule checks:
  - AllShopsMorningOpenWorkflow    → fires every 30 min, opens queues when it's time
  - AllShopsPreCloseWorkflow       → fires every 30 min, runs intelligence near close
  - AllShopsEveningCloseWorkflow   → fires every 30 min, closes queues when it's time
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from agents.shop_ops_activities import (
        close_shop_queue_activity,
        get_shops_approaching_close_activity,
        get_shops_due_to_close_activity,
        get_shops_due_to_open_activity,
        open_shop_queue_activity,
        pre_close_intelligence_activity,
    )
    from modules.lawn_care.workflows import WeatherCheckActivity


# ─── Morning open ────────────────────────────────────────────────────────────

@workflow.defn
class AllShopsMorningOpenWorkflow:
    """Check all shops every 30 min; open queues for those whose open_time ≈ now."""

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        shops_due: List[Dict[str, Any]] = await workflow.execute_activity(
            get_shops_due_to_open_activity,
            start_to_close_timeout=timedelta(minutes=2),
        )
        if not shops_due:
            return {"ok": True, "shops_opened": 0, "skipped": "no shops due to open"}

        results: List[Dict[str, Any]] = []
        for shop in shops_due:
            try:
                result = await workflow.execute_activity(
                    open_shop_queue_activity,
                    shop,
                    start_to_close_timeout=timedelta(minutes=3),
                )
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                results.append({"ok": False, "shop_id": shop["shop_id"], "error": str(exc)})

        return {
            "ok": True,
            "shops_opened": sum(1 for r in results if r.get("ok")),
            "shops_failed": sum(1 for r in results if not r.get("ok")),
            "results": results,
        }


# ─── Pre-close intelligence ──────────────────────────────────────────────────

@workflow.defn
class AllShopsPreCloseWorkflow:
    """Check all shops every 30 min; run pre-close intelligence for those approaching close."""

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        shops_approaching: List[Dict[str, Any]] = await workflow.execute_activity(
            get_shops_approaching_close_activity,
            start_to_close_timeout=timedelta(minutes=2),
        )
        if not shops_approaching:
            return {"ok": True, "assessed": 0, "skipped": "no shops in pre-close window"}

        results: List[Dict[str, Any]] = []
        for shop in shops_approaching:
            try:
                result = await workflow.execute_activity(
                    pre_close_intelligence_activity,
                    shop,
                    start_to_close_timeout=timedelta(minutes=3),
                )
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                results.append({"ok": False, "shop_id": shop["shop_id"], "error": str(exc)})

        return {
            "ok": True,
            "assessed": sum(1 for r in results if r.get("ok")),
            "failed": sum(1 for r in results if not r.get("ok")),
            "results": results,
        }


# ─── Evening close ───────────────────────────────────────────────────────────

@workflow.defn
class AllShopsEveningCloseWorkflow:
    """Check all shops every 30 min; close queues for those whose close_time ≈ now."""

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        shops_due: List[Dict[str, Any]] = await workflow.execute_activity(
            get_shops_due_to_close_activity,
            start_to_close_timeout=timedelta(minutes=2),
        )
        if not shops_due:
            return {"ok": True, "shops_closed": 0, "skipped": "no shops due to close"}

        results: List[Dict[str, Any]] = []
        for shop in shops_due:
            try:
                result = await workflow.execute_activity(
                    close_shop_queue_activity,
                    shop,
                    start_to_close_timeout=timedelta(minutes=3),
                )
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                results.append({"ok": False, "shop_id": shop["shop_id"], "error": str(exc)})

        return {
            "ok": True,
            "shops_closed": sum(1 for r in results if r.get("ok")),
            "shops_failed": sum(1 for r in results if not r.get("ok")),
            "results": results,
        }


# ─── Lawn care weather checks ────────────────────────────────────────────────

@workflow.defn
class AllLawnCareWeatherCheckWorkflow:
    """Run the daily weather check for every active lawn-care tenant."""

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await workflow.execute_activity(
            WeatherCheckActivity,
            payload,
            start_to_close_timeout=timedelta(minutes=20),
        )


# ─── Single-shop variants (for direct trigger / testing) ─────────────────────

@workflow.defn
class ShopMorningOpenWorkflow:
    """Directly open a single shop's queue. Used for manual trigger or testing."""

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await workflow.execute_activity(
            open_shop_queue_activity,
            payload,
            start_to_close_timeout=timedelta(minutes=3),
        )


@workflow.defn
class ShopPreCloseWorkflow:
    """Run pre-close intelligence for a single shop. Used for manual trigger or testing."""

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await workflow.execute_activity(
            pre_close_intelligence_activity,
            payload,
            start_to_close_timeout=timedelta(minutes=3),
        )


@workflow.defn
class ShopEveningCloseWorkflow:
    """Directly close a single shop's queue. Used for manual trigger or testing."""

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await workflow.execute_activity(
            close_shop_queue_activity,
            payload,
            start_to_close_timeout=timedelta(minutes=3),
        )
