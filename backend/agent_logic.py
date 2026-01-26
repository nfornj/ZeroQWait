import os
import json
import logging
from typing import List, Optional, Dict, Any
from db_interface import db_interface
from datetime import datetime
import httpx
import asyncio

logger = logging.getLogger(__name__)

# --- Tool Definitions (Llama 3.2 Schema) ---
MASTER_AGENT_TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'search_shops',
            'description': 'Search for local businesses. You have access to the user\'s location, so "near me" queries are supported automatically via the city/location arguments.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'category': {
                        'type': 'string', 
                        'description': 'Type of shop. Supported: barber, salon, nail_spa, auto_repair, clinic, restaurant, vet. Map user input to one of these.'
                    },
                    'city': {
                        'type': 'string', 
                        'description': 'City name to filter results (e.g. Toronto, Oshawa).'
                    },
                    'query': {
                        'type': 'string', 
                        'description': 'Specific search keywords (e.g. "fade", "oil change").'
                    }
                },
                'required': ['category'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'check_pricing',
            'description': 'Get information about ZeroQwait subscription pricing tiers.',
            'parameters': {
                'type': 'object',
                'properties': {},
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'see_features',
            'description': 'Get information about features offered by ZeroQwait.',
            'parameters': {
                'type': 'object',
                'properties': {},
                'required': [],
            },
        },
    }
]

# --- Native Tool-Calling Agent ---

