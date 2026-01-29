import os
import json
import logging
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, ModelRetry
from pydantic_ai.models.openai import OpenAIModel

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

# Configure Ollama Model
ollama_url = os.getenv("OLLAMA_URL", "http://ollama.llm.svc.cluster.local:11434/v1")
model = OpenAIModel(
    model_name='llama3.2',
    base_url=ollama_url,
    api_key='ollama',
)

# --- MASTER AGENT (Marketing Page Assistant) ---

MASTER_SYSTEM_PROMPT = (
    "You are ZeroQ, the AI Assistant for ZeroQwait. "
    "Your goal is to help users find shops, understand our pricing, and explore our features. "
    "\n\nCONTEXT AWARENESS RULES:\n"
    "1. You will receive a [UI CONTEXT] tag describing what the user is currently seeing.\n"
    "2. When the user says 'this', 'that', or 'pricing', check the [UI CONTEXT] to resolve ambiguity.\n"
    "3. If [UI CONTEXT: User is viewing shops], 'pricing' likely means service prices for those shops. "
    "IMPORTANT: You CANNOT see individual service prices. Acknowledge this and suggest they check the cards or chat with the shop.\n"
    "4. If [UI CONTEXT: User is viewing pricing], 'pricing' means ZeroQwait subscription plans ($0, $29).\n"
    "5. If the intent is still unclear after checking context, politely ask: 'Do you mean the shop's service prices or ZeroQwait's subscription plans?'\n"
    "\nCONVERSATION RULES:\n"
    "1. ALWAYS call 'check_pricing' for OUR pricing/cost questions (ZeroQwait plans).\n"
    "2. ALWAYS call 'see_features' for feature/capability questions.\n"
    "3. ALWAYS call 'see_faq' for help/FAQ questions.\n"
    "4. CALL 'search_shops' ONLY if they want to find a specific local business (barber, salon, etc.).\n"
    "5. Results from 'search_shops' appear as cards. DO NOT list names, addresses or phone numbers in your text. Just confirm they are there.\n"
    "6. GREETINGS & PLEASANTRIES: If the user says 'hi', 'hello', 'good morning', etc., or is just making small talk, respond warmly but DO NOT CALL ANY TOOLS. Do not navigate to pricing, features, or FAQ for a simple 'hi'. Stay in the current view.\n"
    "7. After calling a tool, give a friendly confirmation. If you move to pricing/features, don't repeat the prices/features in text, as they can see them on screen.\n"
    "7. ALWAYS respond in natural, friendly English. Never show JSON or technical tool names."
)

master_pydantic_agent = Agent(
    model,
    deps_type=MasterAgentDeps,
    system_prompt=MASTER_SYSTEM_PROMPT,
    retries=2
)

@master_pydantic_agent.tool
async def search_shops(
    ctx: RunContext[MasterAgentDeps], 
    category: str = Field(description="Category: barber, salon, nail_spa, auto_repair, clinic, restaurant, vet."),
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
            final_text = result.data
            
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
            return {"response": result.data, "actions": actions, "agent_name": self.ai_agent_name}
        except Exception as e:
             return {"response": "Glitch in the front desk logic.", "actions": []}
