"""SOUL Updater — Temporal activity that evolves each shop's persistent SOUL.

Designed to be called as a Temporal Activity from any shop-scoped workflow
(post-run from briefings, shop ops workflows, owner chat finalization).
The activity is idempotent and always returns a JSON-serializable result.

Approach:
  1. Pull the shop's recent agent_runs, conversation memories and notifications
     since `last_evolved_at` (or last 7 days, whichever is broader).
  2. Ask a small planner LLM to extract up to N concrete learnings:
       - patterns the agent should remember
       - personality refinements (tone, upsell style, owner_communication)
       - recent_decisions worth recording
       - open_items still pending
  3. Persist new learnings to `soul_learnings`.
  4. Promote graduated patterns onto `shop_soul.learned_patterns`,
     replacing the lowest-confidence/oldest entry when over limit.
  5. Update the SOUL summary string and `last_evolved_at`.

Tier behaviour:
  * free       → at most one update every 7 days (rolling 30-day window)
  * premium    → runs every invocation (full history considered)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import text
from temporalio import activity

from database import SessionLocal
from modules.agent.models import ShopSoul, SoulLearning
from modules.agent.work_repository import AgentWorkRepository

from .llm_factory import (
    PREMIUM_SUBSCRIPTION_TIERS,
    create_planner_model,
    load_shop_subscription_tier,
)

logger = logging.getLogger(__name__)


_MAX_PATTERNS_FREE = 5
_MAX_PATTERNS_PREMIUM = 25
_FREE_UPDATE_INTERVAL_DAYS = 7
_FREE_HISTORY_WINDOW_DAYS = 30
_PREMIUM_HISTORY_WINDOW_DAYS = 90


def _truncate(value: Any, limit: int = 600) -> str:
    text_value = str(value or "").replace("\n", " ").strip()
    if len(text_value) <= limit:
        return text_value
    return text_value[: limit - 1].rstrip() + "…"


def _is_premium(tier: str) -> bool:
    return tier in PREMIUM_SUBSCRIPTION_TIERS


def _gather_recent_signals(shop_id: int, since: datetime) -> Dict[str, Any]:
    """Pull lightweight evidence the LLM can summarize into SOUL updates."""
    db = SessionLocal()
    try:
        runs = db.execute(
            text(
                """
                SELECT id, run_type, current_agent, status, summary,
                       output_payload, created_at
                FROM agent_runs
                WHERE shop_id = :shop_id AND created_at >= :since
                ORDER BY created_at DESC
                LIMIT 25
                """
            ),
            {"shop_id": shop_id, "since": since},
        ).fetchall()

        notifications = db.execute(
            text(
                """
                SELECT notification_type, title, message, severity, created_at
                FROM agent_notifications
                WHERE shop_id = :shop_id AND created_at >= :since
                ORDER BY created_at DESC
                LIMIT 15
                """
            ),
            {"shop_id": shop_id, "since": since},
        ).fetchall()

        memories = db.execute(
            text(
                """
                SELECT memory_type, content, created_at
                FROM agent_memory
                WHERE shop_id = :shop_id AND created_at >= :since AND is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 25
                """
            ),
            {"shop_id": shop_id, "since": since},
        ).fetchall()

        return {
            "runs": [
                {
                    "id": int(r[0]),
                    "run_type": str(r[1] or ""),
                    "current_agent": str(r[2] or ""),
                    "status": str(r[3] or ""),
                    "summary": _truncate(r[4], 240),
                    "output_summary": _truncate(json.dumps(r[5], default=str) if r[5] else "", 240),
                    "created_at": r[6].isoformat() if r[6] else None,
                }
                for r in runs
            ],
            "notifications": [
                {
                    "type": str(n[0] or ""),
                    "title": _truncate(n[1], 120),
                    "message": _truncate(n[2], 240),
                    "severity": str(n[3] or "info"),
                    "created_at": n[4].isoformat() if n[4] else None,
                }
                for n in notifications
            ],
            "memories": [
                {
                    "memory_type": str(m[0] or ""),
                    "content": _truncate(m[1], 240),
                    "created_at": m[2].isoformat() if m[2] else None,
                }
                for m in memories
            ],
        }
    finally:
        db.close()


def _llm_extract_learnings(
    shop_id: int,
    shop_name: str,
    soul: Dict[str, Any],
    signals: Dict[str, Any],
) -> Dict[str, Any]:
    """Call the planner model to produce structured SOUL updates.

    Returns ``{}`` on any LLM/parse failure — a no-op update is preferred to
    a corrupted SOUL.
    """
    if not signals.get("runs") and not signals.get("notifications") and not signals.get("memories"):
        return {}

    system_prompt = (
        "You are the SOUL Updater for ZeroQwait. Your job is to maintain a "
        "concise, factual personality and learning record for one shop's AI "
        "agent team.\n\n"
        "Read the recent activity for the shop and produce a STRICT JSON object "
        "with these keys (omit a key if there is nothing new for it):\n"
        "  patterns:        list of <=5 short strings (\"On Tuesdays the owner cancels 3pm slots\")\n"
        "  decisions:       list of <=3 objects {date, summary} (factual, no opinions)\n"
        "  open_items:      list of <=3 objects {text, due_at?}\n"
        "  tone:            one of friendly|professional|casual|formal — only set if confidence is high\n"
        "  upsell_style:    one of soft|moderate|aggressive — only set if confidence is high\n"
        "  owner_communication: one of voice|text|summary — only set if confidence is high\n"
        "  summary:         one paragraph (<=400 chars) describing this shop's character today\n"
        "Rules: only output things you can directly justify from the signals. "
        "No speculation. JSON only — no markdown, no commentary."
    )

    user_payload = {
        "shop_id": shop_id,
        "shop_name": shop_name,
        "current_soul": {
            "tone": soul.get("tone"),
            "upsell_style": soul.get("upsell_style"),
            "owner_communication": soul.get("owner_communication"),
            "summary": soul.get("summary"),
            "learned_patterns": soul.get("learned_patterns") or [],
        },
        "recent_signals": signals,
    }

    try:
        llm = create_planner_model(shop_id, temperature=0.2)
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=json.dumps(user_payload, default=str)),
            ]
        )
        raw = str(getattr(response, "content", "") or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        return parsed
    except Exception as exc:  # noqa: BLE001
        logger.warning("SOUL LLM extraction failed for shop %s: %s", shop_id, exc)
        return {}


def _merge_patterns(existing: List[Any], new_patterns: List[str], max_count: int) -> List[Dict[str, Any]]:
    """Merge new patterns into existing patterns, deduped by lower-cased text."""
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def push(content: str, source: str) -> None:
        normalized = content.strip()
        if not normalized:
            return
        key = normalized.lower()
        if key in seen:
            return
        seen.add(key)
        merged.append({"content": normalized, "source": source})

    # Keep new (most recent) at the front
    for content in new_patterns or []:
        push(str(content), source="latest_evolution")
    for entry in existing or []:
        if isinstance(entry, dict):
            push(str(entry.get("content") or ""), source=str(entry.get("source") or "historical"))
        elif isinstance(entry, str):
            push(entry, source="historical")

    return merged[:max_count]


def _merge_decisions(existing: List[Any], new_decisions: List[Dict[str, Any]], max_count: int = 10) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for entry in (new_decisions or []) + (existing or []):
        if isinstance(entry, dict):
            merged.append(entry)
        elif isinstance(entry, str):
            merged.append({"summary": entry})
        if len(merged) >= max_count:
            break
    return merged


def _merge_open_items(existing: List[Any], new_items: List[Dict[str, Any]], max_count: int = 10) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen_text: set[str] = set()

    def push(item: Dict[str, Any]) -> None:
        text_value = str(item.get("text") or item.get("commitment") or "").strip()
        if not text_value:
            return
        key = text_value.lower()
        if key in seen_text:
            return
        seen_text.add(key)
        merged.append({"text": text_value, "due_at": item.get("due_at")})

    for entry in new_items or []:
        if isinstance(entry, dict):
            push(entry)
    for entry in existing or []:
        if isinstance(entry, dict):
            push(entry)
        elif isinstance(entry, str):
            push({"text": entry})
        if len(merged) >= max_count:
            break

    return merged


# ─── Temporal activity ──────────────────────────────────────────────────────

@activity.defn
async def update_shop_soul_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Evolve a single shop's SOUL based on recent activity.

    Payload:
      shop_id       (required)
      reason        (optional) — "post_briefing" / "post_shop_ops" / "scheduled"
      force         (optional) — if True, ignore the free-tier 7-day cooldown
    """
    shop_id = int(payload["shop_id"])
    reason = str(payload.get("reason") or "scheduled")
    force = bool(payload.get("force") or False)

    tier = load_shop_subscription_tier(shop_id)
    is_premium = _is_premium(tier)

    db = SessionLocal()
    try:
        # Resolve shop name for nicer logs / prompts
        shop_row = db.execute(
            text("SELECT name FROM shops WHERE id = :shop_id"),
            {"shop_id": shop_id},
        ).first()
        shop_name = str(shop_row[0]) if shop_row else f"Shop {shop_id}"

        repo = AgentWorkRepository(db)
        soul = repo.get_or_create_shop_soul(shop_id)

        # Cooldown for free tier — at most one evolution per week
        if not is_premium and not force and soul.last_evolved_at:
            since_last = datetime.utcnow() - soul.last_evolved_at
            if since_last < timedelta(days=_FREE_UPDATE_INTERVAL_DAYS):
                return {
                    "ok": True,
                    "shop_id": shop_id,
                    "skipped": "cooldown",
                    "tier": tier,
                    "next_eligible_in_days": _FREE_UPDATE_INTERVAL_DAYS - since_last.days,
                }

        # Determine evidence window
        window_days = _PREMIUM_HISTORY_WINDOW_DAYS if is_premium else _FREE_HISTORY_WINDOW_DAYS
        since_dt = datetime.utcnow() - timedelta(days=window_days)
        if soul.last_evolved_at and not force:
            since_dt = max(since_dt, soul.last_evolved_at - timedelta(days=1))

        signals = _gather_recent_signals(shop_id, since_dt)

        soul_view = {
            "tone": soul.tone,
            "upsell_style": soul.upsell_style,
            "owner_communication": soul.owner_communication,
            "summary": soul.summary,
            "learned_patterns": list(soul.learned_patterns or []),
        }
        learnings = _llm_extract_learnings(shop_id, shop_name, soul_view, signals)

        if not learnings:
            return {
                "ok": True,
                "shop_id": shop_id,
                "skipped": "no_learnings",
                "tier": tier,
                "reason": reason,
            }

        # Persist raw learnings (pattern category) for traceability
        for content in (learnings.get("patterns") or [])[:_MAX_PATTERNS_PREMIUM]:
            repo.create_soul_learning(
                shop_id=shop_id,
                content=str(content)[:500],
                source=reason,
                category="pattern",
                confidence_score=0.7,
                evidence={"reason": reason},
            )

        max_patterns = _MAX_PATTERNS_PREMIUM if is_premium else _MAX_PATTERNS_FREE
        merged_patterns = _merge_patterns(
            list(soul.learned_patterns or []),
            list(learnings.get("patterns") or []),
            max_count=max_patterns,
        )
        merged_decisions = _merge_decisions(
            list(soul.recent_decisions or []),
            list(learnings.get("decisions") or []),
        )
        merged_open_items = _merge_open_items(
            list(soul.open_items or []),
            list(learnings.get("open_items") or []),
        )

        updates: Dict[str, Any] = {
            "learned_patterns": merged_patterns,
            "recent_decisions": merged_decisions,
            "open_items": merged_open_items,
            "last_evolved_at": datetime.utcnow(),
            "tier_scope": "premium" if is_premium else "basic",
            "rolling_window_days": _PREMIUM_HISTORY_WINDOW_DAYS if is_premium else _FREE_HISTORY_WINDOW_DAYS,
        }
        if learnings.get("tone") in {"friendly", "professional", "casual", "formal"}:
            updates["tone"] = str(learnings["tone"])
        if learnings.get("upsell_style") in {"soft", "moderate", "aggressive"}:
            updates["upsell_style"] = str(learnings["upsell_style"])
        if learnings.get("owner_communication") in {"voice", "text", "summary"}:
            updates["owner_communication"] = str(learnings["owner_communication"])
        if isinstance(learnings.get("summary"), str):
            updates["summary"] = learnings["summary"][:1200]

        repo.update_shop_soul(shop_id, **updates)

        result = {
            "ok": True,
            "shop_id": shop_id,
            "tier": tier,
            "reason": reason,
            "patterns_added": len(learnings.get("patterns") or []),
            "decisions_added": len(learnings.get("decisions") or []),
            "open_items_added": len(learnings.get("open_items") or []),
            "summary_updated": "summary" in updates,
        }
        logger.info(
            "SOUL updated shop=%s reason=%s tier=%s patterns_added=%d",
            shop_id, reason, tier, result["patterns_added"],
        )
        return result
    except Exception as exc:  # noqa: BLE001
        logger.exception("update_shop_soul_activity failed for shop %s", shop_id)
        return {"ok": False, "shop_id": shop_id, "error": str(exc)}
    finally:
        db.close()


__all__ = ["update_shop_soul_activity"]
