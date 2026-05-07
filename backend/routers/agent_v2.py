"""
FastAPI router for LangGraph-based owner-facing agent (v2).

Endpoints:
- POST /api/v2/agent/chat - Synchronous chat
- POST /api/v2/agent/chat/stream - SSE streaming chat
- POST /api/v2/agent/approve - Approve/reject HITL action
- POST /api/v2/agent/notifications/{notification_id}/read - Mark notification as read
- POST /api/v2/agent/notifications/read-all - Mark all notifications as read
- GET /api/v2/agent/history - Get conversation history
- GET /api/v2/agent/pending - Get pending approvals
- GET /api/v2/agent/feed - Get persisted feed events
- GET /api/v2/agent/health - Health check

Authentication:
- All endpoints require JWT bearer token
- JWT must contain owner's user_id
- Request must include shop_id (extracted from JWT shops list)
- Authorization: User must be owner of the shop

Multi-tenancy:
- tenant_id (shop_id) injected into AgentState and all tool calls
- Checkpoint thread_id = f"tenant_{shop_id}_{user_id}"
- All database queries run in isolated schema

Streaming (SSE):
- Event types: text, agent_switch, tool_call, tool_result, approval_required, actions, sentence
- [DONE] marks end of stream
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from typing import Dict, Any, cast, Optional, List
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import time
import re
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import text

from redis_client import redis_client as _redis
from langgraph.types import Command

from agents import approval_policy
from agents import chat_service as _chat_service
from agents.supervisor import create_supervisor_runnable
from agents.briefings import (
    build_owner_briefing,
    enrich_pending_approval_payload,
    get_cached_shop_briefing_snapshot,
    get_shop_alert_history,
    refresh_shop_briefing_cache,
)
from agents.memory_context import (
    format_memory_context,
    get_conversation_history,
    merge_and_rank_memories,
)
from agents.state import AgentState
from agents.checkpoints import build_checkpoint_config, get_sync_checkpoint_saver
from agents.chat_service import (
    _create_chat_work_context,
    _finalize_chat_work_context,
    _persist_chat_turn_memory,
    _state_last_text,
)
from agents.tools import finance_tools
from agents.document_store import (
    _OWNER_DOCUMENT_ALLOWED_EXTENSIONS,
    _OWNER_DOCUMENT_ALLOWED_MIME_TYPES,
    _OWNER_DOCUMENT_MAX_BYTES,
    _OWNER_DOCUMENT_MAX_FILES,
    _chunk_owner_document_text,
    _document_memory_query,
    _extract_owner_document_text,
    _get_owner_document_or_404,
    _reindex_owner_document_in_session,
    _sanitize_document_name,
    _sanitize_relative_document_path,
    _serialize_owner_document,
)
from shared.auth_utils import get_current_user
from db_interface import DatabaseInterface
from database import SessionLocal
from modules.agent.models import AgentDocument, AgentMemory, ApprovalStatus, GoalSource, GoalStatus, PolicyMode, RunStatus
from modules.agent.work_repository import AgentWorkRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/agent", tags=["agent_v2"])
db_interface = DatabaseInterface()


def _sync_chat_service_bindings() -> None:
    _chat_service.SessionLocal = SessionLocal
    _chat_service.AgentWorkRepository = AgentWorkRepository
    _chat_service.db_interface = db_interface


def _get_pending_approval_payload(
    shop_id: int,
    user_id: int,
    metrics: Optional[Dict[str, Any]] = None,
    *,
    runnable: Any = None,
) -> list[Dict[str, Any]]:
    _sync_chat_service_bindings()
    effective_runnable = _SUPERVISOR_RUNNABLE if runnable is None else runnable
    if not hasattr(effective_runnable, "get_state"):
        effective_runnable = None
    return _chat_service._get_pending_approval_payload(
        shop_id,
        user_id,
        metrics=metrics,
        runnable=effective_runnable,
    )


def _get_current_pending_approval(
    shop_id: int,
    user_id: int,
    *,
    runnable: Any = None,
) -> Optional[Dict[str, Any]]:
    _sync_chat_service_bindings()
    effective_runnable = _SUPERVISOR_RUNNABLE if runnable is None else runnable
    if not hasattr(effective_runnable, "get_state"):
        effective_runnable = None
    return _chat_service._get_current_pending_approval(
        shop_id,
        user_id,
        runnable=effective_runnable,
    )


def _record_approval_decision(**kwargs: Any) -> None:
    _sync_chat_service_bindings()
    _chat_service._record_approval_decision(**kwargs)


def _resume_persisted_approval(**kwargs: Any) -> Optional[Dict[str, Any]]:
    _sync_chat_service_bindings()
    return _chat_service._resume_persisted_approval(**kwargs)

# ---------------------------------------------------------------------------
# Real-time thinking-step metadata for the streaming UI
# ---------------------------------------------------------------------------

# LangGraph node names that are surfaced as visible pipeline steps in the UI.
_THINKING_NODES: frozenset = frozenset(
    {"classify_intent", "plan_and_route", "execute_plan", "synthesize_response"}
)

_AGENT_DISPLAY_LABELS: Dict[str, str] = {
    "receptionist": "Receptionist",
    "finance": "Finance Manager",
    "hr": "HR Assistant",
    "booking": "Receptionist",
    "crm": "CRM Assistant",
}


def _thinking_label_active(node: str, routed_agent: Optional[str]) -> str:
    has_agent = routed_agent and routed_agent not in ("supervisor", "general")
    agent_name = _AGENT_DISPLAY_LABELS.get(routed_agent or "", "Specialist")
    return {
        "classify_intent": "Classifying your request",
        "plan_and_route": f"Routing to {agent_name}" if has_agent else "Routing request",
        "execute_plan": f"Running {agent_name}" if has_agent else "Processing request",
        "synthesize_response": "Generating response",
    }.get(node, node)


def _thinking_label_done(node: str, routed_agent: Optional[str]) -> str:
    has_agent = routed_agent and routed_agent not in ("supervisor", "general")
    agent_name = _AGENT_DISPLAY_LABELS.get(routed_agent or "", "Specialist")
    return {
        "classify_intent": f"Classified {agent_name}" if has_agent else "Classified General",
        "plan_and_route": f"{agent_name}" if has_agent else "Supervisor",
        "execute_plan": f"{agent_name} complete" if has_agent else "Processing complete",
        "synthesize_response": "Response ready",
    }.get(node, f"{node} complete")


def _extract_current_agent_from_output(out: Any) -> Optional[str]:
    """Extract current_agent from a node output — handles both plain dict and LangGraph Command."""
    if isinstance(out, dict):
        return out.get("current_agent") or None
    # LangGraph Command object has an .update dict
    if hasattr(out, "update") and isinstance(getattr(out, "update", None), dict):
        return out.update.get("current_agent") or None
    return None


def _extract_metadata_from_output(out: Any) -> Dict[str, Any]:
    """Extract metadata from a node output — handles both plain dict and LangGraph Command."""
    if isinstance(out, dict):
        metadata = out.get("metadata")
        return metadata if isinstance(metadata, dict) else {}
    if hasattr(out, "update") and isinstance(getattr(out, "update", None), dict):
        metadata = out.update.get("metadata")
        return metadata if isinstance(metadata, dict) else {}
    return {}


def _normalize_reasoning_events(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, list):
        return []

    events: list[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("text"), str) and item.get("text", "").strip():
            events.append(item)
    return events


def _checkpoint_thread_id(shop_id: int, user_id: int) -> str:
    return f"tenant_{shop_id}_{user_id}"


def _sync_chat_timeout_seconds() -> float:
    raw_value = os.getenv("AGENT_SYNC_TIMEOUT_SECONDS", "50")
    try:
        return max(float(raw_value), 1.0)
    except (TypeError, ValueError):
        return 50.0


def _is_service_customer_count_question(message: str) -> bool:
    normalized = " ".join(str(message or "").lower().split())
    if not normalized:
        return False

    has_service_subject = bool(re.search(r"\bservices?\b", normalized))
    has_customer_subject = bool(
        re.search(r"\b(?:customers?|clients?|visits?|attended|served)\b", normalized)
    )
    wants_breakdown = bool(
        re.search(r"\b(?:for each|each service|per service|by service|service[- ]wise|breakdown)\b", normalized)
    )
    return has_service_subject and has_customer_subject and wants_breakdown


def _is_today_revenue_question(message: str) -> bool:
    normalized = " ".join(str(message or "").lower().split())
    if not normalized:
        return False

    has_revenue_subject = bool(re.search(r"\b(?:revenue|sales|earned|earnings|income)\b", normalized))
    has_today_window = bool(re.search(r"\b(?:today|todays|today's|this day)\b", normalized))
    return has_revenue_subject and has_today_window


def _is_top_services_question(message: str) -> bool:
    normalized = " ".join(str(message or "").lower().split())
    if not normalized:
        return False

    has_service_subject = bool(re.search(r"\bservices?\b", normalized))
    has_ranking_intent = bool(
        re.search(r"\b(?:top|best|highest|most popular|best-selling|best selling|rank|ranking)\b", normalized)
    )
    return has_service_subject and has_ranking_intent and not _is_service_customer_count_question(message)


def _is_time_window_followup(message: str) -> bool:
    normalized = " ".join(str(message or "").lower().split())
    if not normalized:
        return False

    if re.search(r"\b(?:queue|customer service|wait time|employee|employees|staff|staffing|shift|shifts|appointment|appointments|close|open|reopen|pause|resume)\b", normalized):
        return False

    has_followup_prefix = bool(re.match(r"^(?:what about|how about|and|compare)\b", normalized))
    has_time_window = bool(
        re.search(
            r"\b(?:today|yesterday|this|last|past|previous)\s+(?:\d{1,3}|[a-z]+)?\s*"
            r"(?:days?|weeks?|months?|years?|week|month|year)\b",
            normalized,
        )
        or re.search(r"\b\d{1,3}\s+(?:days?|weeks?|months?|years?)\b", normalized)
        or re.search(r"\b(?:today|yesterday|this week|last week|this month|last month)\b", normalized)
    )
    has_new_subject = bool(
        re.search(
            r"\b(?:revenue|sales|services?|customers?|clients?|visits?|invoices?|payments?|pos|refunds?)\b",
            normalized,
        )
    )
    is_bare_time_window = bool(
        re.fullmatch(
            r"(?:today|yesterday|this\s+week|last\s+week|this\s+month|last\s+month|"
            r"(?:\d{1,3}|[a-z]+)\s+(?:days?|weeks?|months?|years?)|"
            r"(?:last|past|previous)\s+(?:\d{1,3}|[a-z]+)\s+(?:days?|weeks?|months?|years?))"
            r"[?.!]?",
            normalized,
        )
    )
    return has_time_window and (has_followup_prefix or is_bare_time_window or (normalized.startswith("for ") and not has_new_subject))


def _finance_followup_key(user_id: int) -> str:
    return f"agent:last_finance_context:{user_id}"


def _remember_direct_finance_context(shop_id: int, user_id: int, operation: str, message: str) -> None:
    _redis.tenant_set(
        shop_id,
        _finance_followup_key(user_id),
        {
            "operation": operation,
            "last_message": message,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        ttl=3600,
    )


def _load_direct_finance_followup_operation(shop_id: int, user_id: int, message: str) -> Optional[str]:
    if not _is_time_window_followup(message):
        return None

    context = _redis.tenant_get(shop_id, _finance_followup_key(user_id))
    if not isinstance(context, dict):
        return None

    operation = str(context.get("operation") or "").strip()
    if operation in {"service_customer_counts", "top_services"}:
        return operation
    return None


def _format_service_customer_counts(result: Dict[str, Any]) -> str:
    if result.get("error"):
        return f"I couldn't pull the service customer counts: {result['error']}"

    services = list(result.get("services") or [])
    window = str(result.get("window_display") or result.get("window") or "the selected period")
    if not services:
        return f"I don't see any completed customer visits by service for {window}."

    lines = []
    for service in services[:10]:
        name = service.get("service_name") or "Unknown service"
        count = int(service.get("customer_count", 0) or 0)
        revenue = float(service.get("revenue", 0.0) or 0.0)
        lines.append(f"- {name}: {count} customer{'s' if count != 1 else ''} (${revenue:.2f})")

    total = int(result.get("total_customers", 0) or 0)
    return (
        f"Customers served by service for {window}: {total} total customer"
        f"{'s' if total != 1 else ''}.\n"
        + "\n".join(lines)
    )


def _format_daily_revenue(result: Dict[str, Any]) -> str:
    if result.get("error"):
        return f"I couldn't pull today's revenue: {result['error']}"

    total_revenue = float(result.get("total_revenue", 0.0) or 0.0)
    completed_services = int(result.get("completed_services", 0) or 0)
    total_customers = int(result.get("total_customers", 0) or 0)
    average_transaction = float(result.get("average_transaction", 0.0) or 0.0)
    date = result.get("date") or "today"
    if completed_services == 0 and total_revenue <= 0:
        return f"I don't see any completed services or recorded revenue for {date} yet."
    return (
        f"Revenue for {date} is ${total_revenue:.2f} across {completed_services} completed service"
        f"{'s' if completed_services != 1 else ''}"
        f" and {total_customers} customer visit{'s' if total_customers != 1 else ''}. "
        f"Average transaction is ${average_transaction:.2f}."
    )


def _format_top_services(result: Dict[str, Any]) -> str:
    if result.get("error"):
        return f"I couldn't pull top services: {result['error']}"

    services = list(result.get("services") or [])
    window = str(result.get("window_display") or result.get("window") or "the selected period")
    if not services:
        return f"I couldn't find completed services to rank for {window}."

    lines = []
    for service in services[:8]:
        name = service.get("name") or service.get("service_name") or "Unknown service"
        count = int(service.get("completed_services", service.get("customer_count", 0)) or 0)
        revenue = float(service.get("revenue", service.get("cost", 0.0)) or 0.0)
        if "revenue" in service or "completed_services" in service or "customer_count" in service:
            lines.append(f"- {name}: ${revenue:.2f} from {count} completed service{'s' if count != 1 else ''}")
        else:
            lines.append(f"- {name}: ${revenue:.2f}")
    return f"Top services for {window}:\n" + "\n".join(lines)


def _direct_service_customer_counts_response(shop_id: int, message: str) -> Dict[str, Any]:
    result = finance_tools._local_service_customer_counts(shop_id, query=message, limit=20)
    return {
        "response": _format_service_customer_counts(result),
        "agent": "finance",
        "approval_required": False,
        "pending_action": None,
        "metadata": {
            "shop_id": shop_id,
            "direct_fastpath": "service_customer_counts",
            "tool_results": result,
        },
    }


def _direct_today_revenue_response(shop_id: int) -> Dict[str, Any]:
    result = finance_tools._local_daily_revenue(shop_id, None)
    return {
        "response": _format_daily_revenue(result),
        "agent": "finance",
        "approval_required": False,
        "pending_action": None,
        "metadata": {
            "shop_id": shop_id,
            "direct_fastpath": "daily_revenue",
            "tool_results": result,
        },
    }


def _direct_top_services_response(shop_id: int, limit: int = 5) -> Dict[str, Any]:
    result = finance_tools._local_top_services(shop_id, limit=limit)
    return {
        "response": _format_top_services(result),
        "agent": "finance",
        "approval_required": False,
        "pending_action": None,
        "metadata": {
            "shop_id": shop_id,
            "direct_fastpath": "top_services",
            "tool_results": result,
        },
    }


async def _invoke_supervisor_sync(initial_state: AgentState, checkpoint_config: Any) -> Dict[str, Any]:
    runnable = _SUPERVISOR_RUNNABLE
    routed_agent: Optional[str] = None
    final_response_text = ""
    final_tool_results: Dict[str, Any] = {}
    pending_action: Optional[Dict[str, Any]] = None

    def _consume_updates() -> None:
        nonlocal routed_agent, final_response_text, final_tool_results

        try:
            update_iter = runnable.stream(
                initial_state,
                config=checkpoint_config,
                stream_mode="updates",
            )

            for update in update_iter:
                if not isinstance(update, dict):
                    continue

                for raw_node_name, out in update.items():
                    lg_node = _resolve_thinking_node({"name": raw_node_name})

                    ca = _extract_current_agent_from_output(out)
                    if ca and ca not in ("supervisor", "general", "", None):
                        routed_agent = ca

                    if lg_node == "synthesize_response" and isinstance(out, dict):
                        msgs = out.get("messages") or []
                        if msgs:
                            final_response_text = getattr(msgs[-1], "content", "") or ""

                    if isinstance(out, dict) and isinstance(out.get("tool_results"), dict):
                        final_tool_results = out.get("tool_results") or final_tool_results

        except Exception as stream_exc:
            exc_name = type(stream_exc).__name__
            if "interrupt" not in exc_name.lower():
                raise

    await asyncio.wait_for(
        asyncio.to_thread(_consume_updates),
        timeout=_sync_chat_timeout_seconds(),
    )

    snapshot = await asyncio.to_thread(runnable.get_state, checkpoint_config)
    if snapshot and snapshot.values:
        state_vals = dict(snapshot.values)
        if not final_response_text:
            final_response_text = _state_last_text(state_vals)
        if isinstance(state_vals.get("tool_results"), dict):
            final_tool_results = state_vals.get("tool_results") or final_tool_results
        if snapshot.next:
            pending_action = _extract_pending_action(
                {
                    **state_vals,
                    "__interrupt__": snapshot.interrupts,
                }
            )

    return {
        "messages": [AIMessage(content=final_response_text)] if final_response_text else [],
        "current_agent": routed_agent or "supervisor",
        "tool_results": final_tool_results,
        "pending_action": pending_action,
        "needs_human_input": pending_action is not None,
    }


_DOCUMENT_REFERENCE_TERMS = (
    "attachment",
    "csv",
    "document",
    "file",
    "json",
    "markdown",
    "spreadsheet",
    "text file",
    "upload",
    "uploaded",
)


def _query_mentions_document(query_text: str) -> bool:
    lowered = str(query_text or "").lower()
    return any(term in lowered for term in _DOCUMENT_REFERENCE_TERMS)


def _select_document_reference_memories(
    shop_id: int,
    user_id: int,
    query_text: str,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    """Resolve referential document prompts to the most relevant uploaded document chunks."""
    document_memories = db_interface.get_agent_memories(
        shop_id=shop_id,
        memory_type="document",
        user_id=user_id,
        limit=24,
    )
    if not document_memories:
        return []

    lowered_query = str(query_text or "").lower()
    target_document_id: Optional[int] = None

    for memory in document_memories:
        memory_meta = memory.get("memory_meta") if isinstance(memory.get("memory_meta"), dict) else {}
        document_id = memory_meta.get("document_id")
        source_candidates = [
            str(memory.get("source") or "").lower(),
            str(memory_meta.get("filename") or "").lower(),
            str(memory_meta.get("relative_path") or "").lower(),
        ]
        if any(candidate and candidate in lowered_query for candidate in source_candidates):
            if isinstance(document_id, int):
                target_document_id = document_id
                break

    if target_document_id is None:
        first_meta = document_memories[0].get("memory_meta")
        if isinstance(first_meta, dict) and isinstance(first_meta.get("document_id"), int):
            target_document_id = first_meta.get("document_id")

    if target_document_id is None:
        return document_memories[:limit]

    selected = [
        memory
        for memory in document_memories
        if isinstance(memory.get("memory_meta"), dict)
        and memory["memory_meta"].get("document_id") == target_document_id
    ]
    selected.sort(
        key=lambda memory: (
            int(memory.get("memory_meta", {}).get("chunk_index") or 0),
            str(memory.get("created_at") or ""),
        )
    )
    return selected[:limit]


def _reset_checkpoint_thread_if_idle(shop_id: int, user_id: int) -> None:
    if not hasattr(_SUPERVISOR_RUNNABLE, "get_state"):
        return

    checkpoint_config = build_checkpoint_config(shop_id, user_id)
    snapshot = _SUPERVISOR_RUNNABLE.get_state(checkpoint_config)
    if snapshot and snapshot.interrupts:
        return

    thread_id = _checkpoint_thread_id(shop_id, user_id)
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM checkpoint_writes WHERE thread_id = :thread_id"), {"thread_id": thread_id})
        db.execute(text("DELETE FROM checkpoints WHERE thread_id = :thread_id"), {"thread_id": thread_id})
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Unable to clear idle checkpoint thread %s: %s", thread_id, exc)
    finally:
        db.close()


# Agent-specific follow-up suggestion pools
_FOLLOWUP_POOLS: Dict[Optional[str], list] = {
    "receptionist": [
        "How many people are waiting right now?",
        "Close the queue for today",
        "What's the average wait time?",
        "Show today's queue summary",
        "Who was served last?",
    ],
    "finance": [
        "Show this week's revenue trend",
        "What was yesterday's revenue?",
        "Which services earn the most?",
        "Export this month's report as CSV",
        "Compare this week vs last week",
    ],
    "hr": [
        "Who is on shift right now?",
        "Show tomorrow's schedule",
        "Add a new employee",
        "How many hours did the team work this week?",
        "Are there any open shifts?",
    ],
    "crm": [
        "Show my open leads",
        "How many new contacts this week?",
        "Show the sales pipeline summary",
        "Which deals are in the negotiation stage?",
        "Create a new lead",
    ],
    None: [
        "Give me today's queue summary",
        "Show this week's revenue trend",
        "Who is on shift now?",
        "What can you help me with?",
    ],
}


def _iter_text_sse(text: str):
    """Yield SSE ``data:`` lines for *text* split word-by-word.

    Sends one event per word rather than one per character, reducing SSE
    event count ~10x while preserving the frontend typewriter effect
    (each chunk is appended to the in-progress message content).
    """
    if not text:
        return
    words = text.split(" ")
    last = len(words) - 1
    for i, word in enumerate(words):
        chunk = word + (" " if i < last else "")
        if chunk:
            yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"


def _generate_followup_suggestions(
    routed_agent: Optional[str],
    user_message: str,
    max_count: int = 3,
) -> list:
    """Return a small list of contextual follow-up questions."""
    import random

    pool = _FOLLOWUP_POOLS.get(routed_agent, _FOLLOWUP_POOLS[None])
    user_lower = user_message.lower()
    # Filter out prompts that are too similar to what the user just asked
    filtered = [s for s in pool if s.lower()[:20] not in user_lower]
    if not filtered:
        filtered = pool
    return random.sample(filtered, min(max_count, len(filtered)))


def _resolve_thinking_node(event: Any) -> Optional[str]:
    """Resolve LangGraph node name across event formats and normalize variants."""
    metadata = event.get("metadata") or {}
    raw_name = metadata.get("langgraph_node") or event.get("name") or ""
    if not raw_name:
        return None

    # Some runtimes include prefixes/suffixes in node names.
    # Normalize to the canonical node key expected by the UI.
    candidates = [
        raw_name,
        str(raw_name).split(".")[-1],
        str(raw_name).split(":")[-1],
        str(raw_name).split("/")[-1],
    ]
    for candidate in candidates:
        if candidate in _THINKING_NODES:
            return candidate
    return None


# PostgreSQL checkpoint persistence is mandatory.
try:
    _CHECKPOINTER_CM = get_sync_checkpoint_saver()
    _CHECKPOINTER = _CHECKPOINTER_CM.__enter__()
    if hasattr(_CHECKPOINTER, "setup"):
        _CHECKPOINTER.setup()
    _SUPERVISOR_RUNNABLE = create_supervisor_runnable(checkpointer=_CHECKPOINTER)
except Exception as e:
    raise RuntimeError(
        "PostgreSQL checkpoint initialization failed for agent_v2. "
        "Fix DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD and ensure psycopg[binary] is installed."
    ) from e
logger.info("agent_v2 using PostgreSQL checkpointer")


def _extract_pending_action(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    pending = result.get("pending_approval")
    interrupts = result.get("__interrupt__") or []
    if not pending:
        return None

    action_id = None
    if interrupts:
        action_id = getattr(interrupts[0], "id", None)

    return {
        **pending,
        "action_id": action_id,
    }


def _serialize_checkpoint_messages(state_values: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Serialize checkpoint messages for the owner-facing history endpoint."""
    serialized: list[Dict[str, Any]] = []
    for message in state_values.get("messages") or []:
        msg_type = getattr(message, "type", None)
        if msg_type == "system":
            continue
        role = "assistant"
        if msg_type == "human":
            role = "user"
        elif msg_type == "ai":
            role = "assistant"
        content = str(getattr(message, "content", ""))
        if not content.strip():
            continue
        # Use the message's additional_kwargs timestamp if present; else omit
        additional = getattr(message, "additional_kwargs", {}) or {}
        timestamp = additional.get("timestamp") or None
        payload = {
            "role": role,
            "content": content,
        }
        if timestamp is not None:
            payload["timestamp"] = timestamp
        serialized.append(payload)
    return serialized


