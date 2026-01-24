import os
import json
import logging
from typing import List, Optional, Dict, Any
from db_interface import db_interface
from datetime import datetime

logger = logging.getLogger(__name__)

# --- Agent Tools (The "Hands" of the Agent) ---

def get_shop_status(shop_id: int) -> Dict[str, Any]:
    """Get the current load and status of all queues in a shop."""
    try:
        queues = db_interface.get_queues({"shop_id": shop_id, "is_active": True})
        status = []
        for q in queues:
            items = db_interface.get_queue_items({"queue_id": q["id"]})
            active_items = [i for i in items if i["status"] in ["waiting", "being_served"]]
            status.append({
                "queue_id": q["id"],
                "name": q["name"],
                "waiting_count": len([i for i in active_items if i["status"] == "waiting"]),
                "currently_serving": len([i for i in active_items if i["status"] == "being_served"])
            })
        return {"shop_id": shop_id, "queues": status}
    except Exception as e:
        return {"error": str(e)}

        logger.error(f"Enrollment error: {e}")
        return {"error": str(e)}

def check_returning_customer(shop_id: int, phone: str) -> Dict[str, Any]:
    """Check if a customer has visited this shop before using their phone number."""
    try:
        customer = db_interface.get_shop_customer_by_phone(shop_id, phone)
        if customer:
            return {
                "is_returning": True,
                "name": customer["name"],
                "visit_count": customer["visit_count"],
                "last_visit": customer["last_visit"]
            }
        return {"is_returning": False}
    except Exception as e:
        return {"error": str(e)}

def enroll_customer(shop_id: int, name: str, phone: str, service_id: Optional[int] = None, notes: Optional[str] = None) -> Dict[str, Any]:
    """Enroll a customer into the most efficient queue or a specific service. REQUIRES NAME AND PHONE."""
    if not name or not phone:
        return {"error": "Missing required information. I need both a NAME and a PHONE NUMBER to sign you up."}
        
    try:
        # Business Logic: Update/Create ShopCustomer record
        db_interface.upsert_shop_customer(shop_id, {"name": name, "phone": phone})
        
        # Business Logic: Find the queue with the shortest wait
        queues = db_interface.get_queues({"shop_id": shop_id, "is_active": True})
        if not queues:
            return {"error": "No active queues found for this shop."}
        
        # Pick queue with fewest waiting people
        queue_stats = []
        for q in queues:
            items = db_interface.get_queue_items({"queue_id": q["id"]})
            waiting = len([i for i in items if i["status"] == "waiting"])
            queue_stats.append((waiting, q))
        
        queue_stats.sort(key=lambda x: x[0])
        best_queue = queue_stats[0][1]

        # Prepare join data
        from routers.queues import join_queue
        from schemas import QueueItemCreate
        
        item_data = QueueItemCreate(
            customer_name=name,
            customer_phone=phone,
            service_id=service_id,
            notes=notes or "Enrolled by AI Front Desk"
        )
        
        # We call the logic from the router directly to maintain consistency
        # Note: join_queue in routers/queues.py handles position calculation etc.
        from routers.queues import join_queue
        result = join_queue(shop_id, item_data)
        
        return {
            "success": True, 
            "message": f"Successfully added {name} to {best_queue['name']}",
            "item": result
        }
    except Exception as e:
        logger.error(f"Enrollment error: {e}")
        return {"error": str(e)}

def get_services(shop_id: int) -> List[Dict[str, Any]]:
    """List available services for the shop."""
    try:
        services = db_interface.get_shop_services(shop_id, include_inactive=False)
        return services
    except Exception:
        return []

def find_best_queue(shop_id: int) -> Dict[str, Any]:
    """Analyze all queues and find the one with the shortest expected wait time."""
    try:
        queues = db_interface.get_queues({"shop_id": shop_id, "is_active": True})
        if not queues:
            return {"error": "No active queues"}
        
        shop = db_interface.get_shop_by_id(shop_id)
        avg_time = shop.get("average_service_time", 15)
        
        stats = []
        for q in queues:
            items = db_interface.get_queue_items({"queue_id": q["id"]})
            waiting = [i for i in items if i["status"] == "waiting"]
            wait_time = len(waiting) * avg_time
            stats.append({
                "queue_id": q["id"],
                "name": q["name"],
                "wait_minutes": wait_time,
                "people_waiting": len(waiting)
            })
        
        # Sort by wait time
        stats.sort(key=lambda x: x["wait_minutes"])
        best = stats[0]
        
        # Detect Bottleneck
        bottleneck = None
        if len(stats) > 1:
            diff = stats[-1]["wait_minutes"] - stats[0]["wait_minutes"]
            if diff >= avg_time * 2: # Significant difference
                bottleneck = {
                    "slowest": stats[-1]["name"],
                    "fastest": stats[0]["name"],
                    "saving": diff
                }

        return {
            "best_queue": best,
            "all_stats": stats,
            "bottleneck_detected": bottleneck
        }
    except Exception as e:
        return {"error": str(e)}

