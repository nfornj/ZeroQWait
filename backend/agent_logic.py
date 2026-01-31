import os
import json
import logging
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, ModelRetry
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from db_interface import db_interface

logger = logging.getLogger(__name__)

# --- PydanticAI Shared Configuration ---

@dataclass
class MasterAgentDeps:
    session_id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    context: Optional[Dict[str, Any]] = None
    actions: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class FrontDeskDeps:
    shop_id: int
    shop_name: str
    ai_agent_name: str
    session_id: str
    actions: List[Dict[str, Any]] = field(default_factory=list)

class MasterResponse(BaseModel):
    response: str = Field(description="The friendly response to show the user.")

# Configure Ollama Model
ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
model = OpenAIModel(
    'llama3.2',
    provider=OpenAIProvider(base_url=ollama_url, api_key='ollama'),
)

# --- MASTER AGENT (Marketing Page Assistant) ---

MASTER_SYSTEM_PROMPT = (
    "You are ZeroQ, the AI Assistant for ZeroQwait - a queue management platform. "
    "Your goal is to help users find shops, understand our pricing, and explore our features.\n\n"
    
    "## CRITICAL: WHEN TO CALL TOOLS\n"
    "NEVER call ANY tool for:\n"
    "- Greetings: 'hi', 'hello', 'hey', 'good morning'\n"
    "- Thanks: 'thank you', 'thanks'\n"
    "- Small talk: 'who are you', 'how are you', 'what can you do'\n"
    "- Vague questions without clear intent\n\n"
    
    "ONLY call tools when the user has CLEAR INTENT:\n"
    "- 'search_shops': User asks for 'shops', 'barbers', 'salons', 'find a place', 'nearby businesses'\n"
    "- 'check_pricing': User asks about 'pricing', 'plans', 'subscription', 'how much does ZeroQwait cost'\n"
    "- 'see_features': User asks 'what features', 'what can ZeroQwait do'\n"
    "- 'see_faq': User asks for 'FAQ', 'help', 'support'\n\n"
    
    "## CONVERSATIONAL WORKFLOW\n"
    "1. For greetings or vague messages, respond warmly and ASK what they're looking for:\n"
    "   'Hello! Would you like me to help you find nearby shops, explore our pricing, or learn about features?'\n"
    "2. Wait for the user to specify their intent before calling any tool.\n"
    "3. Only call tools when the user gives EXPLICIT direction.\n\n"
    
    "## CONTEXT AWARENESS\n"
    "1. [UI CONTEXT] describes what the user sees. Use it to answer 'this'/'that' references.\n"
    "2. User's query ALWAYS overrides context. If they ask for shops while viewing pricing, search shops.\n"
    "3. After calling 'search_shops', shops appear as cards. Don't list names/addresses in text.\n\n"
    
    "## EXAMPLES\n"
    "User: 'hi'\n"
    "ZeroQ: 'Hello! I'm ZeroQ, your ZeroQwait assistant. Are you looking to find nearby shops, explore our pricing, or learn about our features?' [NO TOOLS]\n\n"
    "User: 'show me shops'\n"
    "ZeroQ: (call search_shops) 'I found some shops near you!'\n\n"
    "User: 'thanks'\n"
    "ZeroQ: 'You're welcome! Is there anything else I can help you with?' [NO TOOLS]"
)


master_pydantic_agent = Agent(
    model,
    deps_type=MasterAgentDeps,
    system_prompt=MASTER_SYSTEM_PROMPT,
    retries=10,
    model_settings={'temperature': 0.1}
)

@master_pydantic_agent.tool
async def search_shops(
    ctx: RunContext[MasterAgentDeps], 
    category: Optional[str] = Field(default=None, description="Category: barber, salon, nail_spa, auto_repair, clinic, restaurant, vet. Leave empty for all."),
    city: Optional[str] = Field(default=None, description="City name (e.g. Toronto)."),
    query: Optional[str] = Field(default=None, description="Keywords (e.g. 'fade').")
) -> str:
    """Search for local businesses. Use ONLY if the user is looking for a specific place to visit."""
    clean_query = query
    if clean_query:
        for noise in ["find", "search", "shops", "shop", "me", "a", "near", "in", "the", "for", "any", "around", "nearby"]:
            clean_query = clean_query.replace(noise, "")
        clean_query = clean_query.strip()
    
    result = db_interface.search_shops(
        query=clean_query if clean_query else None,
        shop_type=category,
        city=city,
        latitude=ctx.deps.latitude,
        longitude=ctx.deps.longitude,
        limit=10
    )
    ctx.deps.actions.append({"tool": "search_shops", "result": result})
    return f"Successfully found {len(result)} shops. They are already visible to the user as cards. DO NOT list details."

@master_pydantic_agent.tool
async def check_pricing(ctx: RunContext[MasterAgentDeps]) -> str:
    """View ZeroQwait subscription plans ($0 Free, $29 Premium, Enterprise)."""
    ctx.deps.actions.append({"tool": "navigate_to_page_section", "result": {"target": "pricing"}})
    return "Opened pricing menu."

