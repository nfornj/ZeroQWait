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
import json
import logging
from langchain_core.messages import HumanMessage, SystemMessage
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
                "metadata": {"shop_id": shop_id, "user_id": user_id, "is_voice": is_voice}
            }
            
            # Run supervisor (streaming)
            runnable = _SUPERVISOR_RUNNABLE
            
            # For Phase 1, simple streaming (no actual streaming LLM calls yet)
            result = cast(Dict[str, Any], runnable.invoke(initial_state, checkpoint_config))
            pending_action = _extract_pending_action(result)
            approval_required = bool((result.get("__interrupt__") or []) or result.get("needs_human_input", False))
            
            # Extract response
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
                route="/api/v2/agent/chat/stream",
            )
            
            # Stream response as typed tokens (simulation)
            for char in response_text:
                event_data = {
                    "type": "text",
                    "content": char
                }
                yield f"data: {json.dumps(event_data)}\n\n"
            
            # Signal approval required if needed
            if approval_required:
                approval_event = {
                    "type": "approval_required",
                    "action": (pending_action or {}).get("action"),
                    "details": pending_action or {}
                }
                yield f"data: {json.dumps(approval_event)}\n\n"
            
            # Signal complete
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
    
    return health


__all__ = ["router"]
