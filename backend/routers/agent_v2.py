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
import json
import logging
from langchain_core.messages import HumanMessage, SystemMessage

from redis_client import redis_client as _redis
from langgraph.types import Command

from agents.supervisor import create_supervisor_runnable
from agents.memory_context import merge_and_rank_memories, format_memory_context
from agents.state import AgentState
from agents.checkpoints import build_checkpoint_config, get_sync_checkpoint_saver
from shared.auth_utils import get_current_user
from db_interface import DatabaseInterface

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
        "pending_approval": None,
        "needs_human_input": False,
        "tool_results": None,
        "metadata": {"shop_id": shop_id, "user_id": user_id}
    }
    
    # Run supervisor graph
    try:
        runnable = _SUPERVISOR_RUNNABLE
        
        # Sync invoke (Phase 1 - simple version)
        result = cast(Dict[str, Any], runnable.invoke(initial_state, checkpoint_config))
        pending_action = _extract_pending_action(result)
        approval_required = bool((result.get("__interrupt__") or []) or result.get("needs_human_input", False))
        
        # Extract final response
        messages = result.get("messages", [])
        if messages:
            final_message = messages[-1]
            response_text = getattr(final_message, "content", str(final_message))
        else:
            response_text = "No response"

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
            "metadata": result.get("metadata", {})
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
                "pending_approval": None,
                "needs_human_input": False,
                "tool_results": None,
                "metadata": {"shop_id": shop_id, "user_id": user_id, "is_voice": is_voice},
            }

            runnable = _SUPERVISOR_RUNNABLE
            routed_agent: Optional[str] = None
            final_response_text = ""
            final_tool_results: Dict[str, Any] = {}

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
                                yield f"data: {json.dumps({'type': 'approval_required', 'action': pending_action.get('action'), 'details': pending_action})}\n\n"
                except Exception as state_exc:
                    logger.warning("Could not retrieve final checkpoint state: %s", state_exc)

            _persist_chat_turn_memory(
                shop_id=shop_id,
                user_id=int(user_id),
                user_message=message,
                assistant_response=final_response_text,
                route="/api/v2/agent/chat/stream",
            )

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
    
    # TODO: Load checkpoint history from PostgreSQL
    # For now, return placeholder
    return {
        "messages": [],
        "checkpoint_id": f"tenant_{shop_id}_{user_id}",
        "note": "[Phase 1] History loading not yet implemented"
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

    checkpoint_config = build_checkpoint_config(shop_id, user_id)
    runnable = _SUPERVISOR_RUNNABLE
    snapshot = runnable.get_state(checkpoint_config)

    pending = []
    if snapshot and snapshot.interrupts:
        values = cast(Dict[str, Any], snapshot.values or {})
        pending_approval = values.get("pending_approval")
        interrupt_id = getattr(snapshot.interrupts[0], "id", None)
        if pending_approval:
            pending.append({
                "action_id": interrupt_id,
                "action": pending_approval.get("action"),
                "details": pending_approval.get("details", {}),
                "shop_id": pending_approval.get("shop_id", shop_id),
            })

    return {"pending": pending}


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
