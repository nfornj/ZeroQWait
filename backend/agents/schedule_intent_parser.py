"""Schedule Intent Parser — turns natural-language owner messages into Temporal schedules.

Wired in as a fast-path inside `supervisor.classify_intent`. When the owner
says something like "every Monday at 9am send me last week's revenue", we:

  1. Detect the schedule intent with a tiny LLM classifier.
  2. Convert the natural-language frequency into a cron expression.
  3. Register a Temporal schedule pointing at `CustomShopScheduleWorkflow`.
  4. Persist the schedule row via `AgentWorkRepository.upsert_shop_schedule`.
  5. Return a confirmation message + side-channel flag so the supervisor can
     short-circuit the rest of the graph.

Tier behaviour:
  * free       → at most 3 active custom schedules per shop.
  * premium    → unlimited.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleState,
)

from database import SessionLocal
from modules.agent.models import ShopSchedule
from modules.agent.work_repository import AgentWorkRepository

from .custom_schedule_workflow import CustomShopScheduleWorkflow
from .llm_factory import (
    PREMIUM_SUBSCRIPTION_TIERS,
    create_planner_model,
    load_shop_subscription_tier,
)
from .temporal_config import TEMPORAL_TASK_QUEUE
from .temporal_schedules import _create_or_skip

logger = logging.getLogger(__name__)


_FREE_MAX_CUSTOM_SCHEDULES = 3
_DEFAULT_TIMEZONE = "UTC"

# Quick keyword prefilter — only spend an LLM call when these markers exist
_SCHEDULE_KEYWORDS = re.compile(
    r"\b(every|each|daily|weekly|monthly|recurring|schedule|remind\s+me|every\s+morning|"
    r"every\s+evening|every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b",
    re.IGNORECASE,
)


def _is_premium(tier: str) -> bool:
    return tier in PREMIUM_SUBSCRIPTION_TIERS


def looks_like_schedule_intent(text: str) -> bool:
    """Cheap regex prefilter so we don't spam the LLM on every owner message."""
    if not text:
        return False
    return bool(_SCHEDULE_KEYWORDS.search(text))


# ─── Structured LLM output ──────────────────────────────────────────────────


class ScheduleIntent(BaseModel):
    is_schedule_intent: bool = Field(description="True if the owner is asking for a recurring task.")
    action: str = Field(default="create", description="One of: create, list, cancel.")
    title: str = Field(default="", description="Short human-readable title (<=80 chars).")
    natural_language: str = Field(default="", description="Owner's instruction verbatim or paraphrased.")
    cron_expression: str = Field(
        default="",
        description="Standard 5-field cron in TIMEZONE. Empty if not parsable.",
    )
    timezone: str = Field(default="UTC", description="IANA timezone, defaults to UTC.")
    target_agent: str = Field(default="supervisor", description="supervisor|finance|hr|receptionist|crm")


def _parse_intent_with_llm(shop_id: int, owner_message: str) -> Optional[ScheduleIntent]:
    system_prompt = (
        "You convert shop-owner messages into recurring schedule definitions.\n"
        "Return STRICT JSON matching the ScheduleIntent schema.\n"
        "Rules:\n"
        "  * Set is_schedule_intent=false unless the owner clearly asks for a recurring task.\n"
        "  * cron_expression must be valid 5-field cron ('M H DOM MON DOW').\n"
        "  * If no specific time is given, default to 09:00 in the requested timezone.\n"
        "  * timezone defaults to UTC unless owner names one (e.g. 'America/New_York').\n"
        "  * target_agent: pick the closest specialist (finance for revenue, hr for staff,\n"
        "    receptionist for queue/customers, crm for leads/contacts; supervisor otherwise).\n"
        "Output JSON only, no markdown."
    )

    try:
        llm = create_planner_model(shop_id, temperature=0.0)
        structured = llm.with_structured_output(ScheduleIntent)
        return structured.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=owner_message),
            ]
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Schedule intent LLM failed for shop %s: %s", shop_id, exc)
        return None


# ─── Temporal client helper ─────────────────────────────────────────────────


