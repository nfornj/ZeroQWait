"""Commitment Scanner — finds inferred promises ("I'll text you back tomorrow")
inside agent ↔ owner / agent ↔ customer conversations and persists them.

Used by `chat_service` after a chat run completes. Designed to be cheap and
non-blocking: the caller schedules it as a background asyncio task so the user
never waits on it.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from database import SessionLocal
from modules.agent.work_repository import AgentWorkRepository

from .llm_factory import (
    PREMIUM_SUBSCRIPTION_TIERS,
    create_planner_model,
    load_shop_subscription_tier,
)

logger = logging.getLogger(__name__)

_MAX_MESSAGES = 20
_MAX_NEW_COMMITMENTS_PER_RUN_FREE = 1
_MAX_NEW_COMMITMENTS_PER_RUN_PREMIUM = 5


def _is_premium(tier: str) -> bool:
    return tier in PREMIUM_SUBSCRIPTION_TIERS


def _format_messages(messages: List[Any]) -> List[Dict[str, str]]:
    formatted: List[Dict[str, str]] = []
    for msg in (messages or [])[-_MAX_MESSAGES:]:
        role = "agent"
        content = ""
        if isinstance(msg, dict):
            role = str(msg.get("role") or msg.get("type") or "agent")
            content = str(msg.get("content") or msg.get("text") or "")
        else:
            type_attr = getattr(msg, "type", None)
            if type_attr == "human":
                role = "user"
            elif type_attr == "ai":
                role = "agent"
            elif type_attr == "system":
                continue
            else:
                role = type_attr or "agent"
            content = str(getattr(msg, "content", "") or "")
        content = content.strip()
        if not content:
            continue
        formatted.append({"role": role, "content": content[:600]})
    return formatted


def _parse_due_at(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    text_value = str(raw).strip()
    if not text_value:
        return None
    # Accept ISO-8601 plus a few relative shorthands the LLM tends to emit.
    lowered = text_value.lower()
    now = datetime.utcnow()
    if lowered in {"tomorrow", "next day"}:
        return (now + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    if lowered in {"end_of_day", "eod", "tonight"}:
        return now.replace(hour=20, minute=0, second=0, microsecond=0)
    if lowered.startswith("in ") and lowered.endswith(" hours"):
        try:
            hours = int(lowered.split()[1])
            return now + timedelta(hours=hours)
        except (ValueError, IndexError):
            return None
    try:
        return datetime.fromisoformat(text_value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _llm_extract_commitments(
    shop_id: int,
    run_id: Optional[int],
    messages: List[Dict[str, str]],
    is_premium: bool,
) -> List[Dict[str, Any]]:
    if not messages:
        return []

    cap = _MAX_NEW_COMMITMENTS_PER_RUN_PREMIUM if is_premium else _MAX_NEW_COMMITMENTS_PER_RUN_FREE

    system_prompt = (
        "You are the Commitment Scanner for ZeroQwait. Read the conversation "
        "below and detect any concrete commitment the agent or the owner just "
        "made (e.g. 'I'll send the schedule tomorrow', 'we'll follow up at 3pm', "
        "'remind me Monday morning'). Ignore vague intent.\n\n"
        f"Return STRICT JSON: {{\"commitments\": [...]}} with at most {cap} entries.\n"
        "Each entry: {\n"
        "  made_by:           'agent' | 'owner' | 'customer',\n"
        "  commitment:        short factual sentence (<=160 chars),\n"
        "  due_at:            ISO timestamp OR one of: tomorrow, end_of_day, in 2 hours, in 24 hours,\n"
        "  trigger_if_missed: short label describing what to do if it lapses\n"
        "}\n"
        "Output JSON only — no markdown."
    )

    payload = {"shop_id": shop_id, "run_id": run_id, "messages": messages}

    try:
        llm = create_planner_model(shop_id, temperature=0.1)
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=json.dumps(payload, default=str)),
            ]
        )
        raw = str(getattr(response, "content", "") or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()
        parsed = json.loads(raw)
        commitments = parsed.get("commitments") if isinstance(parsed, dict) else None
        if not isinstance(commitments, list):
            return []
        return commitments[:cap]
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Commitment LLM extraction failed for shop=%s run=%s: %s",
            shop_id, run_id, exc,
        )
        return []


def scan_and_persist_commitments_sync(
    *,
    shop_id: int,
    run_id: Optional[int],
    messages: List[Any],
) -> Dict[str, Any]:
    """Synchronous worker that does the actual extraction + DB writes."""
    if not shop_id:
        return {"ok": False, "error": "missing shop_id"}

    formatted = _format_messages(messages)
    if not formatted:
        return {"ok": True, "shop_id": shop_id, "skipped": "no messages"}

    tier = load_shop_subscription_tier(shop_id)
    is_premium = _is_premium(tier)

    extracted = _llm_extract_commitments(shop_id, run_id, formatted, is_premium)
    if not extracted:
        return {"ok": True, "shop_id": shop_id, "tier": tier, "extracted": 0}

    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        created = 0
        for entry in extracted:
            if not isinstance(entry, dict):
                continue
            commitment = str(entry.get("commitment") or "").strip()
            if not commitment:
                continue
            due_at = _parse_due_at(entry.get("due_at"))
            made_by = str(entry.get("made_by") or "agent").lower()
            if made_by not in {"agent", "owner", "customer"}:
                made_by = "agent"
            try:
                repo.create_commitment(
                    shop_id=shop_id,
                    made_by=made_by,
                    commitment=commitment[:280],
                    run_id=run_id,
                    due_at=due_at,
                    trigger_if_missed=str(entry.get("trigger_if_missed") or "")[:120] or None,
                    action_payload={
                        "raw": entry,
                        "is_premium": is_premium,
                    },
                    detected_from={"source": "chat_finalize", "run_id": run_id},
                )
                created += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to persist commitment for shop %s: %s", shop_id, exc)

        return {
            "ok": True,
            "shop_id": shop_id,
            "tier": tier,
            "extracted": len(extracted),
            "created": created,
        }
    finally:
        db.close()


async def schedule_commitment_scan(
    *,
    shop_id: int,
    run_id: Optional[int],
    messages: List[Any],
) -> None:
    """Fire-and-forget background scan. Safe to call from FastAPI / chat_service."""
    if not shop_id:
        return

    snapshot = list(messages or [])

    async def _runner() -> None:
        try:
            await asyncio.to_thread(
                scan_and_persist_commitments_sync,
                shop_id=int(shop_id),
                run_id=int(run_id) if run_id is not None else None,
                messages=snapshot,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("schedule_commitment_scan failed: %s", exc)

    try:
        asyncio.create_task(_runner())
    except RuntimeError:
        # No running loop — execute synchronously as a fallback
        try:
            scan_and_persist_commitments_sync(
                shop_id=int(shop_id),
                run_id=int(run_id) if run_id is not None else None,
                messages=snapshot,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("commitment scan fallback failed: %s", exc)


__all__ = ["schedule_commitment_scan", "scan_and_persist_commitments_sync"]