def _notification_feed_type(notification_type: str, severity: str, title: str, message: str) -> str:
    # Direct notification_type mapping takes priority — prevents haystack
    # heuristics from misclassifying briefings that mention "approval", etc.
    _ntype = notification_type.lower()
    if _ntype.endswith("_briefing") or _ntype in (
        "morning_briefing", "evening_briefing", "midday_briefing",
        "finance_summary_ready", "commitment_due", "commitment_resolved",
        "shop_open", "shop_close", "pre_close_awareness",
        "remittance_due", "employee_hired", "custom_schedule_fired",
    ):
        return "system"
    if _ntype in (
        "payroll_approval_required", "tip_split_approval_required",
        "capacity_borderline_approval", "policy_action_executed",
    ):
        return "approval_decision"
    if _ntype in ("capacity_overload_lock", "queue_alert"):
        return "queue_update"
    # Haystack fallback for unknown notification types
    haystack = " ".join([notification_type, severity, title, message]).lower()
    if "error" in haystack:
        return "error"
    if "approval" in haystack or "policy" in haystack:
        return "approval_decision"
    if "queue" in haystack:
        return "queue_update"
    return "system"


def _serialize_notification_feed_event(notification: Any) -> Dict[str, Any]:
    payload = dict(getattr(notification, "payload", None) or {})
    notification_type = str(getattr(notification, "notification_type", "system") or "system")
    severity = str(getattr(notification, "severity", "info") or "info")
    created_at = getattr(notification, "created_at", None)
    _status = getattr(notification, "status", "unread")
    # Use .value so that str-enum instances (NotificationStatus.UNREAD) emit
    # "unread" rather than the Python 3.11+ repr "NotificationStatus.UNREAD".
    status_str = _status.value if hasattr(_status, "value") else str(_status)
    return {
        "id": f"notification_{getattr(notification, 'id', 'unknown')}",
        "type": _notification_feed_type(
            notification_type,
            severity,
            str(getattr(notification, "title", "")),
            str(getattr(notification, "message", "")),
        ),
        "title": str(getattr(notification, "title", "Agent notification")),
        "description": str(getattr(notification, "message", "")),
        "timestamp": created_at.isoformat() if created_at is not None else datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "severity": severity,
        "status": status_str,
        "notification_type": notification_type,
        "notification_id": getattr(notification, "id", None),
        "payload": payload,
    }


