"""
Receptionist Sub-Agent - Handles booking, queue, and customer service.

Responsibilities:
- Queue management (list, join, call next, close queue)
- Service discovery and details
- Wait time estimates
- Appointment booking
- Customer notifications

Phase 2: Placeholder implementation using direct db_interface calls
Phase 3: Wire to BookingMCP server

Tools called:
- list_queue(shop_id) → active queue items
- join_queue(shop_id, customer_id, service_name) → position confirmation
- get_wait_time(shop_id, service_name=None) → minutes
- call_next_customer(shop_id) → customer info
- close_queue(shop_id, reason=None) → confirmation
- search_services(shop_id, query=None) → available services

HITL breakpoints:
- close_queue: Requires owner approval (high-impact)
- join_queue: If available slots < 5, may suggest upsell
"""

from typing import Any, Dict
import json as _json
import os
import re

from langchain_core.messages import AIMessage, BaseMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END

from .state import AgentState
from .tools import booking_tools


def classify_entry(state: AgentState) -> dict:
    """No-op node so conditional routing can inspect state safely."""
    return {}


def _latest_user_text(state: AgentState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return ""
    latest = messages[-1]
    return str(latest.content) if isinstance(latest, BaseMessage) else str(latest)


def _ollama_base_url() -> str:
    base_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1").rstrip("/")
    if base_url.endswith("/v1"):
        return base_url[:-3]
    return base_url


def _get_receptionist_writer_llm() -> ChatOllama:
    return ChatOllama(
        model=os.getenv("MODEL_NAME", "gpt-oss:20b"),
        base_url=_ollama_base_url(),
        temperature=0.25,
        top_p=0.9,
    )


def _generate_receptionist_response(
    state: AgentState,
    response_type: str,
    facts: Dict[str, Any],
    *,
    extra_instructions: str = "",
) -> str:
    query = _latest_user_text(state)
    llm = _get_receptionist_writer_llm()
    style_rules = [
        "You are the Receptionist agent for a service business.",
        "Your role is customer-facing operations: queue updates, service guidance, and clear next steps.",
        "Be warm, concise, and practical.",
        "Use only the facts provided in FACTS_JSON. Never invent numbers, names, or queue events.",
        "Do not mention internal systems, JSON, tools, routing, or shop_id unless asked.",
        "No emojis.",
        "Keep replies to short prose; bullets are allowed only when listing services or queue details.",
    ]
    if extra_instructions:
        style_rules.append(extra_instructions)

    prompt = (
        "\n".join(style_rules)
        + f"\n\nRESPONSE_TYPE: {response_type}"
        + f"\nUSER_QUESTION: {_json.dumps(query)}"
        + f"\nFACTS_JSON: {_json.dumps(facts, default=str)}"
        + "\n\nReturn only the owner/customer-facing reply text."
    )

    try:
        response = llm.invoke([{"role": "user", "content": prompt}])
        content = response.content if hasattr(response, "content") else str(response)
        if isinstance(content, list):
            content = " ".join(str(chunk) for chunk in content)
        text = str(content).strip()
        text = re.sub(r"^```(?:text|markdown)?\s*", "", text).rstrip("`").strip()
        if text:
            return text
    except Exception:
        pass

    return "I have the queue and service details, but I couldn't phrase the response cleanly right now."


def receptionist_intent_classifier(state: AgentState) -> str:
    """
    Further classify the receptionist request type.
    
    Returns: "queue_status", "join_queue", "services", "close_queue", "other"
    """
    
    messages = state.get("messages", [])
    if not messages:
        return "other"
    
    latest = messages[-1]
    if isinstance(latest, BaseMessage):
        content = str(latest.content).lower()
    else:
        content = str(latest).lower()
    
    # Simple keyword matching for Phase 2
    if any(word in content for word in ["queue", "wait", "position", "line", "busy"]):
        if "close" in content or "end" in content or "stop" in content:
            return "close_queue"
        return "queue_status"
    elif any(word in content for word in ["join", "register", "add", "book"]):
        return "join_queue"
    elif any(word in content for word in ["service", "what", "offer", "available", "price"]):
        return "services"
    else:
        return "other"


def handle_queue_status(state: AgentState) -> dict:
    """Get current queue status for the shop."""
    
    shop_id = state["tenant_id"]
    result = booking_tools.list_queue(shop_id)
    if result.get("error"):
        response = AIMessage(content=f"I couldn't load the live queue right now: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    metrics = result.get("live_metrics", {})
    response = AIMessage(
        content=_generate_receptionist_response(
            state,
            "queue_status",
            result,
            extra_instructions=(
                "Give a clear live queue update with total in queue, waiting, serving, estimated wait, and next customer when available."
            ),
        )
    )
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result
    }


def handle_join_queue(state: AgentState) -> dict:
    """Process a customer joining the queue."""
    
    shop_id = state["tenant_id"]
    metadata = state.get("metadata") or {}
    customer_name = metadata.get("customer_name") or "Walk-in Customer"
    phone = metadata.get("customer_phone")
    result = booking_tools.join_queue(shop_id, customer_name, phone)
    if result.get("error"):
        response = AIMessage(content=f"I couldn't add the customer to the queue: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=_generate_receptionist_response(
            state,
            "join_queue",
            result,
            extra_instructions=(
                "Confirm queue join with position and estimated wait in the first sentence, then tell the customer what happens next."
            ),
        )
    )
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result
    }


