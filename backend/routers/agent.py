from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from auth_utils import get_current_user_optional
from agent_logic import FrontDeskAgent, MasterAgent
from db_interface import db_interface

router = APIRouter()

class AgentChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []

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
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Global Master AI Chat Endpoint.
    Helpful assistant for the landing page.
    """
    try:
        agent = MasterAgent()
        result = await agent.chat(request.message, request.history)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Master Agent Error: {str(e)}"
        )
