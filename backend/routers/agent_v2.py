"""
FastAPI router for LangGraph-based owner-facing agent (v2).

Endpoints:
- POST /api/v2/agent/chat - Synchronous chat
- POST /api/v2/agent/chat/stream - SSE streaming chat
- POST /api/v2/agent/approve - Approve/reject HITL action
- GET /api/v2/agent/history - Get conversation history
- GET /api/v2/agent/pending - Get pending approvals
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

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Dict, Any, cast, Optional
import asyncio
import base64
from datetime import datetime
import json
import logging
from langchain_core.messages import HumanMessage, SystemMessage

from redis_client import redis_client as _redis
from langgraph.types import Command

from agents import approval_policy
from agents.supervisor import create_supervisor_runnable
from agents.briefings import (
    build_owner_briefing,
    enrich_pending_approval_payload,
    get_cached_shop_briefing_snapshot,
    get_shop_alert_history,
    refresh_shop_briefing_cache,
)
from agents.memory_context import merge_and_rank_memories, format_memory_context
from agents.state import AgentState
from agents.checkpoints import build_checkpoint_config, get_sync_checkpoint_saver
from shared.auth_utils import get_current_user
from db_interface import DatabaseInterface
from database import SessionLocal
from modules.agent.models import ApprovalStatus, GoalSource, GoalStatus, PolicyMode, RunStatus
from modules.agent.work_repository import AgentWorkRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/agent", tags=["agent_v2"])
db_interface = DatabaseInterface()

# ---------------------------------------------------------------------------
# Real-time thinking-step metadata for the streaming UI
# ---------------------------------------------------------------------------

# LangGraph node names that are surfaced as visible pipeline steps in the UI.
_THINKING_NODES: frozenset = frozenset(
    {"classify_intent", "route_to_agent", "execute_plan", "synthesize_response"}
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
        "route_to_agent": f"Routing to {agent_name}" if has_agent else "Routing request",
        "execute_plan": f"Running {agent_name}" if has_agent else "Processing request",
        "synthesize_response": "Generating response",
    }.get(node, node)


def _thinking_label_done(node: str, routed_agent: Optional[str]) -> str:
    has_agent = routed_agent and routed_agent not in ("supervisor", "general")
    agent_name = _AGENT_DISPLAY_LABELS.get(routed_agent or "", "Specialist")
    return {
        "classify_intent": f"Classified {agent_name}" if has_agent else "Classified General",
        "route_to_agent": f"{agent_name}" if has_agent else "Supervisor",
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
    None: [
        "Give me today's queue summary",
        "Show this week's revenue trend",
        "Who is on shift now?",
        "What can you help me with?",
    ],
}


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


def _state_last_text(state_values: Dict[str, Any]) -> str:
    messages = state_values.get("messages") or []
    if not messages:
        return ""
    final_message = messages[-1]
    return getattr(final_message, "content", str(final_message))


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
        serialized.append(
            {
                "role": role,
                "content": str(getattr(message, "content", "")),
            }
        )
    return serialized


def _get_pending_approval_payload(
    shop_id: int,
    user_id: int,
    metrics: Optional[Dict[str, Any]] = None,
) -> list[Dict[str, Any]]:
    """Return current pending approval payloads for a tenant thread."""
    checkpoint_config = build_checkpoint_config(shop_id, user_id)
    runnable = _SUPERVISOR_RUNNABLE
    snapshot = runnable.get_state(checkpoint_config)

    pending: list[Dict[str, Any]] = []
    if snapshot and snapshot.interrupts:
        values = cast(Dict[str, Any], snapshot.values or {})
        pending_approval = values.get("pending_approval")
        interrupt_id = getattr(snapshot.interrupts[0], "id", None)
        if pending_approval:
            pending.append(
                enrich_pending_approval_payload(
                    {
                        "action_id": interrupt_id,
                        "action": pending_approval.get("action"),
                        "details": pending_approval.get("details", {}),
                        "shop_id": pending_approval.get("shop_id", shop_id),
                    },
                    metrics=metrics,
                )
            )

    return pending


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


def _persist_chat_turn_memory(
    *,
    shop_id: int,
    user_id: int,
    user_message: str,
    assistant_response: str,
    route: str,
) -> None:
    """Best-effort persistence for tenant-scoped owner chat memory."""
    try:
        db_interface.add_agent_memory(
            shop_id=shop_id,
            user_id=user_id,
            memory_type="chat_user",
            content=user_message,
            source=route,
            importance_score=0.6,
            memory_meta={"role": "user"},
        )
        db_interface.add_agent_memory(
            shop_id=shop_id,
            user_id=user_id,
            memory_type="chat_assistant",
            content=assistant_response,
            source=route,
            importance_score=0.7,
            memory_meta={"role": "assistant"},
        )
    except Exception as e:
        logger.warning("Agent memory persistence failed (non-fatal): %s", str(e))


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


def _build_work_title(message: str, fallback: str = "Owner request") -> str:
    normalized = " ".join((message or "").split())
    if not normalized:
        return fallback
    return normalized if len(normalized) <= 120 else f"{normalized[:117]}..."


def _create_chat_work_context(shop_id: int, user_id: int, message: str, *, is_voice: bool = False) -> Dict[str, Any]:
    trigger_source = "voice_chat" if is_voice else "chat"
    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        goal = repo.create_goal(
            shop_id=shop_id,
            created_by_user_id=user_id,
            source=GoalSource.CHAT,
            goal_type="owner_request",
            title=_build_work_title(message),
            description=message,
            autonomy_policy="interactive",
            context={"message": message, "trigger_source": trigger_source},
        )
        goal_id = cast(int, getattr(goal, "id"))
        run = repo.create_run(
            shop_id=shop_id,
            goal_id=goal_id,
            triggered_by_user_id=user_id,
            run_type="chat",
            trigger_source=trigger_source,
            execution_mode="interactive",
            graph_thread_id=f"tenant_{shop_id}_{user_id}",
            current_agent="supervisor",
            input_payload={"message": message},
            event_context={"trigger_source": trigger_source},
        )
        run_id = cast(int, getattr(run, "id"))
        return {
            "goal_id": goal_id,
            "run_id": run_id,
            "execution_mode": "interactive",
            "trigger_source": trigger_source,
            "event_context": {"trigger_source": trigger_source, "goal_id": goal_id, "run_id": run_id},
        }
    finally:
        db.close()


def _persist_approval_request(
    *,
    shop_id: int,
    user_id: int,
    goal_id: int,
    run_id: int,
    routed_agent: str,
    pending_action: Dict[str, Any],
) -> Dict[str, Any]:
    action_id = str(pending_action.get("action_id") or "").strip()
    details = pending_action.get("details") or {}
    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        approval = None
        if action_id:
            approval = repo.get_pending_approval_by_action_id(shop_id, action_id)
        if approval is None:
            approval = repo.create_approval_request(
                external_action_id=action_id or None,
                shop_id=shop_id,
                goal_id=goal_id,
                run_id=run_id,
                requested_by_user_id=user_id,
                requested_by_agent=routed_agent or "supervisor",
                action_type=str(pending_action.get("action") or "approval_required"),
                title=_build_work_title(
                    str(pending_action.get("title") or details.get("title") or pending_action.get("action") or "Approval required"),
                    fallback="Approval required",
                ),
                rationale=str(pending_action.get("rationale") or details.get("reason") or details.get("rationale") or "") or None,
                expected_impact=str(pending_action.get("expected_impact") or details.get("impact") or details.get("expected_impact") or "") or None,
                urgency=str(details.get("urgency") or pending_action.get("urgency") or "normal"),
                request_payload=pending_action,
            )
        enriched = dict(pending_action)
        enriched["approval_request_id"] = approval.id
        return enriched
    finally:
        db.close()


def _finalize_chat_work_context(
    *,
    shop_id: int,
    user_id: int,
    goal_id: int,
    run_id: int,
    routed_agent: str,
    response_text: str,
    tool_results: Optional[Dict[str, Any]],
    approval_required: bool,
    pending_action: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        output_payload = {
            "response": response_text,
            "agent": routed_agent,
            "tool_results": tool_results or {},
        }
        if approval_required:
            repo.update_goal_status(goal_id, GoalStatus.WAITING_APPROVAL, summary=response_text or "Waiting for owner approval")
            repo.update_run_status(
                run_id,
                RunStatus.WAITING_APPROVAL,
                output_payload=output_payload,
                current_agent=routed_agent or "supervisor",
            )
            if pending_action:
                return _persist_approval_request(
                    shop_id=shop_id,
                    user_id=user_id,
                    goal_id=goal_id,
                    run_id=run_id,
                    routed_agent=routed_agent or "supervisor",
                    pending_action=pending_action,
                )
            return pending_action

        repo.update_goal_status(goal_id, GoalStatus.COMPLETED, summary=response_text)
        repo.update_run_status(
            run_id,
            RunStatus.COMPLETED,
            output_payload=output_payload,
            current_agent=routed_agent or "supervisor",
        )
        return pending_action
    finally:
        db.close()


def _record_approval_decision(
    *,
    shop_id: int,
    action_id: Optional[str],
    approved: bool,
    reason: Optional[str],
    user_id: int,
    resumed: Dict[str, Any],
) -> None:
    if not action_id:
        return
    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        approval = repo.get_pending_approval_by_action_id(shop_id, action_id)
        if approval is None:
            return
        approval_id = cast(int, getattr(approval, "id"))
        repo.decide_approval_request(
            approval_id,
            status=ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED,
            decided_by_user_id=user_id,
            decision_reason=reason,
            decision_payload={
                "message": _state_last_text(resumed),
                "agent": resumed.get("current_agent", "supervisor"),
                "tool_results": resumed.get("tool_results"),
            },
        )
        goal_id = getattr(approval, "goal_id", None)
        if goal_id is not None:
            repo.update_goal_status(
                int(goal_id),
                GoalStatus.COMPLETED if approved else GoalStatus.CANCELLED,
                summary=_state_last_text(resumed),
            )
        run_id = getattr(approval, "run_id", None)
        if run_id is not None:
            repo.update_run_status(
                int(run_id),
                RunStatus.COMPLETED if approved else RunStatus.CANCELLED,
                output_payload={
                    "message": _state_last_text(resumed),
                    "agent": resumed.get("current_agent", "supervisor"),
                    "tool_results": resumed.get("tool_results"),
                },
                current_agent=resumed.get("current_agent", "supervisor"),
            )
    finally:
        db.close()


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

        # Touch selected memories for recency tracking.
        for memory in selected:
            memory_id = memory.get("id")
            if isinstance(memory_id, int):
                db_interface.touch_agent_memory(memory_id)

        return format_memory_context(selected)
    except Exception as e:
        logger.warning("Agent memory retrieval failed (non-fatal): %s", str(e))
        return ""


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
    
    if not message:
        raise HTTPException(status_code=400, detail="message field required")
    
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
    
    # Build checkpoint config for this tenant
    checkpoint_config = build_checkpoint_config(shop_id, user_id)
    work_context = _create_chat_work_context(shop_id, int(user_id), message)
    
    # Create initial state
    memory_context = _build_memory_context(shop_id, int(user_id), message)
    input_messages = []
    if memory_context:
        input_messages.append(SystemMessage(content=memory_context))
    input_messages.append(HumanMessage(content=message))

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
        runnable = _SUPERVISOR_RUNNABLE

        # Run in thread pool to avoid blocking the asyncio event loop.
        # runnable.invoke() is synchronous (uses sync Postgres checkpointer + sync LLM calls).
        result = cast(Dict[str, Any], await asyncio.to_thread(runnable.invoke, initial_state, checkpoint_config))
        pending_action = _extract_pending_action(result)
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
        )

        _persist_chat_turn_memory(
            shop_id=shop_id,
            user_id=int(user_id),
            user_message=message,
            assistant_response=response_text,
            route="/api/v2/agent/chat",
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
    
    if not message:
        raise HTTPException(status_code=400, detail="message field required")
    
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
    
    # Create streaming generator
    async def event_generator():
        try:
            # Build checkpoint config
            checkpoint_config = build_checkpoint_config(shop_id, user_id)
            work_context = _create_chat_work_context(shop_id, int(user_id), message, is_voice=bool(is_voice))

            # Create initial state
            memory_context = _build_memory_context(shop_id, int(user_id), message)
            input_messages = []
            if memory_context:
                input_messages.append(SystemMessage(content=memory_context))
            input_messages.append(HumanMessage(content=message))

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
            pending_action: Optional[Dict[str, Any]] = None

            # ----------------------------------------------------------------
            # Stream graph execution node-by-node via sync stream updates.
            # This keeps compatibility with the sync Postgres checkpointer
            # while still emitting real-time thinking-step events.
            # ----------------------------------------------------------------
            try:
                update_iter = runnable.stream(
                    initial_state,
                    config=checkpoint_config,
                    stream_mode="updates",
                )

                while True:
                    update = await asyncio.to_thread(next, update_iter, None)
                    if update is None:
                        break
                    if not isinstance(update, dict):
                        continue

                    for raw_node_name, out in update.items():
                        lg_node = _resolve_thinking_node({"name": raw_node_name})
                        if not lg_node:
                            continue

                        # Emit active first for visual progression.
                        start_label = _thinking_label_active(lg_node, routed_agent)
                        yield f"data: {json.dumps({'type': 'thinking_step', 'step': lg_node, 'label': start_label, 'status': 'active', 'agent': routed_agent})}\n\n"

                        ca = _extract_current_agent_from_output(out)
                        if ca and ca not in ("supervisor", "general", "", None):
                            if ca != routed_agent:
                                yield f"data: {json.dumps({'type': 'agent_switch', 'agent': ca})}\n\n"
                            routed_agent = ca

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
                        if snapshot.next:
                            # Graph is paused at a breakpoint (approval required).
                            pending_action = _extract_pending_action(state_vals)
                            if pending_action:
                                pending_action["shop_id"] = shop_id
                                pending_action = enrich_pending_approval_payload(
                                    pending_action,
                                    metrics=db_interface.get_shop_live_wait_metrics(shop_id) or {},
                                )
                except Exception as state_exc:
                    logger.warning("Could not retrieve final checkpoint state: %s", state_exc)

            approval_required = pending_action is not None
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
            )

            if pending_action:
                yield f"data: {json.dumps({'type': 'approval_required', 'action': pending_action.get('action'), 'details': pending_action})}\n\n"

            _persist_chat_turn_memory(
                shop_id=shop_id,
                user_id=int(user_id),
                user_message=message,
                assistant_response=final_response_text,
                route="/api/v2/agent/chat/stream",
            )

            if isinstance(final_tool_results, dict) and final_tool_results:
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': final_tool_results.get('tool') or routed_agent or 'operation', 'result': final_tool_results, 'agent': routed_agent})}\n\n"

            # Stream response text character-by-character.
            for char in (final_response_text or ""):
                yield f"data: {json.dumps({'type': 'text', 'content': char})}\n\n"

            # Emit structured chart/file payloads for frontend insights panel and inline attachments.
            if routed_agent == "finance" and isinstance(final_tool_results, dict):
                points = final_tool_results.get("points")
                if isinstance(points, list) and points:
                    chart_points = []
                    for row in points[:60]:
                        try:
                            chart_points.append(
                                {
                                    "label": str(row.get("period", "")),
                                    "value": float(row.get("revenue", 0.0) or 0.0),
                                }
                            )
                        except (TypeError, ValueError):
                            continue

                    if chart_points:
                        chart_event = {
                            "type": "chart",
                            "title": f"Revenue Trend ({final_tool_results.get('window', 'custom').replace('_', ' ')})",
                            "chartType": "line" if len(chart_points) > 2 else "bar",
                            "data": chart_points,
                            "xKey": "label",
                            "yKey": "value",
                        }
                        yield f"data: {json.dumps(chart_event)}\n\n"

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

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Stream error: {str(e)}", exc_info=True)
            error_event = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_event)}\n\n"
    
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
        raise HTTPException(status_code=409, detail="No pending approval found for this thread")

    current_interrupt_id = getattr(interrupts[0], "id", None)
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

    return {
        "messages": _serialize_checkpoint_messages(values),
        "checkpoint_id": f"tenant_{shop_id}_{user_id}",
        "pending": _get_pending_approval_payload(shop_id, user_id),
    }


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
    return briefing


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
async def health_check():
    """
    Health check for LangGraph agent.
    
    Verifies:
    - Ollama LLM connectivity
    - PostgreSQL checkpoint connectivity
    - Agent graph buildability
    """
    
    health = {
        "status": "ok",
        "components": {}
    }
    
    # Check LLM (Ollama)
    try:
        from agents.supervisor import get_llm
        llm = get_llm()
        # TODO: Actual ping
        health["components"]["ollama"] = "ok"
    except Exception as e:
        health["status"] = "degraded"
        health["components"]["ollama"] = f"error: {str(e)}"
    
    # Check PostgreSQL (checkpoints)
    try:
        from agents.checkpoints import get_checkpoint_saver
        get_checkpoint_saver()
        health["components"]["postgres"] = "ok"
    except Exception as e:
        health["status"] = "degraded"
        health["components"]["postgres"] = f"error: {str(e)}"
    
    # Check graph compilation
    try:
        from agents.supervisor import create_supervisor_runnable
        runnable = create_supervisor_runnable()
        health["components"]["graph"] = "ok"
    except Exception as e:
        health["status"] = "error"
        health["components"]["graph"] = f"error: {str(e)}"

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
