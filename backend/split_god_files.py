#!/usr/bin/env python3
"""
Split god files into domain sub-packages.

db_interface.py (1142 lines, single class) → backend/db/ package
agent_logic.py  (2544 lines, flat module)  → backend/agent/ package

Strategy:
  - Extract exact code sections by confirmed line numbers.
  - No logic changes whatsoever; only file organisation changes.
  - Each new file gets the correct imports for what it uses.
  - Both god files become thin facade re-exports (backward compat preserved).

Confirmed section boundaries (1-based, inclusive start):
  db_interface.py:
    1   : module docstring
    5   : imports start
    18  : class DatabaseInterface:
    27  : # --- User operations ---
    93  : # --- Shop operations ---
    213 : # --- Queue operations ---
    300 : # --- Employee operations ---
    357 : # --- Shop Service operations ---
    416 : # --- Shift operations ---  (contains conversation history at 442)
    516 : # --- Shop Customer Context (CRM) ---
    560 : # --- Agent / Category Support ---
    637 : # --- Agent Memory ---
    772 : # --- Analytics operations ---
    796 : # --- Helpers ---  (_model_to_dict)
    817 : # --- Agent Active Tool Helpers ---
    ~1138: # Singleton instance

  agent_logic.py:
    1   : imports
    25  : # --- Precompiled Regex for Hot Paths ---
    80  : helper functions (start of _extract_customer_details_for_join)
    177 : # --- Configuration ---
    186 : # --- Smart Query Processor ---
    264 : # --- Unified Query Analyzer ---  (ContextUpdates etc.)
    671 : # --- Category Manager ---
    937 : # --- Global Category Manager ---  (category_manager singleton)
    941 : # --- Data Models ---
    1016: # --- Create Agent ---
    1033: # --- Tools ---
    1385: # --- Master Agent ---
    2466: # --- Background Tasks ---
    2544: end
"""

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def read_lines(path: str):
    with open(path) as f:
        return f.readlines()