def _get_notification_feed_payload(shop_id: int, limit: int = 25) -> list[Dict[str, Any]]:
    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        notifications = repo.list_recent_notifications(shop_id, limit=limit)
        return [_serialize_notification_feed_event(item) for item in notifications]
    except Exception as exc:
        logger.warning("Unable to load persisted agent notifications for shop %s: %s", shop_id, exc)
        return []
    finally:
        db.close()


def _normalize_shop_ids(raw_ids: Any) -> list[int]:
    if not isinstance(raw_ids, list):
        return []
    normalized: list[int] = []
    for value in raw_ids:
        try:
            normalized.append(int(value))
        except (TypeError, ValueError):
            continue
    return normalized


def _extract_user_id(current_user: Dict[str, Any]) -> Optional[int]:
    raw_user_id = current_user.get("user_id")
    if raw_user_id is None:
        raw_user_id = current_user.get("id")
    try:
        return int(raw_user_id) if raw_user_id is not None else None
    except (TypeError, ValueError):
        return None


def _get_owned_shop_ids(current_user: Dict[str, Any]) -> list[int]:
    # Preferred source: auth payload shops list (if present and valid).
    from database import SessionLocal
    from modules.shops.models import Shop

    token_shops = _normalize_shop_ids(current_user.get("shops", []))
    if token_shops:
        return token_shops

    user_id = _extract_user_id(current_user)
    if user_id is None:
        return []

    db = SessionLocal()
    try:
        rows = db.query(Shop.id).filter(Shop.owner_id == user_id).all()
        return [int(row[0]) for row in rows]
    finally:
        db.close()


def _require_owner_shop_access(shop_id: Any, current_user: Dict[str, Any]) -> tuple[int, int]:
    user_id = _extract_user_id(current_user)
    user_shops = _get_owned_shop_ids(current_user)

    if user_id is None:
        raise HTTPException(status_code=401, detail="Authenticated user_id missing")

    try:
        normalized_shop_id = int(shop_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="shop_id must be an integer")

    if normalized_shop_id not in user_shops:
        raise HTTPException(status_code=403, detail="Not owner of this shop")

    return int(user_id), normalized_shop_id


def _list_policy_payload(shop_id: int) -> list[Dict[str, Any]]:
    return approval_policy.list_shop_policies(shop_id)


