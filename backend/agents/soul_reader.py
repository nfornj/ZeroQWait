"""SOUL Reader — loads each shop's persistent personality and formats it for prompt injection.

The SOUL is the agent's living identity for a shop:
  * Tone, upsell style, owner communication preference
  * Learned patterns (e.g. "owner cancels Tuesday 3pm slots")
  * Recent decisions (last actions and approvals)
  * Open items (commitments still pending)

Tier behavior (from `users.subscription_tier` joined via `shops.owner_id`):
  * free       → only patterns/decisions observed in the last 30 days
  * premium    → full SOUL, no time window
  * enterprise → same as premium

This module is read-only and side-effect free; safe to call from inside a
LangGraph node or any sync FastAPI handler. Returns an empty string when the
shop has no SOUL row yet (the first run for that shop).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from database import SessionLocal
from modules.agent.models import Commitment, ShopSoul, SoulLearning
from modules.agent.work_repository import AgentWorkRepository

from .llm_factory import PREMIUM_SUBSCRIPTION_TIERS, load_shop_subscription_tier

logger = logging.getLogger(__name__)


_FREE_PATTERN_LIMIT = 5
_PREMIUM_PATTERN_LIMIT = 25
_RECENT_DECISION_LIMIT = 5
_OPEN_ITEM_LIMIT = 5
_FREE_WINDOW_DAYS = 30


def _is_premium(tier: str) -> bool:
    return tier in PREMIUM_SUBSCRIPTION_TIERS


def _format_pattern_list(patterns: List[Dict[str, Any]], limit: int) -> List[str]:
    if not patterns:
        return []
    out: List[str] = []
    for entry in patterns[:limit]:
        if isinstance(entry, dict):
            content = str(entry.get("content") or entry.get("pattern") or "").strip()
            if content:
                out.append(content)
        elif isinstance(entry, str):
            value = entry.strip()
            if value:
                out.append(value)
    return out


def _format_decision_list(decisions: List[Dict[str, Any]], limit: int) -> List[str]:
    if not decisions:
        return []
    out: List[str] = []
    for entry in decisions[:limit]:
        if not isinstance(entry, dict):
            continue
        when = str(entry.get("date") or entry.get("at") or "").strip()
        what = str(entry.get("summary") or entry.get("action") or "").strip()
        if not what:
            continue
        out.append(f"{when}: {what}" if when else what)
    return out


def _format_open_items(open_items: List[Dict[str, Any]], limit: int) -> List[str]:
    if not open_items:
        return []
    out: List[str] = []
    for entry in open_items[:limit]:
        if isinstance(entry, dict):
            text = str(entry.get("text") or entry.get("commitment") or "").strip()
            due = str(entry.get("due") or entry.get("due_at") or "").strip()
            if text:
                out.append(f"{text} (due {due})" if due else text)
        elif isinstance(entry, str):
            value = entry.strip()
            if value:
                out.append(value)
    return out


def _recent_window_filter_dt() -> datetime:
    return datetime.utcnow() - timedelta(days=_FREE_WINDOW_DAYS)


def load_soul_snapshot(shop_id: int) -> Optional[Dict[str, Any]]:
    """Read the raw SOUL row + supporting learnings/commitments for a shop.

    Returns ``None`` when no SOUL row exists yet (the very first run for the shop).
    Tier-aware: free shops see only the last 30 days of learnings/commitments.
    """
    if not shop_id:
        return None

    tier = load_shop_subscription_tier(shop_id)
    is_premium = _is_premium(tier)

    db = SessionLocal()
    try:
        soul = db.query(ShopSoul).filter(ShopSoul.shop_id == shop_id).first()
        if soul is None:
            return None

        # Pull recent graduated learnings as supplementary patterns
        learning_query = (
            db.query(SoulLearning)
            .filter(SoulLearning.shop_id == shop_id, SoulLearning.graduated.is_(True))
            .order_by(SoulLearning.observed_at.desc())
        )
        if not is_premium:
            learning_query = learning_query.filter(
                SoulLearning.observed_at >= _recent_window_filter_dt()
            )
        learnings = learning_query.limit(
            _PREMIUM_PATTERN_LIMIT if is_premium else _FREE_PATTERN_LIMIT
        ).all()

        # Pull pending commitments to surface as "open items"
        repo = AgentWorkRepository(db)
        pending_commitments = repo.list_pending_commitments(
            shop_id, limit=_OPEN_ITEM_LIMIT
        )

        snapshot = {
            "tier": tier,
            "is_premium": is_premium,
            "tone": soul.tone,
            "upsell_style": soul.upsell_style,
            "owner_communication": soul.owner_communication,
            "summary": soul.summary,
            "personality": soul.personality or {},
            "learned_patterns": list(soul.learned_patterns or []),
            "recent_decisions": list(soul.recent_decisions or []),
            "open_items": list(soul.open_items or []),
            "graduated_learnings": [
                {"content": lr.content, "category": lr.category}
                for lr in learnings
            ],
            "pending_commitments": [
                {
                    "text": c.commitment,
                    "due_at": c.due_at.isoformat() if c.due_at else None,
                    "made_by": c.made_by,
                }
                for c in pending_commitments
            ],
            "last_evolved_at": soul.last_evolved_at.isoformat() if soul.last_evolved_at else None,
        }
        return snapshot
    except Exception as exc:  # noqa: BLE001
        logger.warning("load_soul_snapshot failed for shop %s: %s", shop_id, exc)
        return None
    finally:
        db.close()


def format_soul_for_prompt(shop_id: int) -> str:
    """Return a compact ``SystemMessage``-ready SOUL block for the given shop.

    Empty string when there is no SOUL yet. Capped output keeps the prompt
    overhead well under ~600 tokens for free tier and ~1.5k for premium.
    """
    snapshot = load_soul_snapshot(shop_id)
    if not snapshot:
        return ""

    is_premium = bool(snapshot.get("is_premium"))
    pattern_limit = _PREMIUM_PATTERN_LIMIT if is_premium else _FREE_PATTERN_LIMIT

    lines: List[str] = ["SHOP SOUL (persistent agent identity for this shop):"]

    persona_bits: List[str] = []
    if snapshot.get("tone"):
        persona_bits.append(f"tone={snapshot['tone']}")
    if snapshot.get("upsell_style"):
        persona_bits.append(f"upsell={snapshot['upsell_style']}")
    if snapshot.get("owner_communication"):
        persona_bits.append(f"owner_prefers={snapshot['owner_communication']}")
    if persona_bits:
        lines.append("Personality: " + ", ".join(persona_bits))

    summary = (snapshot.get("summary") or "").strip()
    if summary:
        # Cap inline summary length to stay prompt-budget friendly
        lines.append(f"Summary: {summary[:400]}")

    patterns: List[str] = _format_pattern_list(snapshot.get("learned_patterns", []), pattern_limit)
    grad_learnings = snapshot.get("graduated_learnings") or []
    for learning in grad_learnings:
        if len(patterns) >= pattern_limit:
            break
        text = str(learning.get("content") or "").strip()
        if text and text not in patterns:
            patterns.append(text)
    if patterns:
        lines.append("Learned patterns:")
        lines.extend(f"  - {p}" for p in patterns)

    decisions = _format_decision_list(snapshot.get("recent_decisions", []), _RECENT_DECISION_LIMIT)
    if decisions:
        lines.append("Recent decisions:")
        lines.extend(f"  - {d}" for d in decisions)

    open_items = _format_open_items(snapshot.get("open_items", []), _OPEN_ITEM_LIMIT)
    pending = snapshot.get("pending_commitments") or []
    for entry in pending:
        if len(open_items) >= _OPEN_ITEM_LIMIT:
            break
        text = str(entry.get("text") or "").strip()
        due = str(entry.get("due_at") or "").strip()
        if text:
            line = f"{text} (due {due[:10]})" if due else text
            if line not in open_items:
                open_items.append(line)
    if open_items:
        lines.append("Open items / commitments:")
        lines.extend(f"  - {o}" for o in open_items)

    if not is_premium:
        lines.append(
            f"(Free tier — showing patterns from last {_FREE_WINDOW_DAYS} days only.)"
        )

    lines.append(
        "Use this identity as background context. Honour learned patterns "
        "and tone, but always prioritise the latest owner/customer message."
    )

    return "\n".join(lines)


__all__ = ["format_soul_for_prompt", "load_soul_snapshot"]