@master_pydantic_agent.tool
async def see_features(ctx: RunContext[MasterAgentDeps]) -> str:
    """View ZeroQwait features."""
    ctx.deps.actions.append({"tool": "navigate_to_page_section", "result": {"target": "features"}})
    return "Opened features page."

@master_pydantic_agent.tool
async def see_faq(ctx: RunContext[MasterAgentDeps]) -> str:
    """View FAQ."""
    ctx.deps.actions.append({"tool": "navigate_to_page_section", "result": {"target": "faq"}})
    return "Opened FAQ."


# --- FRONT DESK AGENT (Shop-Specific Assistant) ---

front_desk_pydantic_agent = Agent(
    model,
    deps_type=FrontDeskDeps,
    retries=2
)

@front_desk_pydantic_agent.system_prompt
def get_front_desk_prompt(ctx: RunContext[FrontDeskDeps]) -> str:
    return f"""You are the Intelligent Front Desk Agent for '{ctx.deps.shop_name}'. Your name is '{ctx.deps.ai_agent_name}'.
Manage the queue efficiently while providing a friendly, professional experience.
1. Never output raw JSON.
2. If you lack a NAME or PHONE for enrollment, ASK for them politely.
3. Check 'check_returning_customer' if a user provides their phone number."""

@front_desk_pydantic_agent.tool
async def get_shop_status(ctx: RunContext[FrontDeskDeps]) -> Dict[str, Any]:
    """Get current queue lengths and occupancy."""
    try:
        queues = db_interface.get_queues({"shop_id": ctx.deps.shop_id, "is_active": True})
        status = []
        for q in queues:
            items = db_interface.get_queue_items({"queue_id": q["id"]})
            active = [i for i in items if i["status"] in ["waiting", "being_served"]]
            status.append({"name": q["name"], "waiting": len([i for i in active if i["status"] == "waiting"])})
        return {"queues": status}
    except Exception as e:
        return {"error": str(e)}

@front_desk_pydantic_agent.tool
async def check_returning_customer(ctx: RunContext[FrontDeskDeps], phone: str) -> Dict[str, Any]:
    """Check if a customer has visited before."""
    customer = db_interface.get_shop_customer_by_phone(ctx.deps.shop_id, phone)
    if customer:
        return {"is_returning": True, "name": customer["name"]}
    return {"is_returning": False}

@front_desk_pydantic_agent.tool
async def enroll_customer(ctx: RunContext[FrontDeskDeps], name: str, phone: str) -> str:
    """Add a customer to the queue. Requires name and phone."""
    # Logic for enrollment (simplified for this migration)
    # In a real tool, we might call external router logic
    return f"Successfully added {name} to the queue."


# --- Wrapper Classes for FastAPI ---

class MasterAgent:
    def __init__(self):
        self.agent = master_pydantic_agent

    async def chat(self, session_id: str, user_msg: str, latitude: float = None, longitude: float = None, history: List[Dict[str, str]] = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        actions = []
        deps = MasterAgentDeps(session_id=session_id, latitude=latitude, longitude=longitude, context=context, actions=actions)
        
        # UI Context Injection
        ui_ctx_str = ""
        if context:
            v = context.get("active_view")
            if v: ui_ctx_str = f"[UI CONTEXT: User is viewing {v}]"
        
        full_msg = f"{ui_ctx_str}\n{user_msg}" if ui_ctx_str else user_msg
        
        try:
            result = await self.agent.run(full_msg, deps=deps)
            final_text = result.output
            
            # Privacy: Add to history
            db_interface.add_message_to_history(session_id, "user", full_msg)
            db_interface.add_message_to_history(session_id, "assistant", final_text)

            return {"response": final_text, "actions": actions, "agent_name": "ZeroQ (PydanticAI)"}
        except Exception as e:
            logger.error(f"PydanticAI Master Error: {e}")
            return {
                "error": str(e), 
                "response": "I'm having a technical glitch. Let's try again.",
                "actions": []
            }

class FrontDeskAgent:
    def __init__(self, shop_id: int, shop_name: str, ai_agent_name: Optional[str] = None):
        self.shop_id = shop_id
        self.shop_name = shop_name
        self.ai_agent_name = ai_agent_name or shop_name
        self.agent = front_desk_pydantic_agent

    async def chat(self, user_message: str, history: List[Dict[str, str]] = []) -> Dict[str, Any]:
        # Using a dummy session_id for now if not provided
        actions = []
        deps = FrontDeskDeps(shop_id=self.shop_id, shop_name=self.shop_name, ai_agent_name=self.ai_agent_name, session_id="shop_session", actions=actions)
        
        try:
            result = await self.agent.run(user_message, deps=deps)
            return {"response": result.output, "actions": actions, "agent_name": self.ai_agent_name}
        except Exception as e:
             return {"response": "Glitch in the front desk logic.", "actions": []}
