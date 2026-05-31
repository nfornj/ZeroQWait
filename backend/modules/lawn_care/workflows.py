"""Temporal activities for the lawn care vertical module."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from temporalio import activity


@activity.defn(name="WeatherCheckActivity")
async def WeatherCheckActivity(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the daily weather-hold check for each tenant with lawn_care active."""
    from database import SessionLocal
    from modules.lawn_care.agent_skills import check_weather_and_hold
    from sqlalchemy import text

    target_date = str(payload.get("date") or datetime.utcnow().date().isoformat())
    with SessionLocal() as session:
        rows = session.execute(
            text(
                """
                SELECT id
                FROM platform.shops
                WHERE is_active = TRUE
                  AND active_modules::jsonb ? 'lawn_care'
                ORDER BY id
                """
            )
        ).fetchall()

    results = []
    for row in rows:
        shop_id = int(row[0])
        try:
            results.append(await asyncio.to_thread(check_weather_and_hold, shop_id, target_date))
        except Exception as exc:  # noqa: BLE001
            results.append({"shop_id": shop_id, "ok": False, "error": str(exc)})
    return {
        "ok": True,
        "date": target_date,
        "checked_tenants": len(rows),
        "results": results,
    }