async def _temporal_client() -> Optional[Client]:
    address = os.getenv("TEMPORAL_ADDRESS", "temporal:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    try:
        return await Client.connect(address, namespace=namespace)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not connect to Temporal at %s: %s", address, exc)
        return None


def _build_schedule(
    schedule_id: str,
    shop_schedule_db_id: int,
    title: str,
    natural_language: str,
    cron_expression: str,
    timezone: str,
    target_agent: str,
) -> Schedule:
    payload = {
        "shop_schedule_id": shop_schedule_db_id,
        "title": title,
        "natural_language": natural_language,
        "target_agent": target_agent,
    }
    return Schedule(
        action=ScheduleActionStartWorkflow(
            CustomShopScheduleWorkflow.run,
            payload,
            task_queue=TEMPORAL_TASK_QUEUE,
            execution_timeout=timedelta(minutes=15),
        ),
        spec=ScheduleSpec(
            cron_expressions=[cron_expression],
            time_zone_name=timezone,
        ),
        policy=SchedulePolicy(
            overlap=ScheduleOverlapPolicy.SKIP,
            catchup_window=timedelta(hours=1),
            pause_on_failure=False,
        ),
        state=ScheduleState(
            note=f"Custom owner schedule: {title[:120]}",
            paused=False,
        ),
    )


# ─── Public API used by supervisor ──────────────────────────────────────────


async def handle_schedule_intent(
    *,
    shop_id: int,
    user_id: Optional[int],
    owner_message: str,
) -> Optional[Dict[str, Any]]:
    """Detect & register a recurring schedule from a single owner message.

    Returns ``None`` if the message is not a schedule intent. Otherwise returns
    a dict the supervisor uses to short-circuit the graph:
        {
            "handled": True,
            "response": <user-facing confirmation>,
            "intent": <ScheduleIntent dict>,
            "schedule_id": <int> | None,
        }
    """
    if not shop_id or not owner_message:
        return None
    if not looks_like_schedule_intent(owner_message):
        return None

    intent = _parse_intent_with_llm(shop_id, owner_message)
    if intent is None or not intent.is_schedule_intent:
        return None

    action = (intent.action or "create").lower()

    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        existing: List[ShopSchedule] = repo.list_active_shop_schedules(shop_id, limit=20)

        if action == "list":
            if not existing:
                response = "You have no recurring schedules yet."
            else:
                bullets = "\n".join(
                    f"  • {s.title} — {s.cron_expression or 'unscheduled'} ({s.timezone})"
                    for s in existing
                )
                response = "Active recurring schedules:\n" + bullets
            return {"handled": True, "response": response, "intent": intent.model_dump(), "schedule_id": None}

        if action == "cancel":
            # Best-effort cancellation by title match — kept minimal for now.
            target = next(
                (s for s in existing if intent.title and intent.title.lower() in (s.title or "").lower()),
                None,
            )
            if not target:
                return {
                    "handled": True,
                    "response": (
                        "I couldn't find a matching recurring schedule to cancel. "
                        "Try: 'list my schedules' to see them."
                    ),
                    "intent": intent.model_dump(),
                    "schedule_id": None,
                }
            target.status = "cancelled"
            db.commit()
            client = await _temporal_client()
            if client:
                try:
                    handle = client.get_schedule_handle(target.temporal_schedule_id)
                    await handle.delete()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not delete Temporal schedule %s: %s", target.temporal_schedule_id, exc)
            return {
                "handled": True,
                "response": f"Cancelled the recurring schedule '{target.title}'.",
                "intent": intent.model_dump(),
                "schedule_id": int(target.id),
            }

        # action == "create"
        if not intent.cron_expression:
            return {
                "handled": True,
                "response": (
                    "I understood you want a recurring task, but I couldn't pin down "
                    "the exact frequency. Try phrasing like 'every Monday at 9am' or "
                    "'every weekday at 8am'."
                ),
                "intent": intent.model_dump(),
                "schedule_id": None,
            }

        tier = load_shop_subscription_tier(shop_id)
        is_premium = _is_premium(tier)
        if not is_premium and len(existing) >= _FREE_MAX_CUSTOM_SCHEDULES:
            return {
                "handled": True,
                "response": (
                    f"You're on the free tier and already have {len(existing)} active "
                    f"recurring schedules (limit {_FREE_MAX_CUSTOM_SCHEDULES}). "
                    "Cancel one or upgrade to Premium for unlimited schedules."
                ),
                "intent": intent.model_dump(),
                "schedule_id": None,
            }

        schedule_key = f"custom-{uuid.uuid4().hex[:10]}"
        temporal_schedule_id = f"shop-{shop_id}-{schedule_key}"
        timezone = intent.timezone or _DEFAULT_TIMEZONE
        title = (intent.title or owner_message[:80]).strip()

        # Create DB row first so the activity has an ID to load later
        schedule_row = repo.upsert_shop_schedule(
            shop_id=shop_id,
            schedule_key=schedule_key,
            temporal_schedule_id=temporal_schedule_id,
            title=title,
            cron_expression=intent.cron_expression,
            created_by_user_id=user_id,
            schedule_type="custom_nl",
            description=owner_message[:600],
            natural_language=owner_message[:1000],
            timezone=timezone,
            target_agent=intent.target_agent or "supervisor",
            action_payload={
                "owner_message": owner_message,
                "intent": intent.model_dump(),
            },
            tier_scope="premium" if is_premium else "free",
            status="active",
        )

        client = await _temporal_client()
        if client is None:
            schedule_row.status = "pending_temporal"
            db.commit()
            return {
                "handled": True,
                "response": (
                    f"Saved the recurring task '{title}', but I couldn't reach the "
                    "scheduler service right now. It will be activated automatically "
                    "once the scheduler is back online."
                ),
                "intent": intent.model_dump(),
                "schedule_id": int(schedule_row.id),
            }

        schedule_obj = _build_schedule(
            schedule_id=schedule_key,
            shop_schedule_db_id=int(schedule_row.id),
            title=title,
            natural_language=owner_message,
            cron_expression=intent.cron_expression,
            timezone=timezone,
            target_agent=intent.target_agent or "supervisor",
        )
        try:
            await _create_or_skip(
                client,
                temporal_schedule_id,
                schedule_obj,
                f"Custom owner schedule '{title}'",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Temporal schedule create failed: %s", exc)
            schedule_row.status = "pending_temporal"
            db.commit()
            return {
                "handled": True,
                "response": (
                    f"Saved '{title}' but the scheduler refused the cron expression "
                    f"'{intent.cron_expression}'. Try a clearer time."
                ),
                "intent": intent.model_dump(),
                "schedule_id": int(schedule_row.id),
            }

        confirmation = (
            f"Done — I'll run '{title}' on schedule '{intent.cron_expression}' "
            f"({timezone}). You'll see results in your inbox."
        )
        return {
            "handled": True,
            "response": confirmation,
            "intent": intent.model_dump(),
            "schedule_id": int(schedule_row.id),
        }
    finally:
        db.close()


__all__ = ["handle_schedule_intent", "looks_like_schedule_intent"]