def write(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    print(f"  wrote {os.path.relpath(path, BASE)}")


def L(lines, start: int, end: int = None) -> str:
    """
    Extract lines [start, end) where start and end are 1-based.
    end=None means extract to end of file.
    """
    s = start - 1               # convert to 0-based
    e = end - 1 if end else None
    return "".join(lines[s:e])


def find_line(lines, pattern: str, start: int = 1) -> int:
    """Return the 1-based line number of the first line matching pattern after start."""
    import re
    rx = re.compile(pattern)
    for i, ln in enumerate(lines[start - 1:], start=start):
        if rx.search(ln):
            return i
    raise ValueError(f"Pattern not found after line {start}: {pattern!r}")


# ─────────────────────────────────────────────────────────────────────────────
# 1.  db_interface.py  →  backend/db/
# ─────────────────────────────────────────────────────────────────────────────

def split_db():
    print("\n=== Splitting db_interface.py ===")
    src = os.path.join(BASE, "db_interface.py")
    ls = read_lines(src)
    total = len(ls)

    # Confirm key lines (safety check)
    assert "class DatabaseInterface" in ls[17], f"Expected class at line 18, got: {ls[17]!r}"
    assert "User operations" in ls[26], f"Expected User operations at line 27"
    print(f"  db_interface.py: {total} lines, boundaries confirmed.")

    # Shared imports (lines 5-17, i.e. skip module docstring lines 1-4)
    db_imports = L(ls, 5, 18)

    def mixin_file(class_name: str, docstring: str, start: int, end: int) -> str:
        """Wrap a section of DatabaseInterface methods in a standalone mixin class."""
        body = L(ls, start, end)
        return (
            f'"""\n{docstring}\n"""\n'
            + db_imports
            + f"\n\nclass {class_name}:\n"
            + body
        )

    # --- db/base.py ---
    # get_session  : defined just before "# --- User operations ---" (lines after class def)
    get_session_start = find_line(ls, r"def get_session")
    get_session_end   = 27   # line 27 is "# --- User operations ---" - start of next section
    get_session_code  = L(ls, get_session_start, get_session_end)

    # _model_to_dict : lines 796-816  (796 = "# --- Helpers ---", 817 = "# --- Agent Active...")
    helpers_code = L(ls, 796, 817)

    db_base = (
        '"""\nDatabase base: session factory and _model_to_dict helper.\n"""\n'
        + db_imports
        + "\n\nclass DbBase:\n"
        + get_session_code
        + "\n"
        + helpers_code
    )
    write(os.path.join(BASE, "db/base.py"), db_base)

    # --- db/users.py ---
    write(os.path.join(BASE, "db/users.py"),
          mixin_file("UsersMixin", "User table operations.", 27, 93))

    # --- db/shops.py ---
    write(os.path.join(BASE, "db/shops.py"),
          mixin_file("ShopsMixin", "Shop table operations.", 93, 213))

    # --- db/queues.py ---
    write(os.path.join(BASE, "db/queues.py"),
          mixin_file("QueuesMixin", "Queue and queue-item operations.", 213, 300))

    # --- db/employees.py ---
    # Contains employee + service + shift + conversation history (442-515)
    write(os.path.join(BASE, "db/employees.py"),
          mixin_file("EmployeesMixin",
                     "Employee, shop-service, shift, and conversation-history operations.",
                     300, 516))

    # --- db/customers.py ---
    write(os.path.join(BASE, "db/customers.py"),
          mixin_file("CustomersMixin", "Shop customer CRM operations.", 516, 560))

    # --- db/knowledge.py ---
    # Covers Agent/Category Support (560) + Agent Memory (637) sections
    write(os.path.join(BASE, "db/knowledge.py"),
          mixin_file("KnowledgeMixin",
                     "Agent category aliases, knowledge, agent memory, and synonym operations.",
                     560, 772))

    # --- db/analytics.py ---
    # Analytics (772-795) + Agent Active Tool Helpers (817-singleton)
    # Skip Helpers (796-816) which goes to DbBase
    singleton_line = find_line(ls, r"^# Singleton instance")
    analytics_body = L(ls, 772, 796) + L(ls, 817, singleton_line)
    db_analytics = (
        '"""\nAnalytics operations and active queue/wait-time tool helpers.\n"""\n'
        + db_imports
        + "\n\nclass AnalyticsMixin:\n"
        + analytics_body
    )
    write(os.path.join(BASE, "db/analytics.py"), db_analytics)

    # --- db/interface.py ---
    singleton_body = L(ls, singleton_line)  # singleton + factory (rest of file)
    db_interface_py = (
        '"""\nDatabaseInterface — composes all domain mixins. Singleton at bottom.\n"""\n'
        "from db.base import DbBase\n"
        "from db.users import UsersMixin\n"
        "from db.shops import ShopsMixin\n"
        "from db.queues import QueuesMixin\n"
        "from db.employees import EmployeesMixin\n"
        "from db.customers import CustomersMixin\n"
        "from db.knowledge import KnowledgeMixin\n"
        "from db.analytics import AnalyticsMixin\n"
        "\n\n"
        "class DatabaseInterface(\n"
        "    DbBase,\n"
        "    UsersMixin,\n"
        "    ShopsMixin,\n"
        "    QueuesMixin,\n"
        "    EmployeesMixin,\n"
        "    CustomersMixin,\n"
        "    KnowledgeMixin,\n"
        "    AnalyticsMixin,\n"
        "):\n"
        '    """Unified database interface — all domain operations in one object."""\n'
        "    pass\n"
        "\n\n"
        + singleton_body
    )
    write(os.path.join(BASE, "db/interface.py"), db_interface_py)

    # --- db/__init__.py ---
    write(
        os.path.join(BASE, "db/__init__.py"),
        '"""Database sub-package — exposes the db_interface singleton."""\n'
        "from db.interface import DatabaseInterface, db_interface, get_db_interface\n\n"
        '__all__ = ["DatabaseInterface", "db_interface", "get_db_interface"]\n',
    )

    print("  db/ package created successfully.")


# ─────────────────────────────────────────────────────────────────────────────
# 2.  agent_logic.py  →  backend/agent/
# ─────────────────────────────────────────────────────────────────────────────

def split_agent():
    print("\n=== Splitting agent_logic.py ===")
    src = os.path.join(BASE, "agent_logic.py")
    ls = read_lines(src)
    total = len(ls)

    # Confirm key sections
    assert "Precompiled Regex" in ls[24], f"Expected regex section at line 25"
    assert "Configuration" in ls[176], f"Expected Config at line 177"
    print(f"  agent_logic.py: {total} lines, boundaries confirmed.")

    # Full original imports (lines 1-24)
    all_imports = L(ls, 1, 25)

    # ── agent/config.py ────────────────────────────────────────────────────────
    # Lines 177-185: Configuration section (ollama_url, model_name, model)
    config_py = (
        '"""\nOllama / Pydantic-AI model configuration.\n"""\n'
        + all_imports
        + "\n"
        + L(ls, 177, 186)
    )
    write(os.path.join(BASE, "agent/config.py"), config_py)

    # ── agent/regex_constants.py ───────────────────────────────────────────────
    # Lines 25-176: Precompiled regex + helper functions + TTS globals
    regex_py = (
        '"""\n'
        "Precompiled regex patterns, helper functions, and TTS client state.\n"
        '"""\n'
        + all_imports
        + "\n"
        + L(ls, 25, 177)
    )
    write(os.path.join(BASE, "agent/regex_constants.py"), regex_py)

    # ── agent/cache.py ────────────────────────────────────────────────────────
    # Lines 186-263: Smart Query Processor (embedder, SemanticCache, semantic_cache)
    cache_py = (
        '"""\nSentence-transformer embedder and semantic query cache.\n"""\n'
        + all_imports
        + "from agent.config import model\n"
        + "\n"
        + L(ls, 186, 264)
    )
    write(os.path.join(BASE, "agent/cache.py"), cache_py)

    # ── agent/analyzer.py ─────────────────────────────────────────────────────
    # Lines 264-670: ContextUpdates, IntentAnalysis, SearchRecoveryAnalysis,
    #                UnifiedQueryAnalyzer class + unified_query_analyzer singleton
    analyzer_py = (
        '"""\nContextUpdates / IntentAnalysis models and UnifiedQueryAnalyzer.\n"""\n'
        + all_imports
        + "from agent.config import model\n"
        + "from agent.cache import semantic_cache\n"
        + "\n"
        + L(ls, 264, 671)
    )
    write(os.path.join(BASE, "agent/analyzer.py"), analyzer_py)

    # ── agent/categories.py ───────────────────────────────────────────────────
    # Lines 671-940: CategoryManager class + category_manager singleton (937-940)
    categories_py = (
        '"""\nCategoryManager — dynamic DB-driven shop category system.\n"""\n'
        + all_imports
        + "from db_interface import db_interface\n"
        + "from redis_client import redis_client\n"
        + "\n"
        + L(ls, 671, 941)
    )
    write(os.path.join(BASE, "agent/categories.py"), categories_py)

    # ── agent/pydantic_agent.py ───────────────────────────────────────────────
    # Lines 941-1384: Data Models + System Prompt + create_master_agent + all tools
    # (Data Models 941-960, Dynamic System Prompt 961-1015, Create Agent 1016-1032,
    #  Tools 1033-1384)
    pydantic_agent_py = (
        '"""\n'
        "Pydantic-AI MasterAgent: data models, system prompt, agent creation, and tools.\n"
        '"""\n'
        + all_imports
        + "from agent.config import model\n"
        + "from agent.regex_constants import (\n"
        + "    _QUEUE_JOIN_REQUEST_RE, _APPOINTMENT_REQUEST_RE, _WAIT_TIME_REQUEST_RE,\n"
        + "    _CANCEL_REGISTRATION_RE, _REGISTRATION_INTERRUPT_INTENTS,\n"
        + "    _build_queue_join_form_event, _build_appointment_form_event,\n"
        + "    _extract_customer_details_for_join,\n"
        + "    _is_shop_queue_join_request, _is_appointment_request, _is_shop_wait_request,\n"
        + ")\n"
        + "from agent.categories import category_manager\n"
        + "from agent.analyzer import unified_query_analyzer, IntentAnalysis, ContextUpdates\n"
        + "from db_interface import db_interface\n"
        + "from redis_client import redis_client\n"
        + "\n"
        + L(ls, 941, 1385)
    )
    write(os.path.join(BASE, "agent/pydantic_agent.py"), pydantic_agent_py)

    # ── agent/master.py ───────────────────────────────────────────────────────
    # Lines 1385-2465: MasterAgent class
    master_py = (
        '"""\nMasterAgent — orchestrates intent routing, chat, and streaming responses.\n"""\n'
        + all_imports
        + "from agent.config import model\n"
        + "from agent.regex_constants import (\n"
        + "    _SENTENCE_BOUNDARY_RE, _MARKDOWN_BOLD_RE, _MARKDOWN_ITALIC_RE,\n"
        + "    _MARKDOWN_HEADING_RE, _MARKDOWN_CODE_RE, _MARKDOWN_LINK_RE,\n"
        + "    _EMOJI_RE, _WHITESPACE_MULTI_RE,\n"
        + "    _CANCEL_REGISTRATION_RE, _REGISTRATION_INTERRUPT_INTENTS,\n"
        + "    _QUEUE_JOIN_REQUEST_RE, _APPOINTMENT_REQUEST_RE, _WAIT_TIME_REQUEST_RE,\n"
        + "    _TTS_TIMEOUT_SECONDS, _tts_cache, _TTS_CACHE_MAX_ITEMS, _get_tts_client,\n"
        + "    _extract_customer_details_for_join,\n"
        + "    _is_shop_queue_join_request, _is_appointment_request, _is_shop_wait_request,\n"
        + "    _build_queue_join_form_event, _build_appointment_form_event,\n"
        + ")\n"
        + "from agent.cache import semantic_cache\n"
        + "from agent.analyzer import (\n"
        + "    unified_query_analyzer, ContextUpdates, IntentAnalysis, SearchRecoveryAnalysis,\n"
        + ")\n"
        + "from agent.categories import category_manager\n"
        + "from agent.pydantic_agent import (\n"
        + "    master_pydantic_agent, MasterAgentDeps, MasterResponse,\n"
        + "    get_master_system_prompt, create_master_agent,\n"
        + "    search_shops, join_queue, get_wait_time, check_queue_status,\n"
        + "    start_registration, check_pricing, see_features, see_faq, see_testimonials,\n"
        + ")\n"
        + "from db_interface import db_interface\n"
        + "from redis_client import redis_client\n"
        + "\n"
        + L(ls, 1385, 2466)
    )
    write(os.path.join(BASE, "agent/master.py"), master_py)

    # ── agent/background.py ───────────────────────────────────────────────────
    # Lines 2466-end: Background Tasks + Admin Functions
    #
    # Important: the refresh_loop does:
    #   global master_pydantic_agent
    #   master_pydantic_agent = create_master_agent()
    # After the split this updates background.py's module-level master_pydantic_agent.
    # That's fine — MasterAgent.chat() uses self.agent (not the module global), and
    # MasterAgent.refresh_agent() properly updates self.agent directly.
    bg_py = (
        '"""\nBackground refresh tasks and admin helper functions.\n"""\n'
        + all_imports
        + "from agent.categories import category_manager\n"
        + "from agent.pydantic_agent import create_master_agent, master_pydantic_agent\n"
        + "\n"
        + L(ls, 2466)
    )
    write(os.path.join(BASE, "agent/background.py"), bg_py)

    # ── agent/__init__.py ─────────────────────────────────────────────────────
    write(os.path.join(BASE, "agent/__init__.py"), "")

    print("  agent/ package created successfully.")


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Write backward-compatible facade files
# ─────────────────────────────────────────────────────────────────────────────

def write_facades():
    print("\n=== Writing facade files ===")

    # ── db_interface.py ───────────────────────────────────────────────────────
    facade_db = (
        '"""\n'
        "db_interface.py — backward-compatible facade.\n\n"
        "DatabaseInterface and db_interface have been moved to backend/db/.\n"
        "This file re-exports them so all existing imports continue to work.\n"
        '"""\n'
        "from db.interface import DatabaseInterface, db_interface, get_db_interface  # noqa: F401\n\n"
        '__all__ = ["DatabaseInterface", "db_interface", "get_db_interface"]\n'
    )
    write(os.path.join(BASE, "db_interface.py"), facade_db)

    # ── agent_logic.py ────────────────────────────────────────────────────────
    facade_agent = (
        '"""\n'
        "agent_logic.py — backward-compatible facade.\n\n"
        "All logic is in backend/agent/. This re-exports the full public API so that:\n"
        "  from agent_logic import MasterAgent       # routers/agent.py\n"
        "  from agent_logic import semantic_cache    # main.py\n"
        "  import agent_logic                        # main.py (pre-warm)\n"
        "all continue to work without modification.\n"
        '"""\n\n'
        "# ── Model config ──────────────────────────────────────────────────────────\n"
        "from agent.config import ollama_url, model_name, model  # noqa: F401\n\n"
        "# ── Regex patterns, helpers, TTS globals ──────────────────────────────────\n"
        "from agent.regex_constants import (  # noqa: F401\n"
        "    _SENTENCE_BOUNDARY_RE, _MARKDOWN_BOLD_RE, _MARKDOWN_ITALIC_RE,\n"
        "    _MARKDOWN_HEADING_RE, _MARKDOWN_CODE_RE, _MARKDOWN_LINK_RE, _EMOJI_RE,\n"
        "    _WHITESPACE_MULTI_RE, _CANCEL_REGISTRATION_RE,\n"
        "    _REGISTRATION_INTERRUPT_INTENTS,\n"
        "    _QUEUE_JOIN_REQUEST_RE, _APPOINTMENT_REQUEST_RE, _WAIT_TIME_REQUEST_RE,\n"
        "    _NAME_CAPTURE_RE, _PHONE_CAPTURE_RE,\n"
        "    _TTS_TIMEOUT_SECONDS, _tts_client, _tts_cache, _TTS_CACHE_MAX_ITEMS,\n"
        "    _get_tts_client,\n"
        "    _extract_customer_details_for_join, _is_shop_queue_join_request,\n"
        "    _is_appointment_request, _is_shop_wait_request,\n"
        "    _build_queue_join_form_event, _build_appointment_form_event,\n"
        ")\n\n"
        "# ── Semantic cache ────────────────────────────────────────────────────────\n"
        "from agent.cache import get_embedder, SemanticCache, semantic_cache  # noqa: F401\n\n"
        "# ── Query analyzer and intent models ─────────────────────────────────────\n"
        "from agent.analyzer import (  # noqa: F401\n"
        "    ContextUpdates, IntentAnalysis, SearchRecoveryAnalysis,\n"
        "    UnifiedQueryAnalyzer, unified_query_analyzer,\n"
        ")\n\n"
        "# ── Category manager ─────────────────────────────────────────────────────\n"
        "from agent.categories import CategoryManager, category_manager  # noqa: F401\n\n"
        "# ── Pydantic-AI agent, data models, tools ────────────────────────────────\n"
        "from agent.pydantic_agent import (  # noqa: F401\n"
        "    MasterAgentDeps, MasterResponse,\n"
        "    get_master_system_prompt, create_master_agent, master_pydantic_agent,\n"
        "    search_shops, check_pricing, see_features, see_faq, see_testimonials,\n"
        "    join_queue, get_wait_time, check_queue_status, start_registration,\n"
        ")\n\n"
        "# ── MasterAgent class ─────────────────────────────────────────────────────\n"
        "from agent.master import MasterAgent  # noqa: F401\n\n"
        "# ── Background tasks + admin helpers ─────────────────────────────────────\n"
        "from agent.background import (  # noqa: F401\n"
        "    start_background_tasks, add_category_admin, get_categories_admin,\n"
        "    get_learnings_admin, get_extraction_cache_admin,\n"
        ")\n"
    )
    write(os.path.join(BASE, "agent_logic.py"), facade_agent)

    print("  Facade files written.")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting god-file split...")
    split_db()
    split_agent()
    write_facades()
    print("\n✓ Split complete.")
    print("  Next: docker compose up -d --build backend && python3 e2e_test.py")