# --- Agent Brain (The LLM Interface) ---

# Mapping of function names to actual Python functions for the LLM to call
AVAILABLE_TOOLS = {
    "get_shop_status": get_shop_status,
    "enroll_customer": enroll_customer,
    "get_services": get_services,
    "find_best_queue": find_best_queue,
    "check_returning_customer": check_returning_customer
}

TOOL_DEFINITIONS = [
    {
        "name": "check_returning_customer",
        "description": "Check if a customer has visited this shop before. Use this if they mention they've been here or if you have their phone number.",
        "parameters": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "The customer's phone number."}
            },
            "required": ["phone"]
        }
    },
    {
        "name": "get_shop_status",
        "description": "Get current queue lengths and occupancy for the shop.",
        "parameters": {
            "type": "object",
            "properties": {
                "shop_id": {"type": "integer"}
            },
            "required": ["shop_id"]
        }
    },
    {
        "name": "enroll_customer",
        "description": "Add a new customer to the queue. Should be called when name and phone are known.",
        "parameters": {
            "type": "object",
            "properties": {
                "shop_id": {"type": "integer"},
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "service_id": {"type": "integer", "description": "Optional service ID"},
                "notes": {"type": "string"}
            },
            "required": ["shop_id", "name", "phone"]
        }
    },
    {
        "name": "get_services",
        "description": "List all services offered by the shop with prices.",
        "parameters": {
            "type": "object",
            "properties": {
                "shop_id": {"type": "integer"}
            },
            "required": ["shop_id"]
        }
    }
]

# --- Master Agent Settings (Global assistant for Marketing Page) ---

MASTER_TOOL_DEFINITIONS = [
    {
        "name": "search_shops",
        "description": "Search for shops by name, type (e.g., barber, salon, auto), or city. Use this when a user is looking for a place to visit.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term for shop name or general keywords."},
                "shop_type": {"type": "string", "description": "Specific business category (barber, salon, auto_repair, etc)."},
                "city": {"type": "string", "description": "City to search in."}
            }
        }
    },
    {
        "name": "navigate_to_page_section",
        "description": "Smoothly scroll the user to a specific section of the marketing page. Use this when they ask about pricing, features, faq, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "section": {
                    "type": "string", 
                    "enum": ["hero", "features", "pricing", "testimonials", "faq", "highlights"],
                    "description": "The target section to show the user."
                }
            },
            "required": ["section"]
        }
    }
]

MASTER_AVAILABLE_TOOLS = {
    "search_shops": db_interface.search_shops,
    "navigate_to_page_section": lambda section: {"action": "navigate", "target": section}
}

import httpx

