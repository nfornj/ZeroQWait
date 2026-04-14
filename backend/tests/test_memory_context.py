from agents.memory_context import merge_and_rank_memories, format_memory_context


def test_merge_and_rank_memories_prioritizes_relevant_and_dedupes():
    relevant = [
        {"id": 2, "memory_type": "chat_user", "content": "show weekly revenue"},
        {"id": 3, "memory_type": "chat_assistant", "content": "weekly totals returned"},
    ]
    recent = [
        {"id": 1, "memory_type": "chat_user", "content": "hello"},
        {"id": 2, "memory_type": "chat_user", "content": "duplicate should be removed"},
    ]

    merged = merge_and_rank_memories(relevant, recent, max_items=3)

    assert [m["id"] for m in merged] == [2, 3, 1]


def test_format_memory_context_returns_empty_for_no_memories():
    assert format_memory_context([]) == ""


def test_format_memory_context_renders_compact_lines():
    memories = [
        {"id": 7, "memory_type": "chat_user", "content": "Need monthly trend as csv"},
        {"id": 8, "memory_type": "chat_assistant", "content": "Provided chart and csv option"},
    ]

    output = format_memory_context(memories, max_chars_per_item=120)

    assert "Tenant memory context (shop-scoped):" in output
    assert "[chat_user] Need monthly trend as csv" in output
    assert "[chat_assistant] Provided chart and csv option" in output