class ToolCallingAgent:
    """
    Orchestrates the ReAct loop using Llama 3.2's native tool-calling capabilities.
    """
    def __init__(self, model: str = "llama3.2", base_url: str = None):
        self.model = model
        # Use env var or default to internal K8s service for prod, localhost for local
        self.base_url = base_url or os.getenv("OLLAMA_URL", "http://ollama.llm.svc.cluster.local:11434/v1")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def chat(self, session_id: str, user_msg: str, latitude: float = None, longitude: float = None) -> Dict[str, Any]:
        # 1. Load History
        history_records = db_interface.get_conversation_history(session_id, limit=10)
        messages = []
        
        # Add a strict system prompt for tool calling
        system_prompt = (
            "You are ZeroQ, the AI Assistant for ZeroQwait. "
            "Your goal is to help users find shops and manage their visits. "
            "CONVERSATION RULES:\n"
            "1. ALWAYS call the 'search_shops' tool if the user is looking for a place, "
            "uses terms like 'near me', 'find', or mentions a shop category (barber, salon, etc.). "
            "DO NOT just talk about finding shops; actually use the tool.\n"
            "2. Results from 'search_shops' appear automatically as cards on the left. "
            "DO NOT list them in text. Just confirm they are there.\n"
            "3. If the user says 'yes', 'sure', or 'tell me more' after you found shops, "
            "DO NOT call 'search_shops' again. Guide them to use the cards.\n"
            "4. NEVER write raw JSON or technical strings like 'search_shops' in your output.\n"
            "5. If you call a tool, respond with a very brief confirmation (e.g., 'Checking that for you...')."
        )
        messages.append({"role": "system", "content": system_prompt})
        
        for h in history_records:
            msg = {"role": h["role"], "content": h["content"]}
            if h.get("tool_call_id"):
                msg["tool_call_id"] = h["tool_call_id"]
            if h.get("name"): # For legacy or tool name support
                msg["name"] = h["name"]
            
            # Restore tool_calls from serialized content
            if h["role"] == "assistant" and h["content"].startswith("[TC]"):
                try:
                    msg["tool_calls"] = json.loads(h["content"][4:])
                    msg["content"] = None # Standard OpenAI format: content is null when tool_calls present
                except:
                    pass
            messages.append(msg)
        
        # Add current user message with location context if available
        context_msg = user_msg
        if latitude and longitude:
            context_msg = f"[User Location: Lat {latitude}, Long {longitude}] {user_msg}"
        
        messages.append({"role": "user", "content": context_msg})
        db_interface.add_message_to_history(session_id, "user", context_msg)

        # 2. ReAct Loop
        # We allow up to 3 turns to prevent infinite loops
        final_response_text = ""
        actions_taken = []
        
        for _ in range(3):
            try:
                # Call LLM with Tools
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "tools": MASTER_AGENT_TOOLS,
                    "stream": False
                }
                
                response = await self.client.post(f"{self.base_url}/chat/completions", json=payload)
                
                if response.status_code != 200:
                    logger.warning(f"LLM Error {response.status_code}: {response.text}")
                    # Fallback to rule-based if LLM fails cleanly
                    return await self._fallback_rule_based(user_msg, latitude, longitude)

                resp_data = response.json()
                choice = resp_data["choices"][0]
                message = choice["message"]
                
                # [ULTRA-ROBUST INTERCEPTOR]
                # Catch malformed/fuzzy tool calls from Llama 3.2
                content_str = message.get("content", "")
                if not message.get("tool_calls") and content_str:
                    try:
                        import re
                        import ast
                        
                        # 1. Check for known tool names anywhere in the string
                        potential_tool_found = None
                        for tool in MASTER_AGENT_TOOLS:
                            t_name = tool["function"]["name"]
                            if t_name in content_str:
                                potential_tool_found = t_name
                                break
                        
                        if potential_tool_found:
                            # 2. Extract anything that looks like a JSON-ish block { ... }
                            json_match = re.search(r"(\{.*\})", content_str, re.DOTALL)
                            if json_match:
                                raw_chunk = json_match.group(1).strip()
                                
                                # 3. CLEANING: Repair common Llama3 hallucinations
                                # Fix: "parameters"."category" -> "parameters":{"category"
                                # Fix: .category: -> "category":
                                cleaned_chunk = raw_chunk.replace('"."', '":{"').replace('".', '":')
                                cleaned_chunk = re.sub(r'(["\w])\.(\w+)', r'\1":"\2"', cleaned_chunk)
                                
                                data = None
                                try:
                                    data = json.loads(cleaned_chunk)
                                except:
                                    try:
                                        # Use AST for single quotes and Python-ish dicts
                                        data = ast.literal_eval(cleaned_chunk)
                                    except:
                                        # 4. BRUTE FORCE: If still failing, extract key-values via regex
                                        logger.info(f"Brute-forcing parameter extraction for {potential_tool_found}")
                                        extracted_args = {}
                                        for key in ["category", "city", "query", "section"]:
                                            val_match = re.search(rf'"{key}"\s*[:=]\s*(?:"([^"]+)"|([\w]+)|null)', cleaned_chunk)
                                            if val_match:
                                                extracted_args[key] = val_match.group(1) or val_match.group(2)
                                                if extracted_args[key] == "null": extracted_args[key] = None
                                        
                                        if extracted_args or potential_tool_found:
                                            data = {"name": potential_tool_found, "arguments": extracted_args}

                                if data and isinstance(data, dict):
                                    func_name = data.get("name") or data.get("function", {}).get("name") or potential_tool_found
                                    args = data.get("arguments") or data.get("parameters") or data.get("function", {}).get("arguments") or data
                                    
                                    # Filter out names from args if it's the top level object
                                    if isinstance(args, dict) and "name" in args and func_name == args["name"]:
                                        args = {k: v for k, v in args.items() if k not in ["name", "function"]}

                                    if func_name and (args is not None):
                                        logger.info(f"Successfully Intercepted & Repaired Tool Call: {func_name}")
                                        message["tool_calls"] = [{
                                            "id": f"intercept_{datetime.now().strftime('%f')}",
                                            "type": "function",
                                            "function": {
                                                "name": func_name,
                                                "arguments": json.dumps(args) if isinstance(args, dict) else str(args)
                                            }
                                        }]
                                        # SILENCE the raw output in UI
                                        message["content"] = "Checking that for you..."
                    except Exception as e:
                        logger.error(f"Interceptor Critical Failure: {e}")

                # Check for tool calls (Native or Intercepted)
                if message.get("tool_calls"):
                    # Add assistant's "thinking" step to history and DB
                    messages.append(message)
                    db_interface.add_message_to_history(
                        session_id, 
                        "assistant", 
                        "[TC]" + json.dumps(message.get("tool_calls"))
                    )
                    
                    tool_calls = message["tool_calls"]
                    
                    for tc in tool_calls:
                        func_name = tc["function"]["name"]
                        args = json.loads(tc["function"]["arguments"])
                        
                        logger.info(f"Executing Tool: {func_name} with {args}")
                        
                        # EXECUTE TOOL
                        result = None
                        if func_name == "search_shops":
                            # Pre-processing: Clean query of noise to help fuzzy search
                            raw_query = args.get("query", "")
                            clean_query = raw_query
                            if clean_query:
                                 for noise in ["find", "search", "shops", "shop", "me", "a", "near", "in", "the", "for", "any", "around", "with", "can", "you", "please", "to", "at", "show", "some", "nearby", "on", "zeroqwait", "could", "would", "want", "looking"]:
                                     clean_query = clean_query.replace(noise, "")
                                 clean_query = clean_query.strip()
                            
                            # City Hallucination Fix: If LLM guess Toronto but we have no city in user msg, prioritze Lat/Long
                            final_city = args.get("city")
                            if final_city == "Toronto" and "toronto" not in user_msg.lower():
                                final_city = None # Be flexible
                            
                            final_query = clean_query if clean_query else None
                            
                            result = db_interface.search_shops(
                                query=final_query,
                                shop_type=args.get("category"),
                                city=final_city,
                                latitude=latitude,
                                longitude=longitude,
                                limit=10
                            )
                            logger.info(f"Search Shops Result: Found {len(result)} items")
                            actions_taken.append({"tool": "search_shops", "result": result})
                            
                        elif func_name == "check_pricing":
                            result = "Free Tier: $0/mo. Premium: $29/mo. Enterprise: Contact us."
                            actions_taken.append({"tool": "navigate_to_page_section", "result": {"target": "pricing"}})
                            
                        elif func_name == "see_features":
                            result = "AI Front Desk, Queue Management, Analytics, Customer CRM."
                            actions_taken.append({"tool": "navigate_to_page_section", "result": {"target": "features"}})
                        
                        # Feed result back to LLM
                        # [SANITIZATION] Summarize for the brain, but keep full data for the frontend
                        content_for_llm = json.dumps(result)
                        
                        if func_name == "search_shops" and isinstance(result, list):
                            content_for_llm = f"Successfully found {len(result)} shops. They are already displayed to the user as cards. DO NOT list them in your response. Just say something like 'I found some shops nearby' and ask if they like any of them."
                        
                        tool_msg = {
                            "role": "tool",
                            "content": content_for_llm,
                            "tool_call_id": tc["id"],
                            "name": func_name
                        }
                        messages.append(tool_msg)
                        db_interface.add_message_to_history(
                            session_id,
                            "tool",
                            content_for_llm,
                            tool_call_id=tc["id"]
                        )
                
                else:
                    # Final Answer
                    final_response_text = message["content"]
                    break
                    
            except Exception as e:
                logger.error(f"ReAct Loop Error: {e}")
                return await self._fallback_rule_based(user_msg, latitude, longitude)
        
        # 3. Save Assistant Response & Return
        if not final_response_text:
            final_response_text = "I processed your request."
            
        db_interface.add_message_to_history(session_id, "assistant", final_response_text)
        
        logger.info(f"Final response for {session_id}: {final_response_text[:50]}... with {len(actions_taken)} actions")
        
        return {
            "response": final_response_text,
            "actions": actions_taken,
            "agent_name": "ZeroQ (Llama)"
        }

    async def _fallback_rule_based(self, user_msg: str, latitude, longitude):
        """Original robust fallback for when LLM is down."""
        logger.info("Falling back to rule-based logic.")
        # Reuse previous logic pattern
        msg = user_msg.lower()
        clean_query = msg
        shop_type = None
        
        # Quick Keyword Logic
        if any(x in msg for x in ["hair", "cut", "barber"]): shop_type = "barber"
        elif any(x in msg for x in ["auto", "car", "mechanic"]): shop_type = "auto_repair"
        elif any(x in msg for x in ["nail", "manicure", "pedicure"]): shop_type = "nail_spa"
        elif any(x in msg for x in ["food", "restaurant", "eat"]): shop_type = "restaurant"
        elif any(x in msg for x in ["vet", "pet", "dog", "cat"]): shop_type = "vet"
        elif any(x in msg for x in ["clinic", "doctor", "health"]): shop_type = "clinic"
        elif any(x in msg for x in ["salon", "style", "color"]): shop_type = "salon"
        
        # Clean query logic
        for noise in ["find", "search", "shops", "shop", "me", "a", "near", "in", "the", "for", "any", "around", "with", "can", "you", "please", "to", "at", "show", "some", "nearby", "on", "zeroqwait", "could", "would", "want", "looking"]:
            clean_query = clean_query.replace(noise, "")
            
        final_query = clean_query.strip() or None
        logger.info(f"Fallback Search Params: query='{final_query}', shop_type='{shop_type}', lat={latitude}, long={longitude}")
        
        shops = db_interface.search_shops(query=final_query, shop_type=shop_type, limit=5, latitude=latitude, longitude=longitude)
        
        response_text = "I'm having trouble connecting to my brain, but here are some search results." if shops else "I'm having trouble connecting right now."
        if shops:
             response_text = f"I found {len(shops)} shops nearby (Offline Mode)."
             
        return {
            "response": response_text,
            "actions": [{"tool": "search_shops", "result": shops}] if shops else [],
            "agent_name": "ZeroQ (Fallback)"
        }


