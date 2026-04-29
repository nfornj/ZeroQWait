"""
agent_logic.py — backward-compatible facade.

All logic is in backend/agent/. This re-exports the full public API so that:
  from agent_logic import MasterAgent       # routers/agent.py
  from agent_logic import semantic_cache    # main.py
  import agent_logic                        # main.py (pre-warm)
all continue to work without modification.
"""

# ── Model config ──────────────────────────────────────────────────────────
from agent.config import ollama_url, model_name, model  # noqa: F401

# ── Regex patterns, helpers, TTS globals ──────────────────────────────────
from agent.regex_constants import (  # noqa: F401
    _SENTENCE_BOUNDARY_RE, _MARKDOWN_BOLD_RE, _MARKDOWN_ITALIC_RE,
    _MARKDOWN_HEADING_RE, _MARKDOWN_CODE_RE, _MARKDOWN_LINK_RE, _EMOJI_RE,
    _WHITESPACE_MULTI_RE, _CANCEL_REGISTRATION_RE,
    _REGISTRATION_INTERRUPT_INTENTS,
    _QUEUE_JOIN_REQUEST_RE, _APPOINTMENT_REQUEST_RE, _WAIT_TIME_REQUEST_RE,
    _NAME_CAPTURE_RE, _PHONE_CAPTURE_RE,
    _TTS_TIMEOUT_SECONDS, _tts_client, _tts_cache, _TTS_CACHE_MAX_ITEMS,
    _get_tts_client,
    _extract_customer_details_for_join, _is_shop_queue_join_request,
    _is_appointment_request, _is_shop_wait_request,
    _build_queue_join_form_event, _build_appointment_form_event,
)

# ── Semantic cache ────────────────────────────────────────────────────────
from agent.cache import get_embedder, SemanticCache, semantic_cache  # noqa: F401

# ── Query analyzer and intent models ─────────────────────────────────────
from agent.analyzer import (  # noqa: F401
    ContextUpdates, IntentAnalysis, SearchRecoveryAnalysis,
    UnifiedQueryAnalyzer, unified_query_analyzer,
)

# ── Category manager ─────────────────────────────────────────────────────
from agent.categories import CategoryManager, category_manager  # noqa: F401

# ── Pydantic-AI agent, data models, tools ────────────────────────────────
from agent.pydantic_agent import (  # noqa: F401
    MasterAgentDeps, MasterResponse,
    get_master_system_prompt, create_master_agent, master_pydantic_agent,
    search_shops, check_pricing, see_features, see_faq, see_testimonials,
    join_queue, get_wait_time, check_queue_status, start_registration,
)

# ── MasterAgent class ─────────────────────────────────────────────────────
from agent.master import MasterAgent  # noqa: F401

# ── Background tasks + admin helpers ─────────────────────────────────────
from agent.background import (  # noqa: F401
    start_background_tasks, add_category_admin, get_categories_admin,
    get_learnings_admin, get_extraction_cache_admin,
)
