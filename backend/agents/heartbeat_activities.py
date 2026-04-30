from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List

from temporalio import activity

from agents.briefings import refresh_shop_briefing_cache
from database import SessionLocal
from modules.agent.models import RunStatus
from modules.agent.work_repository import AgentWorkRepository
from modules.shops.models import Shop

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@activity.defn
async def list_active_shop_ids_activity() -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        rows = session.query(Shop.id, Shop.name).filter(Shop.is_active == True).all()
        return [{"shop_id": int(shop_id), "shop_name": str(shop_name)} for shop_id, shop_name in rows]
    finally:
        session.close()


@activity.defn
async def refresh_shop_briefing_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    shop_id = int(payload["shop_id"])
    briefing_type = str(payload.get("briefing_type") or "morning")
    try:
        workflow_id = activity.info().workflow_id
    except RuntimeError:
        workflow_id = None

    session = SessionLocal()
    repo = AgentWorkRepository(session)
    run = None
    try:
        run = repo.create_run(
            shop_id=shop_id,
            run_type=f"{briefing_type}_briefing",
            trigger_source="temporal",
            execution_mode="scheduled",
            graph_thread_id=workflow_id,
            input_payload=payload,
        )
        briefing = refresh_shop_briefing_cache(shop_id)
        repo.create_notification(
            shop_id=shop_id,
            run_id=run.id,
            notification_type=f"{briefing_type}_briefing",
            title=f"{briefing_type.title()} briefing ready",
            message=str(briefing.get("summary") or "Your operational briefing is ready."),
            severity="info",
            payload={"briefing": briefing, "generated_at": _utcnow_iso()},
        )
        repo.update_run_status(run.id, RunStatus.COMPLETED, output_payload=briefing)
        return {"ok": True, "shop_id": shop_id, "briefing_type": briefing_type, "briefing": briefing}
    except Exception as exc:
        logger.exception("Temporal briefing activity failed for shop %s", shop_id)
        if run is not None:
            repo.update_run_status(run.id, RunStatus.FAILED, error_message=str(exc))
        raise
    finally:
        session.close()