# --- Agent Tools (The "Hands" of the Agent) ---
# ... (Keep existing tool functions: get_shop_status, enroll_customer, etc.) ...
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
        return [{"id": s["id"], "name": s["name"], "cost": s["cost"]} for s in services]
    except Exception as e:
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

# --- Shared Agent Utilities ---

def sanitize_history(history: List[Dict[str, str]], limit: int = 10) -> List[Dict[str, str]]:
    """Clean history of any raw technical data or long JSON blobs."""
    clean_history = []
    for msg in history[-limit:]:
        content = msg.get("content", "")
        # If it looks like technical data or code, summarize it.
        if content.startswith("{") or content.startswith("[") or "import " in content or "def " in content:
            # Keep the role but sanitize the content
            if msg.get("role") == "tool":
                role_label = f"Technical result for {msg.get('name', 'tool')}"
            else:
                role_label = "Technical data message"
            clean_history.append({"role": msg["role"], "content": f"--- {role_label}: Omitted for brevity ---"})
        else:
            clean_history.append(msg)
    return clean_history

def detect_leakage(text: str) -> bool:
    """Check if the text contains technical leakage (code, JSON, tool names)."""
    clean_text = str(text or "").strip()
    if not clean_text:
        return False
        
    # JSON or block markers
    if clean_text.startswith("{") or clean_text.startswith("["):
        return True
    
    # Specific keywords that indicate internal processing
    leakage_keywords = [
        "import ", "def ", "python", "json", "dictionary", "script", 
        "tool_call", "tool_result", "search_shops", "get_services",
        "find_best_queue", "enroll_customer", "navigate_to_page_section"
    ]
    if any(x in clean_text.lower() for x in leakage_keywords):
        return True
        
    return False