def handle_services_inquiry(state: AgentState) -> dict:
    """List available services and details."""
    
    shop_id = state["tenant_id"]
    latest = state["messages"][-1]
    query = str(latest.content) if isinstance(latest, BaseMessage) else str(latest)
    normalized_query = query.lower()
    broad_catalog_request = any(
        token in normalized_query for token in ["service", "services", "offer", "available", "price", "prices", "what"]
    )
    result = booking_tools.search_services(shop_id, None if broad_catalog_request else query)
    if result.get("error"):
        response = AIMessage(content=f"I couldn't load the service catalog right now: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=_generate_receptionist_response(
            state,
            "services_inquiry",
            result,
            extra_instructions=(
                "If services are available, present a concise helpful list including service name, cost, and duration, and end with a selection prompt."
            ),
        )
    )
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result
    }


def handle_close_queue(state: AgentState) -> dict:
    """
    Close the queue (high-impact action requiring HITL approval).
    
    Sets pending_approval and needs_human_input to trigger approval card.
    """
    
    shop_id = state["tenant_id"]
    
    reason = "Owner requested queue closure"

    # Propose action for HITL approval (actual execution occurs after approval).
    return {
        "messages": list(state["messages"]) + [AIMessage(
            content="I can close the queue for today. Let me request your approval..."
        )],
        "pending_approval": {
            "action": "close_queue",
            "shop_id": shop_id,
            "details": {
                "reason": reason,
                "timestamp": "now",
                "impact": "Customers can no longer join queue"
            }
        },
        "needs_human_input": True,
        "tool_results": None
    }


def handle_other(state: AgentState) -> dict:
    """Generic receptionist response."""
    
    response = AIMessage(
        content=_generate_receptionist_response(
            state,
            "fallback_help",
            {
                "capabilities": [
                    "Queue status and wait times",
                    "Joining the queue",
                    "Service information",
                    "Closing the queue (manager approval required)",
                ]
            },
            extra_instructions="Offer concise receptionist help options and invite the next request.",
        )
    )
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": None
    }


def build_receptionist_graph():
    """
    Build the LangGraph StateGraph for the Receptionist sub-agent.
    
    Flow:
    1. classify_request - determine what receptionist task
    2. route to handler (queue_status, join_queue, services, close_queue, other)
    3. END
    """
    
    graph = StateGraph(AgentState)
    
    # Nodes
    graph.add_node("classify", classify_entry)
    graph.add_node("queue_status", handle_queue_status)
    graph.add_node("join_queue", handle_join_queue)
    graph.add_node("services", handle_services_inquiry)
    graph.add_node("close_queue", handle_close_queue)
    graph.add_node("other", handle_other)
    
    # Edges: classify -> route based on result
    graph.add_conditional_edges(
        "classify",
        lambda state: receptionist_intent_classifier(state),
        {
            "queue_status": "queue_status",
            "join_queue": "join_queue",
            "services": "services",
            "close_queue": "close_queue",
            "other": "other"
        }
    )
    
    # All handlers end
    graph.add_edge("queue_status", END)
    graph.add_edge("join_queue", END)
    graph.add_edge("services", END)
    graph.add_edge("close_queue", END)
    graph.add_edge("other", END)
    
    # Entry point
    graph.set_entry_point("classify")
    
    return graph


def create_receptionist_runnable():
    """Compile the Receptionist graph into an executable runnable."""
    graph = build_receptionist_graph()
    return graph.compile()


__all__ = [
    "build_receptionist_graph",
    "create_receptionist_runnable"
]