class FrontDeskAgent:
    def __init__(self, shop_id: int, shop_name: str, ai_agent_name: Optional[str] = None):
        self.shop_id = shop_id
        self.shop_name = shop_name
        self.ai_agent_name = ai_agent_name or shop_name
        # Internal K3s URL for Ollama
        self.base_url = "http://ollama.llm.svc.cluster.local:11434/api/chat"
        self.model = "llama3.2"

    def get_system_prompt(self):
        return f"""You are the Intelligent Front Desk Agent for '{self.shop_name}'. Your name is '{self.ai_agent_name}'.
Goal: Manage the queue efficiently while providing a friendly, professional experience.

Core Protocol:
1. **Never output raw JSON or code.** Never show strings like "get_services" or "{{'id': 1}}" to the customer. Always use natural sentences.
2. **Dynamic Persona:** Match the user's energy! If they make funny sounds (like "ooh la la") or jokes, be witty and playful back. Use humor but stay professional.
3. **Missing Info:** If you lack a NAME or PHONE for enrollment, ASK for them politely. DO NOT guess or use placeholders.
4. **CRM Awareness:** Always check `check_returning_customer` if a user provides their phone number. If they are returning, welcome them back by name and acknowledge their loyalty.
5. **Conversational Variance:** Acknowledge user non-answers. If they say "maybe later" or "I'm busy", back off gracefully.
6. **Pivot Logic:** Even when being funny, always find a way to offer shop services (Haircuts, Shaves, etc.) organically.

Tooling:
- 'check_returning_customer': Check if customer is a regular.
- 'get_services': See what we offer and prices.
- 'get_shop_status': Check wait times.
- 'enroll_customer': ONLY use this once you have BOTH a NAME and a PHONE NUMBER.

Operational Info:
- Current Shop ID: {self.shop_id}
- Shop Name: {self.shop_name}
- AI Agent Name: {self.ai_agent_name}
"""

    async def chat(self, user_message: str, history: List[Dict[str, str]] = []) -> Dict[str, Any]:
        """
        Agentic chat loop using Local Ollama (Llama 3).
        """
        messages = [
            {"role": "system", "content": self.get_system_prompt()}
        ]
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.base_url,
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "tools": [{"type": "function", "function": t} for t in TOOL_DEFINITIONS]
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"Ollama API Error: {response.text}")
                    return self._mock_chat(user_message, history)

                resp_data = response.json()
                message = resp_data["message"]
                
                actions_taken = []
                
                # If tool calls are present, execute them and do a SECOND pass for a natural response
                if message.get("tool_calls"):
                    # Add agent's tool call to history
                    messages.append(message)
                    
                    for tc in message["tool_calls"]:
                        func = tc["function"]
                        name = func["name"]
                        args = func.get("arguments", {})
                        if isinstance(args, str):
                            args = json.loads(args)
                        
                        args["shop_id"] = self.shop_id
                        
                        if name in AVAILABLE_TOOLS:
                            result = AVAILABLE_TOOLS[name](**args)
                            actions_taken.append({"tool": name, "result": result})
                            
                            # Add tool result to history for the second pass
                            messages.append({
                                "role": "tool",
                                "content": json.dumps(result),
                                "name": name
                            })
                    
                    # --- SECOND PASS ---
                    # Now call the LLM again with the tool results in history
                    response_pass2 = await client.post(
                        self.base_url,
                        json={
                            "model": self.model,
                            "messages": messages,
                            "stream": False
                        }
                    )
                    
                    if response_pass2.status_code == 200:
                        resp_data_pass2 = response_pass2.json()
                        text = resp_data_pass2["message"].get("content", "I've processed your request.")
                    else:
                        text = "I've executed the requested actions, but I'm having trouble phrasing my response. How else can I help?"
                else:
                    text = message.get("content", "I'm not sure how to respond to that.")
                
                # Safety check: Catch any JSON leakage or "tool_call" artifacts
                clean_text = str(text or "").strip()
                
                # Broad match for anything that looks like JSON or a tool call (starts with { or "tool",)
                leakage_detected = False
                if clean_text.startswith("{") or clean_text.startswith("["):
                    leakage_detected = True
                elif '"' in clean_text and "{" in clean_text and (any(t in clean_text for t in AVAILABLE_TOOLS)):
                    leakage_detected = True

                if leakage_detected:
                    logger.warning(f"Raw LLM leakage detected and intercepted: {clean_text}")
                    # Try to find a fallback response from our mock logic or a simple polite brush-off
                    fallback = self._mock_chat(user_message, history)
                    text = fallback["response"]

                return {
                    "response": text,
                    "actions": actions_taken,
                    "shop_name": self.shop_name
                }
        except Exception as e:
            logger.error(f"Local LLM chat failed: {e}")
            return self._mock_chat(user_message, history)

    def _mock_chat(self, user_message, history):
        msg = user_message.lower()
        actions_taken = []
        
        # Playful energy for "funny sounds"
        if any(s in msg for s in ["ooh la la", "haha", "hehe", "lol", "funny", "yay"]):
            text_response = "Ooh la la indeed! You've got that stylish energy! ✨ While we celebrate your vibe, can I help you pick a service like a Haircut or Coloring?"
        else:
            text_response = "I'm ready to help! You can ask about our services, join the queue, or check wait times."
        
        if "join" in msg or "queue" in msg:
             text_response = "I'd love to help you join! What is your name and phone number?"
        elif "status" in msg or "how busy" in msg or "best" in msg or "long" in msg:
             best_data = find_best_queue(self.shop_id)
             if best_data.get("bottleneck_detected"):
                 bn = best_data["bottleneck_detected"]
                 text_response = f"Currently, '{bn['slowest']}' is quite busy. I recommend joining '{bn['fastest']}' instead – it will save you about {bn['saving']} minutes!"
             else:
                 best = best_data["best_queue"]
                 text_response = f"The best option right now is '{best['name']}' with an estimated wait of {best['wait_minutes']} minutes."
             actions_taken.append({"tool": "find_best_queue", "result": best_data})
             
        elif "service" in msg or "price" in msg:
            services = get_services(self.shop_id)
            srv_list = ", ".join([f"{s['name']} (${s['cost']})" for s in services])
            text_response = f"We offer several services, including: {srv_list}."
            actions_taken.append({"tool": "get_services", "result": services})

        return {
            "response": text_response,
            "actions": actions_taken,
            "shop_name": self.shop_name
        }


