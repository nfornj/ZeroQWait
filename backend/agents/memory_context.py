"""Utilities for selecting and formatting tenant-scoped agent memories."""

import json
from typing import Dict, List


def merge_and_rank_memories(
    relevant: List[Dict],
    recent: List[Dict],
    max_items: int = 8,
) -> List[Dict]:
    """Merge two memory lists, preserving priority: relevant first, then recent, dedup by id."""
    ordered: List[Dict] = []
    seen_ids = set()

    for memory in (relevant or []) + (recent or []):
        memory_id = memory.get("id")
        if memory_id in seen_ids:
            continue
        seen_ids.add(memory_id)
        ordered.append(memory)
        if len(ordered) >= max_items:
            break

    return ordered


def format_memory_context(memories: List[Dict], max_chars_per_item: int = 240) -> str:
    """Build a compact system-context string from selected memories."""
    if not memories:
        return ""

    lines = [
        "Tenant memory context (shop-scoped):",
        "Use this as supporting context, but prioritize the latest user message.",
    ]

    for idx, memory in enumerate(memories, start=1):
        memory_type = memory.get("memory_type", "unknown")
        content = str(memory.get("content", "")).strip().replace("\n", " ")
        if len(content) > max_chars_per_item:
            content = f"{content[:max_chars_per_item].rstrip()}..."
        lines.append(f"{idx}. [{memory_type}] {content}")

    return "\n".join(lines)


def save_conversation_turn(
    redis_client,
    shop_id: str,
    user_id: str,
    role: str,
    content: str,
    max_turns: int = 20,
) -> None:
    """Save one conversation message to Redis list conv:{shop_id}:{user_id}."""
    if not getattr(redis_client, "enabled", False):
        return

    client = getattr(redis_client, "client", None)
    if client is None:
        return

    if role not in {"user", "assistant"}:
        return

    payload = json.dumps({"role": role, "content": str(content or "")})
    key = f"conv:{shop_id}:{user_id}"

    try:
        client.rpush(key, payload)
        client.ltrim(key, -max_turns * 2, -1)
    except Exception:
        return


def get_conversation_history(redis_client, shop_id: str, user_id: str) -> List[Dict]:
    """Get stored conversation messages from Redis key conv:{shop_id}:{user_id}."""
    if not getattr(redis_client, "enabled", False):
        return []

    client = getattr(redis_client, "client", None)
    if client is None:
        return []

    key = f"conv:{shop_id}:{user_id}"
    try:
        raw_items = client.lrange(key, 0, -1)
    except Exception:
        return []

    if not raw_items:
        return []

    history: List[Dict] = []
    for raw in raw_items:
        try:
            parsed = json.loads(raw)
        except Exception:
            continue

        role = parsed.get("role")
        content = parsed.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            history.append({"role": role, "content": content})

    return history
