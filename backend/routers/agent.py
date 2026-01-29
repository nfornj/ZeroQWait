from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from auth_utils import get_current_user_optional
from agent_logic import FrontDeskAgent, MasterAgent
from db_interface import db_interface

from fastapi import APIRouter, Depends, HTTPException, status, Request

router = APIRouter()

class AgentChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None

# --- Simple In-Memory Rate Limiter ---
import time
RATE_LIMITS = {} # ip -> {tokens, last_update}
RATE_LIMIT_CAPACITY = 20
RATE_LIMIT_FILL_RATE = 20 / 60.0 # tokens per second

def check_rate_limit(ip: str) -> bool:
    now = time.time()
    if ip not in RATE_LIMITS:
        RATE_LIMITS[ip] = {"tokens": RATE_LIMIT_CAPACITY, "last_update": now}
    
    bucket = RATE_LIMITS[ip]
    elapsed = now - bucket["last_update"]
    bucket["last_update"] = now
    
    # Refill
    bucket["tokens"] = min(RATE_LIMIT_CAPACITY, bucket["tokens"] + elapsed * RATE_LIMIT_FILL_RATE)
    
    if bucket["tokens"] >= 1:
        bucket["tokens"] -= 1
        return True
    return False

@router.get("/health")
async def agent_health():
    return {"status": "ok", "message": "Agent router is active"}

@router.post("/chat/{shop_id}")
async def agent_chat(
    shop_id: int,
    request: AgentChatRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Intelligent Agent Chat Endpoint.
    Acts as the 'Front Desk' for the shop.
    """
    try:
        # Get shop info for the agent persona
        shop = db_interface.get_shop_by_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        # Initialize Agent
        agent = FrontDeskAgent(
            shop_id=shop_id, 
            shop_name=shop["name"],
            ai_agent_name=shop.get("ai_agent_name")
        )
        
        # Process Message
        result = await agent.chat(request.message, request.history)
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent Error: {str(e)}"
        )


@router.post("/master/chat")
async def master_agent_chat(
    request: AgentChatRequest,
    req: Request, # FastAPI Request object to get IP
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Global Master AI Chat Endpoint.
    """
    # 1. Rate Check
    client_ip = req.client.host
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please slow down.")

    print(f"[DEBUG] Master agent chat request received: {request.message}")
    
    try:
        agent = MasterAgent()
        
        # 2. Use Session ID from request, or fallback to IP-based session for guests
        final_session_id = request.session_id or f"guest_{client_ip}"
        
        result = await agent.chat(
            session_id=final_session_id,
            user_msg=request.message, 
            history=request.history, 
            latitude=request.latitude, 
            longitude=request.longitude,
            context=request.context
        )
        print(f"[DEBUG] Master agent response: {result['response'][:50]}...")
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        # 3. Graceful Error Handling
        return {
            "response": "I'm encountering a temporary server issue. Please try again in a moment.",
            "actions": [],
            "error": str(e)
        }