class MasterAgent(FrontDeskAgent):
    """
    Global ZeroQwait Assistant for the Marketing Page.
    Helps with product info, navigation, and searching shops.
    """
    def __init__(self):
        super().__init__(shop_id=0, shop_name="ZeroQwait")
        self.ai_agent_name = "ZeroQ"

    def get_system_prompt(self):
        return f"""You are 'ZeroQ', the Sovereign AI Architect for ZeroQwait. 
Your goal is to demonstrate our revolutionary AI-powered queue ecosystem.

**The Product: ZeroQwait**
- **Core Value:** We eliminate physical wait lines and replace them with intelligent virtual queues and AI Front Desks.
- **AI Front Desk:** Every shop gets its own persona-driven AI agent (like me, but specialized) to handle customers, explain services, and manage arrivals.
- **Canvas Orb Visuals:** We use high-performance WebGL/Canvas animations to visualize the 'pulse' of the queue.
- **Predictive Analytics:** We use deep learning to predict wait times and identify business bottlenecks.

**Pricing Plans:**
1. **Free ($0/mo):** 1 shop, 50 customers/queue, basic management.
2. **Premium ($29/mo):** 5 shops, 200 customers/queue, dedicated DB, advanced analytics, custom branding. (Recommended)
3. **Enterprise (Contact Us):** Unlimited everything, on-premise options, dedicated SLA.

**Global Tools:**
- `search_shops`: Search our network of 100+ simulated businesses (Barbers, Salons, Auto, Dental). Use this if they ask for a place to visit.
- `navigate_to_page_section`: Scroll to hero, features, pricing, faq, or highlights.

**Guidelines:**
- Be sharp, tech-forward, and impressively helpful.
- When someone asks "what is this?", explain it as a Universal AI Front Desk for all service businesses.
- If they ask about pricing, guide them to the pricing section using `navigate_to_page_section` AND summarize the tiers.
- If they are looking for a shop, use `search_shops` immediately. 
- **CRITICAL:** Always use the `search_shops` tool if the user asks for a place, a category of business, or recommendations. Never just list shops in text format; always provide the structured data via the tool so the UI can display them correctly.
"""

    async def chat(self, user_message: str, history: List[Dict[str, str]] = []) -> Dict[str, Any]:
        """Override chat to use master tools and prompt."""
        messages = [
            {"role": "system", "content": self.get_system_prompt()}
        ]
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.base_url,
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "tools": [{"type": "function", "function": t} for t in MASTER_TOOL_DEFINITIONS]
                    }
                )
                
                if response.status_code != 200:
                    return {"response": "I'm having a bit of trouble connecting to my brain. How else can I assist?", "actions": []}

                resp_data = response.json()
                message = resp_data["message"]
                actions_taken = []
                
                if message.get("tool_calls"):
                    messages.append(message)
                    for tc in message["tool_calls"]:
                        func = tc["function"]
                        name = func["name"]
                        args = func.get("arguments", {})
                        if isinstance(args, str): args = json.loads(args)
                        
                        if name in MASTER_AVAILABLE_TOOLS:
                            result = MASTER_AVAILABLE_TOOLS[name](**args)
                            actions_taken.append({"tool": name, "result": result, "args": args})
                            messages.append({"role": "tool", "content": json.dumps(result), "name": name})
                    
                    # Pass 2
                    response_pass2 = await client.post(
                        self.base_url,
                        json={"model": self.model, "messages": messages, "stream": False}
                    )
                    text = response_pass2.json()["message"].get("content", "I've processed your request.")
                else:
                    text = message.get("content", "I'm here to help!")

                return {
                    "response": text,
                    "actions": actions_taken,
                    "agent_name": self.ai_agent_name
                }
        except Exception:
            return {"response": "I'm currently recalibrating focus. Ask me about our features or pricing!", "actions": []}