def get_fallback_persona_response(agent_name: str) -> str:
    """Universal fallback response when leakage is detected."""
    if agent_name == "ZeroQ":
        return "I'm here to help you navigate ZeroQwait's features. How else can I assist you in exploring our platform or finding a shop today?"
    return "I'm focused on helping you with your visit today. How else can I assist you with our services or the queue?"


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
        self.shop_name = shop_name
        self.ai_agent_name = ai_agent_name or shop_name
        # Internal K3s URL for Ollama (default) or override via Env
        self.base_url = os.getenv("OLLAMA_URL", "http://ollama.llm.svc.cluster.local:11434/api/chat")
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
        messages.extend(sanitize_history(history))
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
                            
                            # Add tool result (sanitized) to history for the second pass
                            messages.append({
                                "role": "tool",
                                "content": f"Action {name} completed successfully." if isinstance(result, (list, dict)) and len(str(result)) > 200 else json.dumps(result),
                                "name": name
                            })
                    
                    # --- SECOND PASS ---
                    messages.append({"role": "system", "content": f"REMINIDER: You are {self.ai_agent_name}. No technical talk. Respond naturally to the user."})
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
                
                # --- LEAKAGE INTERCEPTOR ---
                if detect_leakage(text):
                    logger.warning(f"FrontDeskAgent leakage intercepted: {text[:100]}...")
                    text = get_fallback_persona_response(self.ai_agent_name)

                return {
                    "response": text,
                    "actions": actions_taken,
                    "shop_name": self.shop_name,
                    "agent_name": self.ai_agent_name
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



class MasterAgent:
    def __init__(self):
        self.ai_agent_name = "ZeroQ"
        self.tool_agent = ToolCallingAgent()

    async def chat(self, user_msg, history=None, latitude=None, longitude=None):
        # Generate or retrieve session ID (Simplified: using a static one for demo or hash of user_msg + time)
        # In a real app, this comes from frontend
        session_id = f"demo_session_{datetime.now().strftime('%Y%m%d')}"
        
        return await self.tool_agent.chat(session_id, user_msg, latitude, longitude)
