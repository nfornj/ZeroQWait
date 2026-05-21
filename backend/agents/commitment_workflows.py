"""Commitment Resolver — periodic Temporal workflow that fires due commitments.

Runs every 15 minutes via the brain schedule. Each tick:
  1. List commitments where `status='pending' AND due_at <= now()`.
  2. For each due commitment:
       * Free tier  → create an `agent_notification` for the owner (no auto-act).
       * Premium    → create the notification AND mark the commitment so the
         supervisor can act on it next time the owner opens the inbox.
  3. Mark the commitment as `resolved` (with resolved_at).

The actual side effect (notifying the owner) is implemented as an activity so
the workflow stays Temporal-deterministic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import text
from temporalio import activity, workflow

from database import SessionLocal
from modules.agent.work_repository import AgentWorkRepository

from .llm_factory import PREMIUM_SUBSCRIPTION_TIERS, load_shop_subscription_tier

logger = logging.getLogger(__name__)


def _is_premium(tier: str) -> bool:
    return tier in PREMIUM_SUBSCRIPTION_TIERS


@activity.defn
async def list_due_commitments_activity(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return commitments whose due_at has elapsed and are still pending."""
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT id, shop_id, made_by, commitment, trigger_if_missed,
                       due_at, action_payload
                FROM commitments
                WHERE status = 'pending'
                  AND due_at IS NOT NULL
                  AND due_at <= (NOW() AT TIME ZONE 'UTC')
                ORDER BY due_at ASC
                LIMIT 50
                """
            )
        ).fetchall()
        return [
            {
                "commitment_id": int(r[0]),
                "shop_id": int(r[1]),
                "made_by": str(r[2] or "agent"),
                "commitment": str(r[3] or ""),
                "trigger_if_missed": str(r[4] or "") or None,
                "due_at": r[5].isoformat() if r[5] else None,
                "action_payload": r[6] or {},
            }
            for r in rows
        ]
    finally:
        db.close()


@activity.defn
async def resolve_commitment_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Notify the owner about a due commitment and mark it resolved.

    Tier behaviour:
      * Free       → notification only.
      * Premium    → notification with auto-action hint for supervisor follow-up.
    """
    commitment_id = int(payload["commitment_id"])
    shop_id = int(payload["shop_id"])
    commitment_text = str(payload.get("commitment") or "")
    trigger = str(payload.get("trigger_if_missed") or "")

    tier = load_shop_subscription_tier(shop_id)
    is_premium = _is_premium(tier)

    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)

        message = (
            f"Reminder: '{commitment_text}'"
            + (f" — trigger: {trigger}" if trigger else "")
        )
        notif_payload = {
            "commitment_id": commitment_id,
            "tier": tier,
            "auto_act": is_premium,
            "action_required": is_premium,
            "trigger_if_missed": trigger or None,
        }

        repo.create_notification(
            shop_id=shop_id,
            notification_type="commitment_due",
            title="Commitment due",
            message=message[:480],
            severity="warning",
            payload=notif_payload,
        )

        # Mark commitment resolved
        db.execute(
            text(
                """
                UPDATE commitments
                SET status = 'resolved',
                    resolved_at = (NOW() AT TIME ZONE 'UTC')
                WHERE id = :commitment_id
                """
            ),
            {"commitment_id": commitment_id},
        )
        db.commit()

        return {
            "ok": True,
            "commitment_id": commitment_id,
            "shop_id": shop_id,
            "tier": tier,
            "auto_act": is_premium,
        }
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("resolve_commitment_activity failed for id=%s", commitment_id)
        return {"ok": False, "commitment_id": commitment_id, "error": str(exc)}
    finally:
        db.close()


@workflow.defn
class CommitmentResolverWorkflow:
    """Periodic sweep that fires every due commitment."""

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        due: List[Dict[str, Any]] = await workflow.execute_activity(
            list_due_commitments_activity,
            payload or {},
            start_to_close_timeout=timedelta(minutes=2),
        )
        if not due:
            return {"ok": True, "resolved": 0, "skipped": "no due commitments"}

        results: List[Dict[str, Any]] = []
        for entry in due:
            try:
                result = await workflow.execute_activity(
                    resolve_commitment_activity,
                    entry,
                    start_to_close_timeout=timedelta(minutes=2),
                )
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                results.append({
                    "ok": False,
                    "commitment_id": entry.get("commitment_id"),
                    "error": str(exc),
                })

        return {
            "ok": True,
            "checked": len(due),
            "resolved": sum(1 for r in results if r.get("ok")),
            "failed": sum(1 for r in results if not r.get("ok")),
            "results": results,
        }
