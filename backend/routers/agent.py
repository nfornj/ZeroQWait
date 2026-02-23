from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from shared.auth_utils import get_current_user_optional
from agent_logic import MasterAgent
from db_interface import db_interface

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks

router = APIRouter()

class AgentChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    is_voice: bool = False

# --- Distributed Rate Limiter ---
def check_rate_limit(ip: str) -> bool:
    from redis_client import redis_client
    return redis_client.check_rate_limit(ip, limit=20, window=60)

@router.get("/health")
async def agent_health():
    return {"status": "ok", "message": "Agent router is active"}

# Remove Shop-specific FrontDesk agent for now as it was removed from core logic.
# Can be re-enabled if MasterAgent supports shop-specific info routing.

@router.post("/master/chat")
async def master_agent_chat(
    request: AgentChatRequest,
    req: Request, # FastAPI Request object to get IP
    background_tasks: BackgroundTasks,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Global Master AI Chat Endpoint.
    Uses server-side Redis session storage for conversation history.
    """
    from redis_client import redis_client
    
    # 1. Rate Check
    client_ip = req.client.host
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please slow down.")

    print(f"[DEBUG] Master agent chat request received: {request.message}")
    
    try:
        agent = MasterAgent()
        
        # 2. Use Session ID from request, or fallback to IP-based session for guests
        final_session_id = request.session_id or f"guest_{client_ip}"
        
        # 3. Determine User ID
        user_id = str(current_user["id"]) if current_user else f"anon_{client_ip}"
        
        # 4. SERVER-SIDE HISTORY: Fetch from Redis instead of trusting client
        server_history = redis_client.get_session_history(final_session_id, limit=10)
        
        # Merge: Use server history, but allow client to pass initial context if new session
        if server_history:
            history_to_use = server_history
        elif request.history:
            # New session with client-provided context (first message)
            history_to_use = request.history
        else:
            history_to_use = []
        
        # 5. Store the incoming user message
        redis_client.add_session_message(final_session_id, "user", request.message)
        background_tasks.add_task(db_interface.add_message_to_history, final_session_id, "user", request.message)

        result = await agent.chat(
            session_id=final_session_id,
            user_msg=request.message, 
            history=history_to_use, 
            latitude=request.latitude, 
            longitude=request.longitude,
            context=request.context,
            user_id=user_id,
            is_voice=request.is_voice
        )
        
        # 6. Store the agent's response
        response_text = result.get('response', '')
        redis_client.add_session_message(final_session_id, "assistant", response_text)
        background_tasks.add_task(db_interface.add_message_to_history, final_session_id, "assistant", response_text)
        
        print(f"[DEBUG] Master agent response: {response_text[:50]}...")
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        # Graceful Error Handling
        return {
            "response": "I'm encountering a temporary server issue. Please try again in a moment.",
            "actions": [],
            "error": str(e)
        }
