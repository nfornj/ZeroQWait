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

def enroll_customer(shop_id: int, name: str, phone: str, service_id: Optional[int] = None, notes: Optional[str] = None) -> Dict[str, Any]:
    """Enroll a customer into the most efficient queue or a specific service."""
    try:
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
    "find_best_queue": find_best_queue
}

TOOL_DEFINITIONS = [
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

import httpx

class FrontDeskAgent:
    def __init__(self, shop_id: int, shop_name: str):
        self.shop_id = shop_id
        self.shop_name = shop_name
        self.api_key = os.getenv("GROQ_API_KEY") # Switch to Groq for OS LLM
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    def get_system_prompt(self):
        return f"""You are the Intelligent Front Desk Agent for '{self.shop_name}'.
Goal: Manage the queue efficiently and provide world-class service.

Key rules:
- Be concise. Speak like a professional receptionist.
- Use tools to help customers.
- If name/phone is missing, ask for them.
- Proactively suggest shorter queues if a bottleneck is detected.

Tools available:
- get_shop_status: Check wait times.
- get_services: List prices and services.
- find_best_queue: Identify the best option for the customer.
- enroll_customer: Join the queue (Requires Name and Phone).

Current Shop ID: {self.shop_id}
"""

    async def chat(self, user_message: str, history: List[Dict[str, str]] = []) -> Dict[str, Any]:
        """
        Agentic chat loop using Groq Llama 3.
        """
        if not self.api_key:
            return self._mock_chat(user_message, history)

        messages = [
            {"role": "system", "content": self.get_system_prompt()}
        ]
        # Append limited history
        messages.extend(history[-4:])
        messages.append({"role": "user", "content": user_message})

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.base_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": "llama3-70b-8192", 
                        "messages": messages,
                        "tools": [{"type": "function", "function": t} for t in TOOL_DEFINITIONS],
                        "tool_choice": "auto"
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"Groq API Error: {response.text}")
                    return self._mock_chat(user_message, history)

                resp_data = response.json()
                message = resp_data["choices"][0]["message"]
                
                actions_taken = []
                
                if message.get("tool_calls"):
                    for tc in message["tool_calls"]:
                        func = tc["function"]
                        name = func["name"]
                        args = json.loads(func["arguments"])
                        args["shop_id"] = self.shop_id
                        
                        if name in AVAILABLE_TOOLS:
                            result = AVAILABLE_TOOLS[name](**args)
                            actions_taken.append({"tool": name, "result": result})
                    
                    if any(a["tool"] == "enroll_customer" for a in actions_taken):
                        text = "I've successfully added you to the queue! You should receive a confirmation shortly."
                    elif any(a["tool"] == "find_best_queue" for a in actions_taken):
                        best = next(a for a in actions_taken if a["tool"] == "find_best_queue")["result"]
                        text = f"I've checked the wait times. The best option is '{best['best_queue']['name']}'."
                    else:
                        text = message.get("content") or "Processing your request..."
                else:
                    text = message.get("content")
                
                return {
                    "response": text,
                    "actions": actions_taken,
                    "shop_name": self.shop_name
                }
        except Exception as e:
            logger.error(f"Chat execution failed: {e}")
            return self._mock_chat(user_message, history)

    def _mock_chat(self, user_message, history):
        msg = user_message.lower()
        actions_taken = []
        text_response = "I'm ready to help. Say Join Queue or ask about wait times."
        
        if "join" in msg or "queue" in msg:
             text_response = "I'd love to help you join. What is your name and phone number?"
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