def _upsert_policy_payload(
    *,
    shop_id: int,
    policy_key: str,
    mode: str,
    policy_value: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    definition = approval_policy.get_policy_definition(policy_key)
    if definition is None:
        raise HTTPException(status_code=404, detail="Unknown policy_key")

    normalized_mode = str(mode or "").strip().lower()
    supported_modes = set(approval_policy.SUPPORTED_POLICY_MODES)
    if normalized_mode not in supported_modes:
        raise HTTPException(
            status_code=400,
            detail=f"mode must be one of: {', '.join(sorted(supported_modes))}",
        )

    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        repo.upsert_shop_policy(
            shop_id=shop_id,
            policy_key=policy_key,
            category=str(definition["category"]),
            mode=PolicyMode(normalized_mode),
            enabled=True,
            policy_value=policy_value,
            config=config,
        )
    finally:
        db.close()

    for item in _list_policy_payload(shop_id):
        if item["policy_key"] == policy_key:
            return item
    raise HTTPException(status_code=500, detail="Failed to load updated policy")


def _build_memory_context(shop_id: int, user_id: int, query_text: str) -> str:
    """Best-effort retrieval of tenant-scoped memory context for supervisor input."""
    try:
        relevant = db_interface.search_agent_memories(
            shop_id=shop_id,
            query_text=query_text,
            user_id=user_id,
            limit=6,
        )
        recent = db_interface.get_agent_memories(
            shop_id=shop_id,
            user_id=user_id,
            limit=8,
        )
        selected = merge_and_rank_memories(relevant, recent, max_items=8)

        if _query_mentions_document(query_text):
            document_memories = _select_document_reference_memories(shop_id, user_id, query_text)
            if document_memories:
                selected = merge_and_rank_memories(document_memories, selected, max_items=8)

        # Touch selected memories for recency tracking.
        for memory in selected:
            memory_id = memory.get("id")
            if isinstance(memory_id, int):
                db_interface.touch_agent_memory(memory_id)

        return format_memory_context(selected)
    except Exception as e:
        logger.warning("Agent memory retrieval failed (non-fatal): %s", str(e))
        return ""


@router.get("/documents")
async def list_owner_documents(
    shop_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id, normalized_shop_id = _require_owner_shop_access(shop_id, current_user)

    db = SessionLocal()
    try:
        documents = (
            db.query(AgentDocument)
            .filter(AgentDocument.shop_id == normalized_shop_id)
            .order_by(AgentDocument.updated_at.desc(), AgentDocument.id.desc())
            .all()
        )
        return {
            "shop_id": normalized_shop_id,
            "user_id": user_id,
            "documents": [_serialize_owner_document(document) for document in documents],
        }
    finally:
        db.close()


@router.delete("/documents/{document_id}")
async def delete_owner_document(
    document_id: int,
    shop_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id, normalized_shop_id = _require_owner_shop_access(shop_id, current_user)

    db = SessionLocal()
    try:
        document = _get_owner_document_or_404(db, shop_id=normalized_shop_id, document_id=document_id)
        deleted_chunks = _document_memory_query(db, shop_id=normalized_shop_id, document_id=document.id).delete(
            synchronize_session=False
        )
        filename = document.relative_path or document.filename
        db.delete(document)
        db.commit()
        return {
            "shop_id": normalized_shop_id,
            "user_id": user_id,
            "document_id": document_id,
            "deleted_memory_chunks": deleted_chunks,
            "message": f"Removed '{filename}' from secure storage and the knowledge base.",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Owner document delete failed")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {exc}")
    finally:
        db.close()


@router.post("/documents/{document_id}/reindex")
async def reindex_owner_document(
    document_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    user_id, normalized_shop_id = _require_owner_shop_access(body.get("shop_id"), current_user)

    db = SessionLocal()
    try:
        document = _get_owner_document_or_404(db, shop_id=normalized_shop_id, document_id=document_id)
        indexed_chunks = _reindex_owner_document_in_session(
            db,
            document=document,
            shop_id=normalized_shop_id,
        )
        db.commit()
        db.refresh(document)
        return {
            "shop_id": normalized_shop_id,
            "user_id": user_id,
            "indexed_chunks": indexed_chunks,
            "document": _serialize_owner_document(document),
            "message": f"Re-indexed '{document.relative_path or document.filename}' into {indexed_chunks} knowledge chunk(s).",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Owner document re-index failed")
        raise HTTPException(status_code=500, detail=f"Failed to re-index document: {exc}")
    finally:
        db.close()


@router.post("/documents/upload")
async def upload_owner_documents(
    shop_id: int = Form(...),
    files: List[UploadFile] = File(...),
    relative_paths: Optional[List[str]] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    user_id, normalized_shop_id = _require_owner_shop_access(shop_id, current_user)

    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    if len(files) > _OWNER_DOCUMENT_MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"You can upload up to {_OWNER_DOCUMENT_MAX_FILES} files at once",
        )
    if relative_paths and len(relative_paths) != len(files):
        raise HTTPException(status_code=400, detail="relative_paths must match the files array")

    db = SessionLocal()
    uploaded_documents: List[Dict[str, Any]] = []
    total_chunks_created = 0
    duplicate_count = 0

    try:
        for index, upload in enumerate(files):
            safe_name = _sanitize_document_name(upload.filename)
            safe_relative_path = _sanitize_relative_document_path(
                relative_paths[index] if relative_paths else upload.filename,
                safe_name,
            )
            file_bytes = await upload.read()
            if len(file_bytes) > _OWNER_DOCUMENT_MAX_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail=f"{safe_name}: exceeds the {_OWNER_DOCUMENT_MAX_BYTES // (1024 * 1024)} MB limit",
                )

            extracted_text = _extract_owner_document_text(
                file_bytes,
                filename=safe_name,
                content_type=upload.content_type or "text/plain",
            )
            checksum = hashlib.sha256(file_bytes).hexdigest()

            existing = (
                db.query(AgentDocument)
                .filter(
                    AgentDocument.shop_id == normalized_shop_id,
                    AgentDocument.checksum == checksum,
                )
                .first()
            )
            if existing:
                duplicate_count += 1
                uploaded_documents.append(_serialize_owner_document(existing, duplicate=True))
                continue

            chunks = _chunk_owner_document_text(extracted_text)
            document = AgentDocument(
                shop_id=normalized_shop_id,
                uploaded_by_user_id=user_id,
                filename=safe_name,
                relative_path=safe_relative_path,
                content_type=(upload.content_type or "text/plain"),
                size_bytes=len(file_bytes),
                checksum=checksum,
                file_blob=file_bytes,
                extracted_text=extracted_text,
                knowledge_status="indexed",
                chunk_count=len(chunks),
            )
            db.add(document)
            db.flush()

            for chunk_index, chunk in enumerate(chunks, start=1):
                db.add(
                    AgentMemory(
                        shop_id=normalized_shop_id,
                        user_id=None,
                        memory_type="document",
                        content=f"From {safe_relative_path} (chunk {chunk_index}/{len(chunks)}): {chunk}",
                        source=safe_relative_path,
                        importance_score=0.82,
                        memory_meta={
                            "document_id": document.id,
                            "filename": safe_name,
                            "relative_path": safe_relative_path,
                            "chunk_index": chunk_index,
                            "chunk_count": len(chunks),
                            "checksum": checksum,
                        },
                        is_active=True,
                        created_at=datetime.utcnow(),
                    )
                )

            uploaded_documents.append(
                _serialize_owner_document(document)
            )
            total_chunks_created += len(chunks)

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Owner document upload failed")
        raise HTTPException(status_code=500, detail=f"Failed to ingest uploaded documents: {exc}")
    finally:
        db.close()

    return {
        "shop_id": normalized_shop_id,
        "user_id": user_id,
        "documents": uploaded_documents,
        "ingested_chunks": total_chunks_created,
        "duplicate_documents": duplicate_count,
        "message": (
            f"Stored {len(uploaded_documents) - duplicate_count} new document(s) securely, skipped {duplicate_count} duplicate(s), and indexed {total_chunks_created} knowledge chunk(s)."
        ),
    }


# ============================================================================
# Policy Management
# ============================================================================


@router.get("/policies")
async def list_policies(
    shop_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id, normalized_shop_id = _require_owner_shop_access(shop_id, current_user)
    return {
        "shop_id": normalized_shop_id,
        "user_id": user_id,
        "policies": _list_policy_payload(normalized_shop_id),
    }


@router.put("/policies/{policy_key}")
async def update_policy(
    policy_key: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    user_id, shop_id = _require_owner_shop_access(body.get("shop_id"), current_user)
    policy = _upsert_policy_payload(
        shop_id=shop_id,
        policy_key=policy_key,
        mode=body.get("mode"),
        policy_value=body.get("policy_value"),
        config=body.get("config") if isinstance(body.get("config"), dict) else None,
    )
    return {
        "shop_id": shop_id,
        "user_id": user_id,
        "policy": policy,
    }


# ============================================================================
# Chat Endorsement - Synchronous
# ============================================================================

@router.post("/chat")
async def chat_sync(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Synchronous chat endpoint.
    
    Request body:
    {
        "message": "How many people are in the queue?",
        "shop_id": 123,  # Optional; auto-detect from user's shops if omitted
        "session_id": "optional-session-id"
    }
    
    Response:
    {
        "response": "There are currently X people in the queue...",
        "agent": "receptionist",  # Which sub-agent handled it
        "approval_required": false,
        "metadata": {...}
    }
    """
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not _redis.check_rate_limit(client_ip, limit=20, window=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")
    
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    message = body.get("message", "")
    shop_id = body.get("shop_id")
    attachments = body.get("attachments", []) or []
    
    if not message:
        raise HTTPException(status_code=400, detail="message field required")
    
    # Augment message with any attached file content
    human_message_content = message
    for att in attachments:
        filename = str(att.get("filename", "attachment"))
        text_content = str(att.get("text_content", "")).strip()
        if text_content:
            human_message_content = f"{human_message_content}\n\n[Attached file: {filename}]\n{text_content}"
    
    # Get user's shops and validate ownership
    user_id = _extract_user_id(current_user)
    user_shops = _get_owned_shop_ids(current_user)  # List of shop IDs user owns
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authenticated user_id missing")
    
    if not shop_id:
        # Use first shop if only one
        if len(user_shops) == 1:
            shop_id = user_shops[0]
        else:
            raise HTTPException(
                status_code=400,
                detail="shop_id required or user must own exactly one shop"
            )
    
    try:
        shop_id = int(shop_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="shop_id must be an integer")

    if shop_id not in user_shops:
        raise HTTPException(status_code=403, detail="Not owner of this shop")

    logger.info("chat/sync start shop_id=%s user_id=%s msg_len=%d", shop_id, user_id, len(message))

    _reset_checkpoint_thread_if_idle(shop_id, int(user_id))

    existing_pending = _get_current_pending_approval(shop_id, int(user_id), runnable=_SUPERVISOR_RUNNABLE)
    followup_operation = None if existing_pending else _load_direct_finance_followup_operation(shop_id, int(user_id), message)
    if followup_operation == "service_customer_counts":
        response = _direct_service_customer_counts_response(shop_id, message)
        _remember_direct_finance_context(shop_id, int(user_id), "service_customer_counts", message)
        _persist_chat_turn_memory(
            shop_id=shop_id,
            user_id=int(user_id),
            user_message=message,
            assistant_response=str(response.get("response") or ""),
            route="/api/v2/agent/chat",
        )
        return response
    if followup_operation == "top_services":
        response = _direct_top_services_response(shop_id)
        _remember_direct_finance_context(shop_id, int(user_id), "top_services", message)
        _persist_chat_turn_memory(
            shop_id=shop_id,
            user_id=int(user_id),
            user_message=message,
            assistant_response=str(response.get("response") or ""),
            route="/api/v2/agent/chat",
        )
        return response

    if existing_pending is None and _is_service_customer_count_question(message):
        response = _direct_service_customer_counts_response(shop_id, message)
        _remember_direct_finance_context(shop_id, int(user_id), "service_customer_counts", message)
        _persist_chat_turn_memory(
            shop_id=shop_id,
            user_id=int(user_id),
            user_message=message,
            assistant_response=str(response.get("response") or ""),
            route="/api/v2/agent/chat",
        )
        return response
    if existing_pending is None and _is_today_revenue_question(message):
        response = _direct_today_revenue_response(shop_id)
        _remember_direct_finance_context(shop_id, int(user_id), "daily_revenue", message)
        _persist_chat_turn_memory(
            shop_id=shop_id,
            user_id=int(user_id),
            user_message=message,
            assistant_response=str(response.get("response") or ""),
            route="/api/v2/agent/chat",
        )
        return response
    if existing_pending is None and _is_top_services_question(message):
        response = _direct_top_services_response(shop_id)
        _remember_direct_finance_context(shop_id, int(user_id), "top_services", message)
        _persist_chat_turn_memory(
            shop_id=shop_id,
            user_id=int(user_id),
            user_message=message,
            assistant_response=str(response.get("response") or ""),
            route="/api/v2/agent/chat",
        )
        return response

    # Build checkpoint config for this tenant
    checkpoint_config = build_checkpoint_config(shop_id, user_id)
    work_context = _create_chat_work_context(shop_id, int(user_id), message)

    # Create initial state
    memory_context = _build_memory_context(shop_id, int(user_id), message)
    input_messages = []
    if memory_context:
        input_messages.append(SystemMessage(content=memory_context))
    input_messages.append(HumanMessage(content=human_message_content))

    initial_state: AgentState = {
        "messages": input_messages,
        "tenant_id": shop_id,
        "user_id": int(user_id),
        "current_agent": "supervisor",
        "active_goal_id": work_context["goal_id"],
        "active_task_id": None,
        "execution_mode": work_context["execution_mode"],
        "autonomy_policy": None,
        "event_context": work_context["event_context"],
        "proposed_actions": [],
        "run_summary": {"run_id": work_context["run_id"], "status": "running"},
        "pending_approval": None,
        "needs_human_input": False,
        "tool_results": None,
        "metadata": {"shop_id": shop_id, "user_id": user_id, "goal_id": work_context["goal_id"], "run_id": work_context["run_id"]}
    }
    
    # Run supervisor graph
    try:
        result = await _invoke_supervisor_sync(initial_state, checkpoint_config)
        pending_action = cast(Optional[Dict[str, Any]], result.get("pending_action"))
        if pending_action:
            pending_action["shop_id"] = shop_id
            pending_action = enrich_pending_approval_payload(
                pending_action,
                metrics=db_interface.get_shop_live_wait_metrics(shop_id) or {},
            )
        approval_required = bool((result.get("__interrupt__") or []) or result.get("needs_human_input", False))
        
        # Extract final response
        messages = result.get("messages", [])
        if messages:
            final_message = messages[-1]
            response_text = getattr(final_message, "content", str(final_message))
        else:
            response_text = "No response"

        pending_action = _finalize_chat_work_context(
            shop_id=shop_id,
            user_id=int(user_id),
            goal_id=work_context["goal_id"],
            run_id=work_context["run_id"],
            routed_agent=result.get("current_agent", "supervisor"),
            response_text=response_text,
            tool_results=cast(Optional[Dict[str, Any]], result.get("tool_results")),
            approval_required=approval_required,
            pending_action=pending_action,
            conversation_messages=messages,
        )

        _persist_chat_turn_memory(
            shop_id=shop_id,
            user_id=int(user_id),
            user_message=message,
            assistant_response=response_text,
            route="/api/v2/agent/chat",
        )

        logger.info(
            "chat/sync done shop_id=%s user_id=%s agent=%s text_len=%d approval=%s",
            shop_id, user_id, result.get("current_agent", "supervisor"),
            len(response_text), approval_required,
        )
        return {
            "response": response_text,
            "agent": result.get("current_agent", "supervisor"),
            "approval_required": approval_required,
            "pending_action": pending_action,
            "metadata": {
                **(result.get("metadata", {}) or {}),
                "goal_id": work_context["goal_id"],
                "run_id": work_context["run_id"],
            }
        }

    except asyncio.TimeoutError:
        logger.warning(
            "Sync chat timed out for shop_id=%s user_id=%s after %.1fs",
            shop_id,
            user_id,
            _sync_chat_timeout_seconds(),
        )
        raise HTTPException(
            status_code=504,
            detail="Sync agent request timed out. Use /api/v2/agent/chat/stream for long-running requests.",
        )
    
    except Exception as e:
        logger.error(f"Supervisor graph error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


# ============================================================================
# Chat Streaming - SSE
# ============================================================================

@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Streaming chat endpoint (Server-Sent Events).
    
    Returns SSE stream with events:
    - {type: 'text', content: '...'} - streaming text tokens
    - {type: 'agent_switch', agent: 'finance'} - sub-agent delegation
    - {type: 'tool_call', tool: 'daily_revenue', args: {...}}
    - {type: 'tool_result', tool: '...', result: {...}}
    - {type: 'approval_required', action: '...', details: {...}} - HITL breakpoint
    - {type: 'actions', actions: [...]} - quick-action buttons
    - {type: 'sentence', text: '...', audio: 'base64...'} - paired TTS
    - {type: 'stream_status', status: 'completed'|'error', ...} - terminal stream telemetry
    - [DONE] - stream complete
    
    Request body same as /chat endpoint.
    """
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not _redis.check_rate_limit(client_ip, limit=20, window=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")
    
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    message = body.get("message", "")
    shop_id = body.get("shop_id")
    is_voice = body.get("is_voice", False)
    attachments = body.get("attachments", []) or []
    
    if not message:
        raise HTTPException(status_code=400, detail="message field required")
    
    # Augment message with any attached file content
    human_message_content = message
    for att in attachments:
        filename = str(att.get("filename", "attachment"))
        text_content = str(att.get("text_content", "")).strip()
        if text_content:
            human_message_content = f"{human_message_content}\n\n[Attached file: {filename}]\n{text_content}"
    
    # Validate ownership
    user_id = _extract_user_id(current_user)
    user_shops = _get_owned_shop_ids(current_user)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authenticated user_id missing")
    
    if not shop_id:
        if len(user_shops) == 1:
            shop_id = user_shops[0]
        else:
            raise HTTPException(status_code=400, detail="shop_id required")
    
    try:
        shop_id = int(shop_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="shop_id must be an integer")

    if shop_id not in user_shops:
        raise HTTPException(status_code=403, detail="Not owner of this shop")

    _reset_checkpoint_thread_if_idle(shop_id, int(user_id))

    existing_pending = _get_current_pending_approval(shop_id, int(user_id), runnable=_SUPERVISOR_RUNNABLE)
    followup_operation = None if existing_pending else _load_direct_finance_followup_operation(shop_id, int(user_id), message)
    
    # Create streaming generator
    async def event_generator():
        _stream_t0 = time.monotonic()
        try:
            logger.info(
                "chat/stream start shop_id=%s user_id=%s msg_len=%d fast_path=%s",
                shop_id,
                user_id,
                len(message),
                followup_operation or ("direct" if existing_pending is None else "pending"),
            )
            if followup_operation == "service_customer_counts" or (existing_pending is None and _is_service_customer_count_question(message)):
                yield f"data: {json.dumps({'type': 'thinking_step', 'step': 'prepare', 'label': 'Reading completed visits by service…', 'status': 'active', 'agent': 'finance'})}\n\n"
                yield f"data: {json.dumps({'type': 'agent_switch', 'agent': 'finance'})}\n\n"
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'service_customer_counts', 'agent': 'finance', 'label': 'Counting customers by service'})}\n\n"
                result = await asyncio.to_thread(
                    finance_tools._local_service_customer_counts,
                    shop_id,
                    query=message,
                    limit=20,
                )
                response_text = _format_service_customer_counts(result)
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'service_customer_counts', 'result': result, 'agent': 'finance'})}\n\n"
                yield f"data: {json.dumps({'type': 'thinking_step', 'step': 'prepare', 'label': 'Service customer counts ready', 'status': 'done', 'agent': 'finance'})}\n\n"
                for _sse in _iter_text_sse(response_text):
                    yield _sse
                _remember_direct_finance_context(shop_id, int(user_id), "service_customer_counts", message)
                _persist_chat_turn_memory(
                    shop_id=shop_id,
                    user_id=int(user_id),
                    user_message=message,
                    assistant_response=response_text,
                    route="/api/v2/agent/chat/stream",
                )
                _fast_dur_ms = int((time.monotonic() - _stream_t0) * 1000)
                yield f"data: {json.dumps({'type': 'stream_status', 'status': 'completed', 'agent': 'finance', 'has_text': True, 'has_tool_results': True, 'approval_required': False, 'duration_ms': _fast_dur_ms})}\n\n"
                _fast_sugg = _generate_followup_suggestions('finance', message)
                if _fast_sugg:
                    yield f"data: {json.dumps({'type': 'suggestions', 'suggestions': _fast_sugg})}\n\n"
                yield "data: [DONE]\n\n"
                return

            if existing_pending is None and _is_today_revenue_question(message):
                yield f"data: {json.dumps({'type': 'thinking_step', 'step': 'prepare', 'label': 'Reading live revenue…', 'status': 'active', 'agent': 'finance'})}\n\n"
                yield f"data: {json.dumps({'type': 'agent_switch', 'agent': 'finance'})}\n\n"
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'daily_revenue', 'agent': 'finance', 'label': 'Reading today revenue'})}\n\n"
                result = await asyncio.to_thread(finance_tools._local_daily_revenue, shop_id, None)
                response_text = _format_daily_revenue(result)
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'daily_revenue', 'result': result, 'agent': 'finance'})}\n\n"
                yield f"data: {json.dumps({'type': 'thinking_step', 'step': 'prepare', 'label': 'Revenue ready', 'status': 'done', 'agent': 'finance'})}\n\n"
                for _sse in _iter_text_sse(response_text):
                    yield _sse
                _remember_direct_finance_context(shop_id, int(user_id), "daily_revenue", message)
                _persist_chat_turn_memory(
                    shop_id=shop_id,
                    user_id=int(user_id),
                    user_message=message,
                    assistant_response=response_text,
                    route="/api/v2/agent/chat/stream",
                )
                _fast_dur_ms = int((time.monotonic() - _stream_t0) * 1000)
                yield f"data: {json.dumps({'type': 'stream_status', 'status': 'completed', 'agent': 'finance', 'has_text': True, 'has_tool_results': True, 'approval_required': False, 'duration_ms': _fast_dur_ms})}\n\n"
                _fast_sugg = _generate_followup_suggestions('finance', message)
                if _fast_sugg:
                    yield f"data: {json.dumps({'type': 'suggestions', 'suggestions': _fast_sugg})}\n\n"
                yield "data: [DONE]\n\n"
                return

            if followup_operation == "top_services" or (existing_pending is None and _is_top_services_question(message)):
                yield f"data: {json.dumps({'type': 'thinking_step', 'step': 'prepare', 'label': 'Ranking live services…', 'status': 'active', 'agent': 'finance'})}\n\n"
                yield f"data: {json.dumps({'type': 'agent_switch', 'agent': 'finance'})}\n\n"
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'top_services', 'agent': 'finance', 'label': 'Ranking top services'})}\n\n"
                result = await asyncio.to_thread(finance_tools._local_top_services, shop_id, 5)
                response_text = _format_top_services(result)
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'top_services', 'result': result, 'agent': 'finance'})}\n\n"
                yield f"data: {json.dumps({'type': 'thinking_step', 'step': 'prepare', 'label': 'Top services ready', 'status': 'done', 'agent': 'finance'})}\n\n"
                for _sse in _iter_text_sse(response_text):
                    yield _sse
                _remember_direct_finance_context(shop_id, int(user_id), "top_services", message)
                _persist_chat_turn_memory(
                    shop_id=shop_id,
                    user_id=int(user_id),
                    user_message=message,
                    assistant_response=response_text,
                    route="/api/v2/agent/chat/stream",
                )
                _fast_dur_ms = int((time.monotonic() - _stream_t0) * 1000)
                yield f"data: {json.dumps({'type': 'stream_status', 'status': 'completed', 'agent': 'finance', 'has_text': True, 'has_tool_results': True, 'approval_required': False, 'duration_ms': _fast_dur_ms})}\n\n"
                _fast_sugg = _generate_followup_suggestions('finance', message)
                if _fast_sugg:
                    yield f"data: {json.dumps({'type': 'suggestions', 'suggestions': _fast_sugg})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Emit immediately so the user sees activity before any DB / LLM work starts.
            yield f"data: {json.dumps({'type': 'thinking_step', 'step': 'prepare', 'label': 'Analyzing your request…', 'status': 'active', 'agent': None})}\n\n"

            # Build checkpoint config
            checkpoint_config = build_checkpoint_config(shop_id, user_id)
            work_context = _create_chat_work_context(shop_id, int(user_id), message, is_voice=bool(is_voice))

            # Create initial state
            memory_context = _build_memory_context(shop_id, int(user_id), message)
            input_messages = []
            if memory_context:
                input_messages.append(SystemMessage(content=memory_context))
            input_messages.append(HumanMessage(content=human_message_content))

            initial_state: AgentState = {
                "messages": input_messages,
                "tenant_id": shop_id,
                "user_id": int(user_id),
                "current_agent": "supervisor",
                "active_goal_id": work_context["goal_id"],
                "active_task_id": None,
                "execution_mode": work_context["execution_mode"],
                "autonomy_policy": None,
                "event_context": work_context["event_context"],
                "proposed_actions": [],
                "run_summary": {"run_id": work_context["run_id"], "status": "running"},
                "pending_approval": None,
                "needs_human_input": False,
                "tool_results": None,
                "metadata": {"shop_id": shop_id, "user_id": user_id, "is_voice": is_voice, "goal_id": work_context["goal_id"], "run_id": work_context["run_id"]},
            }

            runnable = _SUPERVISOR_RUNNABLE
            routed_agent: Optional[str] = None
            final_response_text = ""
            final_tool_results: Dict[str, Any] = {}
            final_metadata: Dict[str, Any] = {}
            pending_action: Optional[Dict[str, Any]] = None

            # ----------------------------------------------------------------
            # Stream graph execution via producer thread + async consumer.
            # A keepalive SSE comment is emitted every _KEEPALIVE_INTERVAL
            # seconds so proxies/nginx don't close the connection during
            # slow LLM steps (qwen3:14b can take 60-120s per step).
            # ----------------------------------------------------------------
            _GRAPH_STEP_TIMEOUT = 150  # total seconds before we give up
            _KEEPALIVE_INTERVAL = 15   # SSE ": keepalive" cadence

            _graph_queue: asyncio.Queue = asyncio.Queue(maxsize=512)
            _GRAPH_DONE = object()
            _evt_loop = asyncio.get_event_loop()

            def _produce_graph_events() -> None:
                """Run sync LangGraph stream in a thread; push events to queue."""
                try:
                    for _upd in runnable.stream(
                        initial_state,
                        config=checkpoint_config,
                        stream_mode="updates",
                    ):
                        _evt_loop.call_soon_threadsafe(_graph_queue.put_nowait, _upd)
                except Exception as _exc:
                    _evt_loop.call_soon_threadsafe(_graph_queue.put_nowait, _exc)
                finally:
                    _evt_loop.call_soon_threadsafe(_graph_queue.put_nowait, _GRAPH_DONE)

            asyncio.ensure_future(asyncio.to_thread(_produce_graph_events))

            _graph_deadline = asyncio.get_event_loop().time() + _GRAPH_STEP_TIMEOUT

            try:
                while True:
                    _remaining = _graph_deadline - asyncio.get_event_loop().time()
                    if _remaining <= 0:
                        logger.warning(
                            "Graph timed out after %ds for shop=%s", _GRAPH_STEP_TIMEOUT, shop_id
                        )
                        break

                    try:
                        update = await asyncio.wait_for(
                            _graph_queue.get(),
                            timeout=min(_KEEPALIVE_INTERVAL, _remaining),
                        )
                    except asyncio.TimeoutError:
                        # No event yet — send a keepalive comment to prevent proxy timeout.
                        yield ": keepalive\n\n"
                        continue

                    if update is _GRAPH_DONE:
                        break
                    if isinstance(update, Exception):
                        _exc_name = type(update).__name__
                        if "interrupt" in _exc_name.lower() or "Interrupt" in _exc_name:
                            logger.info("Graph interrupted (approval gate): %s", _exc_name)
                        else:
                            raise update
                        break
                    if not isinstance(update, dict):
                        continue

                    for raw_node_name, out in update.items():
                        lg_node = _resolve_thinking_node({"name": raw_node_name})
                        if not lg_node:
                            continue

                        metadata_out = _extract_metadata_from_output(out)
                        if metadata_out:
                            final_metadata = dict(metadata_out)

                        # Emit active first for visual progression.
                        start_label = _thinking_label_active(lg_node, routed_agent)
                        yield f"data: {json.dumps({'type': 'thinking_step', 'step': lg_node, 'label': start_label, 'status': 'active', 'agent': routed_agent})}\n\n"

                        ca = _extract_current_agent_from_output(out)
                        if ca and ca not in ("supervisor", "general", "", None):
                            if ca != routed_agent:
                                yield f"data: {json.dumps({'type': 'agent_switch', 'agent': ca})}\n\n"
                            routed_agent = ca

                        if lg_node == "classify_intent":
                            reasoning_text = metadata_out.get("routing_reasoning")
                            if isinstance(reasoning_text, str) and reasoning_text.strip():
                                yield f"data: {json.dumps({'type': 'reasoning', 'step': lg_node, 'id': 'supervisor_route', 'text': reasoning_text.strip(), 'agent': routed_agent or 'supervisor'})}\n\n"

                        for reasoning_event in _normalize_reasoning_events(metadata_out.get("reasoning_events")):
                            yield f"data: {json.dumps({'type': 'reasoning', 'step': lg_node, 'id': reasoning_event.get('id') or f'{lg_node}_reasoning', 'text': str(reasoning_event.get('text')).strip(), 'agent': routed_agent or metadata_out.get('execution_target') or metadata_out.get('route', {}).get('to') or 'supervisor', 'tool': reasoning_event.get('tool')})}\n\n"

                        if lg_node == "execute_plan":
                            execution_target = metadata_out.get("execution_target") or routed_agent
                            specialist_operation = metadata_out.get("specialist_operation") or execution_target
                            if execution_target in {"receptionist", "finance", "hr", "crm"}:
                                yield f"data: {json.dumps({'type': 'tool_call', 'tool': specialist_operation, 'agent': execution_target, 'label': _thinking_label_active(lg_node, execution_target)})}\n\n"

                        # Capture final synthesized text when available.
                        if lg_node == "synthesize_response" and isinstance(out, dict):
                            msgs = out.get("messages") or []
                            if msgs:
                                final_response_text = getattr(msgs[-1], "content", "") or ""

                        if isinstance(out, dict) and isinstance(out.get("tool_results"), dict):
                            final_tool_results = out.get("tool_results") or final_tool_results

                        done_label = _thinking_label_done(lg_node, routed_agent)
                        yield f"data: {json.dumps({'type': 'thinking_step', 'step': lg_node, 'label': done_label, 'status': 'done', 'agent': routed_agent})}\n\n"

            except Exception as stream_exc:
                exc_name = type(stream_exc).__name__
                if "interrupt" in exc_name.lower() or "Interrupt" in exc_name:
                    logger.info("Graph interrupted (approval gate): %s", exc_name)
                    # Fall through — state retrieval below will surface the pending action.
                else:
                    raise

            # ----------------------------------------------------------------
            # If response text wasn't captured via astream_events (e.g. graph
            # intercepted for approval), retrieve it from the final checkpoint.
            # ----------------------------------------------------------------
            if not final_response_text:
                try:
                    snapshot = await asyncio.to_thread(runnable.get_state, checkpoint_config)
                    if snapshot and snapshot.values:
                        state_vals = dict(snapshot.values)
                        final_response_text = _state_last_text(state_vals)
                        if isinstance(state_vals.get("tool_results"), dict):
                            final_tool_results = state_vals.get("tool_results") or final_tool_results
                            if isinstance(state_vals.get("metadata"), dict):
                                final_metadata = dict(state_vals.get("metadata") or final_metadata)
                        if snapshot.next:
                            # Graph is paused at a breakpoint (approval required).
                            pending_action = _extract_pending_action(
                                {
                                    **state_vals,
                                    "__interrupt__": snapshot.interrupts,
                                }
                            )
                            if pending_action:
                                pending_action["shop_id"] = shop_id
                                pending_action = enrich_pending_approval_payload(
                                    pending_action,
                                    metrics=db_interface.get_shop_live_wait_metrics(shop_id) or {},
                                )
                except Exception as state_exc:
                    logger.warning("Could not retrieve final checkpoint state: %s", state_exc)

            approval_required = pending_action is not None
            # Best-effort grab of the final messages list for commitment scanning
            final_messages_for_scan = None
            try:
                snap = await asyncio.to_thread(runnable.get_state, checkpoint_config)
                if snap and snap.values and isinstance(snap.values.get("messages"), list):
                    final_messages_for_scan = list(snap.values.get("messages") or [])
            except Exception:
                final_messages_for_scan = None

            pending_action = _finalize_chat_work_context(
                shop_id=shop_id,
                user_id=int(user_id),
                goal_id=work_context["goal_id"],
                run_id=work_context["run_id"],
                routed_agent=routed_agent or "supervisor",
                response_text=final_response_text,
                tool_results=final_tool_results,
                approval_required=approval_required,
                pending_action=pending_action,
                conversation_messages=final_messages_for_scan,
            )

            if pending_action:
                yield f"data: {json.dumps({'type': 'approval_required', 'action': pending_action.get('action'), 'details': pending_action})}\n\n"
                # Notify owner via Telegram if connected
                try:
                    from modules.shops.models import Shop as _Shop
                    _db_tg = SessionLocal()
                    try:
                        _shop_tg = _db_tg.query(_Shop).filter(_Shop.id == shop_id).first()
                        if _shop_tg and _shop_tg.telegram_chat_id and _shop_tg.telegram_notifications_enabled:
                            import telegram_service as _tg
                            _action_id = pending_action.get("action_id") or pending_action.get("id") or ""
                            _action_label = pending_action.get("action") or "Action required"
                            _details = pending_action.get("description") or pending_action.get("details") or ""
                            _tg_text = await _tg.format_approval_notification(_action_label, str(_details)[:200], _action_id)
                            await _tg.send_message(_shop_tg.telegram_chat_id, _tg_text)
                    finally:
                        _db_tg.close()
                except Exception as _tg_err:
                    logger.warning("Telegram approval notification error: %s", _tg_err)

            _persist_chat_turn_memory(
                shop_id=shop_id,
                user_id=int(user_id),
                user_message=message,
                assistant_response=final_response_text,
                route="/api/v2/agent/chat/stream",
            )

            if isinstance(final_tool_results, dict) and final_tool_results:
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': final_metadata.get('specialist_operation') or final_tool_results.get('tool') or routed_agent or 'operation', 'result': final_tool_results, 'agent': routed_agent})}\n\n"

            # Stream response text word-by-word for efficient SSE delivery.
            for _sse in _iter_text_sse(final_response_text or ""):
                yield _sse

            # Emit structured chart/file payloads for frontend insights panel and inline attachments.
            if routed_agent == "finance" and isinstance(final_tool_results, dict):
                points = final_tool_results.get("points")
                services = final_tool_results.get("services")
                preferred_presentation = str(final_tool_results.get("preferred_presentation") or "").lower()
                if isinstance(points, list) and points:
                    chart_points = []
                    table_rows = []
                    for row in points[:60]:
                        try:
                            revenue = float(row.get("revenue", 0.0) or 0.0)
                            customers = int(row.get("customers", 0) or 0)
                            completed_services = int(row.get("completed_services", 0) or 0)
                            average_ticket = revenue / completed_services if completed_services else 0.0
                            chart_points.append(
                                {
                                    "label": str(row.get("period", "")),
                                    "revenue": revenue,
                                    "customers": customers,
                                }
                            )
                            table_rows.append(
                                {
                                    "period": str(row.get("period", "")),
                                    "revenue": revenue,
                                    "completedServices": completed_services,
                                    "customers": customers,
                                    "averageTicket": average_ticket,
                                }
                            )
                        except (TypeError, ValueError):
                            continue

                    if table_rows and preferred_presentation == "table":
                        table_event = {
                            "type": "table",
                            "title": f"Revenue by Day ({final_tool_results.get('window', 'custom').replace('_', ' ')})",
                            "rowIdKey": "period",
                            "columns": [
                                {"key": "period", "label": "Date", "priority": "primary"},
                                {
                                    "key": "revenue",
                                    "label": "Revenue",
                                    "align": "right",
                                    "priority": "primary",
                                    "format": {"kind": "currency", "currency": "USD", "decimals": 2},
                                },
                                {
                                    "key": "completedServices",
                                    "label": "Services",
                                    "align": "right",
                                    "priority": "secondary",
                                    "format": {"kind": "number", "decimals": 0},
                                },
                                {
                                    "key": "customers",
                                    "label": "Customers",
                                    "align": "right",
                                    "priority": "secondary",
                                    "format": {"kind": "number", "decimals": 0},
                                },
                                {
                                    "key": "averageTicket",
                                    "label": "Avg Ticket",
                                    "align": "right",
                                    "priority": "secondary",
                                    "format": {"kind": "currency", "currency": "USD", "decimals": 2},
                                },
                            ],
                            "data": table_rows,
                        }
                        yield f"data: {json.dumps(table_event)}\n\n"

                    if chart_points and preferred_presentation != "table":
                        chart_window = str(
                            final_tool_results.get("window_display")
                            or final_tool_results.get("window")
                            or "custom"
                        ).replace("_", " ")
                        chart_event = {
                            "type": "chart",
                            "title": f"Revenue Trend ({chart_window})",
                            "description": "Revenue and customers by period.",
                            "chartType": "line" if len(chart_points) > 2 else "bar",
                            "data": chart_points,
                            "xKey": "label",
                            "series": [
                                {"key": "revenue", "label": "Revenue"},
                                {"key": "customers", "label": "Customers"},
                            ],
                            "showLegend": True,
                            "showGrid": True,
                        }
                        yield f"data: {json.dumps(chart_event)}\n\n"

                if preferred_presentation == "table" and isinstance(services, list) and services:
                    service_rows = []
                    for index, service in enumerate(services[:60], start=1):
                        try:
                            service_rows.append(
                                {
                                    "rank": index,
                                    "name": str(service.get("name", "")),
                                    "price": float(service.get("cost", 0.0) or 0.0),
                                    "durationMinutes": int(service.get("duration_minutes", 0) or 0),
                                }
                            )
                        except (TypeError, ValueError):
                            continue

                    if service_rows:
                        table_event = {
                            "type": "table",
                            "title": "Services",
                            "rowIdKey": "rank",
                            "columns": [
                                {
                                    "key": "rank",
                                    "label": "#",
                                    "align": "right",
                                    "priority": "secondary",
                                    "format": {"kind": "number", "decimals": 0},
                                },
                                {"key": "name", "label": "Service", "priority": "primary"},
                                {
                                    "key": "price",
                                    "label": "Price",
                                    "align": "right",
                                    "priority": "primary",
                                    "format": {"kind": "currency", "currency": "USD", "decimals": 2},
                                },
                                {
                                    "key": "durationMinutes",
                                    "label": "Minutes",
                                    "align": "right",
                                    "priority": "secondary",
                                    "format": {"kind": "number", "decimals": 0},
                                },
                            ],
                            "data": service_rows,
                        }
                        yield f"data: {json.dumps(table_event)}\n\n"

                csv_content = final_tool_results.get("csv_content")
                if isinstance(csv_content, str) and csv_content.strip():
                    file_event = {
                        "type": "file",
                        "filename": final_tool_results.get("filename") or "finance_export.csv",
                        "mimeType": "text/csv",
                        "content": base64.b64encode(csv_content.encode("utf-8")).decode("ascii"),
                    }
                    yield f"data: {json.dumps(file_event)}\n\n"

            # Emit contextual follow-up suggestions based on the routed agent.
            follow_ups = _generate_followup_suggestions(routed_agent, message)
            if follow_ups:
                yield f"data: {json.dumps({'type': 'suggestions', 'suggestions': follow_ups})}\n\n"

            completion_event = {
                "type": "stream_status",
                "status": "completed",
                "agent": routed_agent or "supervisor",
                "has_text": bool(final_response_text),
                "has_tool_results": bool(final_tool_results),
                "approval_required": approval_required,
                "duration_ms": int((time.monotonic() - _stream_t0) * 1000),
            }
            yield f"data: {json.dumps(completion_event)}\n\n"
            logger.info(
                "chat/stream done shop_id=%s user_id=%s agent=%s text_len=%d approval=%s",
                shop_id,
                user_id,
                routed_agent or "supervisor",
                len(final_response_text),
                approval_required,
            )
            yield "data: [DONE]\n\n"

        except asyncio.CancelledError:
            # Client disconnected mid-stream — clean exit, no need to yield [DONE].
            logger.info("Stream cancelled: client disconnected for shop_id=%s", shop_id)
            return
        except Exception as e:
            logger.error(
                "Stream error shop_id=%s user_id=%s: %s", shop_id, user_id, e, exc_info=True
            )
            error_message = str(e) or "Unexpected stream error"
            status_event = {"type": "stream_status", "status": "error", "message": error_message}
            error_event = {"type": "error", "message": error_message}
            yield f"data: {json.dumps(status_event)}\n\n"
            yield f"data: {json.dumps(error_event)}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


