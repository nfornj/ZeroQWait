"""Utilities for selecting and formatting tenant-scoped agent memories."""

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