# ============================================================================
# Human-in-the-Loop Approval
# ============================================================================

@router.post("/approve")
async def approve_action(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Resume a checkpointed graph after owner approval/rejection.
    
    Request body:
    {
        "shop_id": 123,
        "action_id": "action_xyz",  # From pending_approval
        "approved": true,  # or false to reject
        "reason": "optional reason"
    }
    
    Response:
    {
        "status": "approved",
        "message": "Action executed successfully"
    }
    """
    
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    shop_id = body.get("shop_id")
    action_id = body.get("action_id")
    approved = body.get("approved", False)
    reason = body.get("reason")
    
    # Authorization check
    user_id = _extract_user_id(current_user)
    user_shops = _get_owned_shop_ids(current_user)

    if user_id is None:
        raise HTTPException(status_code=401, detail="Authenticated user_id missing")

    try:
        shop_id = int(shop_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="shop_id must be an integer")

    if shop_id not in user_shops:
        raise HTTPException(status_code=403, detail="Not owner of this shop")

    checkpoint_config = build_checkpoint_config(shop_id, user_id)

    runnable = _SUPERVISOR_RUNNABLE
    snapshot = runnable.get_state(checkpoint_config)

    interrupts = list(snapshot.interrupts or ())
    if not interrupts:
        resumed = _resume_persisted_approval(
            shop_id=shop_id,
            action_id=str(action_id or "").strip() or None,
            approved=bool(approved),
            reason=reason,
            user_id=int(user_id),
        )
        if resumed is None:
            raise HTTPException(status_code=409, detail="No pending approval found for this thread")

        _record_approval_decision(
            shop_id=shop_id,
            action_id=str(action_id or "").strip() or None,
            pending_action=None,
            approved=bool(approved),
            reason=reason,
            user_id=int(user_id),
            resumed=resumed,
        )

        return {
            "status": "approved" if approved else "rejected",
            "message": _state_last_text(resumed),
            "agent": resumed.get("current_agent", "supervisor"),
            "tool_results": resumed.get("tool_results"),
        }

    current_interrupt_id = getattr(interrupts[0], "id", None)
    snapshot_values = cast(Dict[str, Any], snapshot.values or {}) if snapshot else {}
    current_pending_action = cast(Optional[Dict[str, Any]], snapshot_values.get("pending_approval"))
    if action_id and current_interrupt_id and action_id != current_interrupt_id:
        raise HTTPException(status_code=409, detail="action_id does not match the current pending approval")

    resumed = cast(
        Dict[str, Any],
        runnable.invoke(
            Command(resume={"approved": bool(approved), "reason": reason}),
            checkpoint_config,
        ),
    )

    _record_approval_decision(
        shop_id=shop_id,
        action_id=current_interrupt_id,
        pending_action=current_pending_action,
        approved=bool(approved),
        reason=reason,
        user_id=int(user_id),
        resumed=resumed,
    )

    return {
        "status": "approved" if approved else "rejected",
        "message": _state_last_text(resumed),
        "agent": resumed.get("current_agent", "supervisor"),
        "tool_results": resumed.get("tool_results"),
    }


# ============================================================================
# Approval Streaming - SSE
# ============================================================================

@router.post("/approve/stream")
async def approve_action_stream(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Streaming SSE version of /approve.

    Emits thinking-step, tool-result, and text events while the graph
    resumes from the HITL breakpoint so the owner sees live progress.

    Same request body as /approve:
      { "shop_id": 123, "action_id": "...", "approved": true, "reason": "..." }

    Events emitted:
      {type: "thinking_step", step, label, status, agent}
      {type: "reasoning", step, id, text, agent, tool}
      {type: "tool_result", tool, result, agent}
      {type: "text", content}          — streamed response chunks
      {type: "stream_status", status, agent, tool_results}
      [DONE]
    """
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    shop_id = body.get("shop_id")
    action_id = body.get("action_id")
    approved = body.get("approved", False)
    reason = body.get("reason")

    user_id, shop_id = _require_owner_shop_access(shop_id, current_user)

    checkpoint_config = build_checkpoint_config(shop_id, user_id)
    runnable = _SUPERVISOR_RUNNABLE

    # Snapshot retrieval is sync — wrap in thread to avoid blocking the event loop.
    snapshot = await asyncio.to_thread(runnable.get_state, checkpoint_config)
    interrupts = list(snapshot.interrupts or ())

    # ── No live interrupt: fall back to persisted-approval path ──────────────
    if not interrupts:
        async def _no_interrupt_stream():
            resumed = await asyncio.to_thread(
                _resume_persisted_approval,
                shop_id=shop_id,
                action_id=str(action_id or "").strip() or None,
                approved=bool(approved),
                reason=reason,
                user_id=user_id,
            )
            if resumed is None:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No pending approval found for this thread'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            _record_approval_decision(
                shop_id=shop_id,
                action_id=str(action_id or "").strip() or None,
                pending_action=None,
                approved=bool(approved),
                reason=reason,
                user_id=user_id,
                resumed=resumed,
            )
            msg = _state_last_text(resumed)
            for _sse in _iter_text_sse(msg):
                yield _sse
            yield f"data: {json.dumps({'type': 'stream_status', 'status': 'approved' if approved else 'rejected', 'agent': resumed.get('current_agent', 'supervisor'), 'tool_results': resumed.get('tool_results')})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(_no_interrupt_stream(), media_type="text/event-stream")

    # ── Live interrupt: stream graph resume ───────────────────────────────────
    current_interrupt_id = getattr(interrupts[0], "id", None)
    snapshot_values = cast(Dict[str, Any], snapshot.values or {}) if snapshot else {}
    current_pending_action = cast(Optional[Dict[str, Any]], snapshot_values.get("pending_approval"))

    if action_id and current_interrupt_id and action_id != current_interrupt_id:
        raise HTTPException(status_code=409, detail="action_id does not match the current pending approval")

    async def _approval_stream():
        final_response_text = ""
        final_tool_results: Dict[str, Any] = {}
        routed_agent = "supervisor"
        _STEP_TIMEOUT = 150  # seconds per graph step

        try:
            _action_label = "approved" if approved else "rejected"
            yield f"data: {json.dumps({'type': 'thinking_step', 'step': 'approve', 'label': f'Executing {_action_label} action\u2026', 'status': 'active', 'agent': routed_agent})}\n\n"

            update_iter = runnable.stream(
                Command(resume={"approved": bool(approved), "reason": reason}),
                checkpoint_config,
                stream_mode="updates",
            )

            while True:
                update = await asyncio.wait_for(
                    asyncio.to_thread(next, update_iter, None),
                    timeout=_STEP_TIMEOUT,
                )
                if update is None:
                    break
                if not isinstance(update, dict):
                    continue

                for raw_node_name, out in update.items():
                    lg_node = _resolve_thinking_node({"name": raw_node_name})
                    if not lg_node:
                        continue

                    metadata_out = _extract_metadata_from_output(out)
                    ca = _extract_current_agent_from_output(out)
                    if ca and ca not in ("supervisor", "general", "", None):
                        if ca != routed_agent:
                            yield f"data: {json.dumps({'type': 'agent_switch', 'agent': ca})}\n\n"
                        routed_agent = ca

                    start_label = _thinking_label_active(lg_node, routed_agent)
                    yield f"data: {json.dumps({'type': 'thinking_step', 'step': lg_node, 'label': start_label, 'status': 'active', 'agent': routed_agent})}\n\n"

                    for reasoning_event in _normalize_reasoning_events(metadata_out.get("reasoning_events")):
                        yield f"data: {json.dumps({'type': 'reasoning', 'step': lg_node, 'id': reasoning_event.get('id') or f'{lg_node}_reasoning', 'text': str(reasoning_event.get('text')).strip(), 'agent': routed_agent, 'tool': reasoning_event.get('tool')})}\n\n"

                    if isinstance(out, dict) and isinstance(out.get("tool_results"), dict):
                        final_tool_results = out["tool_results"]
                        yield f"data: {json.dumps({'type': 'tool_result', 'tool': lg_node, 'result': final_tool_results, 'agent': routed_agent})}\n\n"

                    if lg_node == "synthesize_response" and isinstance(out, dict):
                        msgs = out.get("messages") or []
                        if msgs:
                            final_response_text = getattr(msgs[-1], "content", "") or ""

                    done_label = _thinking_label_done(lg_node, routed_agent)
                    yield f"data: {json.dumps({'type': 'thinking_step', 'step': lg_node, 'label': done_label, 'status': 'done', 'agent': routed_agent})}\n\n"

        except Exception as stream_exc:
            exc_name = type(stream_exc).__name__
            if "interrupt" not in exc_name.lower():
                logger.error("Approval stream error: %s", stream_exc, exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': str(stream_exc)[:200]})}\n\n"
                yield "data: [DONE]\n\n"
                return

        # Retrieve final text from checkpoint if synthesize_response didn't emit it.
        if not final_response_text:
            try:
                snap = await asyncio.to_thread(runnable.get_state, checkpoint_config)
                if snap and snap.values:
                    final_response_text = _state_last_text(dict(snap.values))
                    if not final_tool_results and isinstance(snap.values.get("tool_results"), dict):
                        final_tool_results = snap.values["tool_results"]
            except Exception as snap_exc:
                logger.warning("Could not retrieve post-approval checkpoint: %s", snap_exc)

        _record_approval_decision(
            shop_id=shop_id,
            action_id=current_interrupt_id,
            pending_action=current_pending_action,
            approved=bool(approved),
            reason=reason,
            user_id=user_id,
            resumed={"current_agent": routed_agent, "tool_results": final_tool_results},
        )

        if final_response_text:
            for _sse in _iter_text_sse(final_response_text):
                yield _sse

        yield f"data: {json.dumps({'type': 'stream_status', 'status': 'approved' if approved else 'rejected', 'agent': routed_agent, 'tool_results': final_tool_results})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_approval_stream(), media_type="text/event-stream")


# ============================================================================
# Conversation History & State
# ============================================================================

@router.get("/history")
async def get_history(
    shop_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get conversation history with Supervisor agent for this shop owner.
    
    Response:
    {
        "messages": [
            {"role": "user", "content": "...", "timestamp": "..."},
            {"role": "assistant", "content": "...", "timestamp": "..."}
        ],
        "checkpoint_id": "tenant_123_45"
    }
    """
    
    # Authorization check
    user_id = _extract_user_id(current_user)
    user_shops = _get_owned_shop_ids(current_user)

    if user_id is None:
        raise HTTPException(status_code=401, detail="Authenticated user_id missing")
    
    try:
        shop_id = int(shop_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="shop_id must be an integer")

    if shop_id not in user_shops:
        raise HTTPException(status_code=403, detail="Not owner of this shop")
    
    checkpoint_config = build_checkpoint_config(shop_id, user_id)
    snapshot = _SUPERVISOR_RUNNABLE.get_state(checkpoint_config)
    values = cast(Dict[str, Any], snapshot.values or {}) if snapshot else {}
    checkpoint_messages = _serialize_checkpoint_messages(values)
    if not checkpoint_messages:
        checkpoint_messages = get_conversation_history(_redis, str(shop_id), str(user_id))

    return {
        "messages": checkpoint_messages,
        "checkpoint_id": f"tenant_{shop_id}_{user_id}",
        "pending": _get_pending_approval_payload(shop_id, user_id),
    }


@router.post("/reset-conversation")
async def reset_conversation(
    shop_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete all checkpoint data for this owner's conversation thread so the
    next message starts a completely fresh context.

    The caller must own the shop (same guard as /history).
    """
    user_id: Optional[int] = current_user.get("user_id")
    user_shops: list[int] = current_user.get("shop_ids") or []

    if not user_id:
        raise HTTPException(status_code=401, detail="Authenticated user_id missing")

    if shop_id not in user_shops:
        raise HTTPException(status_code=403, detail="Not owner of this shop")

    thread_id = _checkpoint_thread_id(shop_id, user_id)
    db = SessionLocal()
    try:
        db.execute(
            text("DELETE FROM checkpoint_writes WHERE thread_id = :tid"),
            {"tid": thread_id},
        )
        db.execute(
            text("DELETE FROM checkpoints WHERE thread_id = :tid"),
            {"tid": thread_id},
        )
        db.commit()
        logger.info("reset-conversation: cleared thread %s for user %s", thread_id, user_id)
    except Exception as exc:
        db.rollback()
        logger.warning("reset-conversation: failed to clear thread %s: %s", thread_id, exc)
        raise HTTPException(status_code=500, detail="Failed to reset conversation")
    finally:
        db.close()

    return {"status": "ok", "thread_id": thread_id}


@router.get("/pending")
async def get_pending_approvals(
    shop_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get pending approval actions awaiting owner decision.
    
    Response:
    {
        "pending": [
            {
                "action_id": "action_xyz",
                "action": "close_queue",
                "details": {...},
                "created_at": "..."
            }
        ]
    }
    """
    
    # Authorization check
    user_id = _extract_user_id(current_user)
    user_shops = _get_owned_shop_ids(current_user)
    
    try:
        shop_id = int(shop_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="shop_id must be an integer")

    if user_id is None:
        raise HTTPException(status_code=401, detail="Authenticated user_id missing")

    if shop_id not in user_shops:
        raise HTTPException(status_code=403, detail="Not owner of this shop")

    metrics = db_interface.get_shop_live_wait_metrics(shop_id) or {}
    return {"pending": _get_pending_approval_payload(shop_id, user_id, metrics=metrics)}


@router.get("/briefing")
async def get_owner_briefing(
    shop_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Return a lightweight operational briefing for the owner inbox."""
    user_id = _extract_user_id(current_user)
    user_shops = _get_owned_shop_ids(current_user)

    try:
        shop_id = int(shop_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="shop_id must be an integer")

    if user_id is None:
        raise HTTPException(status_code=401, detail="Authenticated user_id missing")

    if shop_id not in user_shops:
        raise HTTPException(status_code=403, detail="Not owner of this shop")

    shop = db_interface.get_shop_by_id(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    cached_snapshot = get_cached_shop_briefing_snapshot(shop_id)
    if not cached_snapshot:
        cached_snapshot = refresh_shop_briefing_cache(shop_id, shop.get("name"))

    metrics = dict((cached_snapshot or {}).get("metrics") or {})
    live_metrics = db_interface.get_shop_live_wait_metrics(shop_id) or {}
    metrics.update({key: value for key, value in live_metrics.items() if value is not None})

    if not metrics.get("active_services"):
        services = db_interface.get_shop_services(shop_id, include_inactive=False) or []
        metrics["active_services"] = len(services)
    if not metrics.get("active_employees"):
        employees = db_interface.get_shop_employees(shop_id, is_active=True) or []
        metrics["active_employees"] = len(employees)

    pending = _get_pending_approval_payload(shop_id, user_id, metrics=live_metrics or metrics)

    active_services = int(metrics.get("active_services", 0) or 0)
    active_employees = int(metrics.get("active_employees", 0) or 0)
    pending_count = len(pending)
    queue_length = int(metrics.get("queue_length", 0) or 0)
    wait_minutes = int(metrics.get("estimated_wait_minutes", 0) or 0)
    serving_count = int(metrics.get("people_being_served", 0) or 0)
    today_total_revenue = float(metrics.get("today_revenue", 0.0) or 0.0)
    today_transactions = int(metrics.get("today_transactions", 0) or 0)
    weekly_total_revenue = float(metrics.get("weekly_revenue", 0.0) or 0.0)

    briefing = build_owner_briefing(
        shop_id=shop_id,
        shop_name=shop.get("name", "Your shop"),
        metrics={
            **metrics,
            "queue_length": queue_length,
            "estimated_wait_minutes": wait_minutes,
            "people_being_served": serving_count,
            "active_employees": active_employees,
        },
        active_services=active_services,
        active_employees=active_employees,
        pending_count=pending_count,
        today_revenue=today_total_revenue,
        today_transactions=today_transactions,
        weekly_revenue=weekly_total_revenue,
        alert_history=get_shop_alert_history(shop_id),
        generated_at=(cached_snapshot or {}).get("generated_at") or datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        source=str((cached_snapshot or {}).get("source") or "live"),
    )
    briefing["pending"] = pending
    briefing["recent_notifications"] = _get_notification_feed_payload(shop_id, limit=10)
    return briefing


@router.get("/feed")
async def get_feed(
    shop_id: int,
    limit: int = 25,
    current_user: dict = Depends(get_current_user),
):
    """Return persisted owner-facing feed events sourced from agent_notifications."""
    user_id, shop_id = _require_owner_shop_access(shop_id, current_user)
    del user_id

    normalized_limit = max(1, min(int(limit), 100))
    return {"events": _get_notification_feed_payload(shop_id, limit=normalized_limit)}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Mark a persisted owner-facing notification as read."""
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON request body") from exc

    _, shop_id = _require_owner_shop_access(body.get("shop_id"), current_user)

    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        notification = repo.mark_notification_read_for_shop(notification_id, shop_id)
        if notification is None:
            raise HTTPException(status_code=404, detail="Notification not found")
        return {"notification": _serialize_notification_feed_event(notification)}
    finally:
        db.close()


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Mark all persisted owner-facing notifications for a shop as read."""
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON request body") from exc

    _, shop_id = _require_owner_shop_access(body.get("shop_id"), current_user)

    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        updated = repo.mark_all_notifications_read(shop_id)
        return {"updated": updated}
    finally:
        db.close()


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
async def health_check():
    """
    Health check for LangGraph agent.
    
    Verifies:
    - LLM connectivity (provider-aware: ollama, nvidia, openai-compatible)
    - PostgreSQL checkpoint connectivity
    - Redis connectivity
    - Agent graph buildability
    """
    import httpx
    from agents.llm_factory import normalize_provider, default_api_base_url_for_provider, _default_api_key

    health = {
        "status": "ok",
        "components": {}
    }

    # Check LLM — provider-aware probe
    llm_provider = normalize_provider(os.getenv("LLM_PROVIDER", "ollama"))
    try:
        if llm_provider == "ollama":
            ollama_base = os.getenv("OLLAMA_URL", "http://localhost:11434/v1").rstrip("/")
            if ollama_base.endswith("/v1"):
                ollama_base = ollama_base[:-3]
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{ollama_base}/api/tags")
                resp.raise_for_status()
                models = [m.get("name", "") for m in resp.json().get("models", [])]
            health["components"]["llm"] = f"ok (ollama, {len(models)} model(s))"
        elif llm_provider == "nvidia":
            api_key = _default_api_key("nvidia") or ""
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    "https://integrate.api.nvidia.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                model_count = len(resp.json().get("data", []))
            health["components"]["llm"] = f"ok (nvidia nim, {model_count} model(s))"
        else:
            # OpenAI-compatible: probe /v1/models on the configured base URL
            base_url = default_api_base_url_for_provider(llm_provider) or os.getenv("OPENAI_BASE_URL", "")
            if base_url:
                api_key = _default_api_key(llm_provider) or ""
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{base_url.rstrip('/')}/models", headers=headers)
                    resp.raise_for_status()
                health["components"]["llm"] = f"ok ({llm_provider})"
            else:
                health["components"]["llm"] = f"skipped (no base url for {llm_provider})"
    except Exception as e:
        health["status"] = "degraded"
        health["components"]["llm"] = f"error ({llm_provider}): {str(e)[:120]}"

    # Check PostgreSQL (checkpoints)
    try:
        from agents.checkpoints import get_checkpoint_saver
        get_checkpoint_saver()
        health["components"]["postgres"] = "ok"
    except Exception as e:
        health["status"] = "degraded"
        health["components"]["postgres"] = f"error: {str(e)}"

    # Check Redis
    try:
        from redis_client import redis_client as _redis
        if _redis.client is not None:
            _redis.client.ping()
            health["components"]["redis"] = "ok"
        else:
            health["status"] = "degraded"
            health["components"]["redis"] = "disabled (no connection)"
    except Exception as e:
        health["status"] = "degraded"
        health["components"]["redis"] = f"error: {str(e)[:80]}"

    # Check graph compilation
    try:
        from agents.supervisor import create_supervisor_runnable
        runnable = create_supervisor_runnable()
        health["components"]["graph"] = "ok"
    except Exception as e:
        health["status"] = "error"
        health["components"]["graph"] = f"error: {str(e)}"

    # Check Temporal connectivity (only when TEMPORAL_ENABLED=true)
    from agents.temporal_config import temporal_enabled, TEMPORAL_ADDRESS
    if temporal_enabled():
        try:
            from temporalio.client import Client as TemporalClient
            await asyncio.wait_for(
                TemporalClient.connect(TEMPORAL_ADDRESS, namespace="default"),
                timeout=4.0,
            )
            health["components"]["temporal"] = "ok"
        except Exception as e:
            health["components"]["temporal"] = f"error: {str(e)[:80]}"
    else:
        health["components"]["temporal"] = "disabled"

    # Check Odoo ERP
    try:
        from integrations.odoo_client import odoo_client
        odoo_info = odoo_client.health_check()
        if odoo_info.get("enabled"):
            health["components"]["odoo"] = odoo_info.get("status", "unknown")
            if odoo_info.get("version"):
                health["components"]["odoo_version"] = odoo_info["version"]
        else:
            health["components"]["odoo"] = "disabled"
    except Exception as e:
        health["components"]["odoo"] = f"error: {str(e)}"

    return health


__all__ = ["router"]
