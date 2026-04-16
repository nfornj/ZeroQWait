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
from .tools import appointment_tools


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
        model=os.getenv("MODEL_NAME", "qwen3:14b-q4_K_M"),
        base_url=_ollama_base_url(),
        temperature=0.25,
        top_p=0.9,
        num_gpu=-1,
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

    response = llm.invoke([{"role": "user", "content": prompt}])
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = " ".join(str(chunk) for chunk in content)
    text = str(content).strip()
    text = re.sub(r"^```(?:text|markdown)?\s*", "", text).rstrip("`").strip()
    if not text:
        raise RuntimeError("LLM returned empty response for receptionist query")
    return text


def receptionist_intent_classifier(state: AgentState) -> str:
    """
    Further classify the receptionist request type.
    
    Returns: "queue_status", "join_queue", "services", "close_queue",
             "book_appointment", "list_appointments", "cancel_appointment",
             "available_slots", "other"
    """
    
    messages = state.get("messages", [])
    if not messages:
        return "other"
    
    latest = messages[-1]
    if isinstance(latest, BaseMessage):
        content = str(latest.content).lower()
    else:
        content = str(latest).lower()
    
    # Appointment-related intents
    if any(word in content for word in ["appointment", "schedule", "book", "booking", "slot"]):
        if any(word in content for word in ["cancel", "remove", "delete"]):
            return "cancel_appointment"
        if any(word in content for word in ["available", "slot", "open", "free", "when can"]):
            return "available_slots"
        if any(word in content for word in ["list", "show", "today", "upcoming", "my appointment"]):
            return "list_appointments"
        if any(word in content for word in ["reschedule", "move", "change time"]):
            return "cancel_appointment"  # reschedule handled via cancel flow
        return "book_appointment"
    
    # Queue-related intents
    if any(word in content for word in ["queue", "wait", "position", "line", "busy"]):
        if "close" in content or "end" in content or "stop" in content:
            return "close_queue"
        return "queue_status"
    elif any(word in content for word in ["join", "register", "add"]):
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


def handle_book_appointment(state: AgentState) -> dict:
    """Book a new appointment from owner/customer request."""
    shop_id = state["tenant_id"]
    metadata = state.get("metadata") or {}

    # Extract appointment details from metadata or derive from message
    service_id = metadata.get("service_id")
    scheduled_start = metadata.get("scheduled_start")
    customer_name = metadata.get("customer_name", "Walk-in")
    customer_phone = metadata.get("customer_phone")
    customer_email = metadata.get("customer_email")
    employee_id = metadata.get("employee_id")

    if not service_id or not scheduled_start:
        response = AIMessage(
            content=_generate_receptionist_response(
                state,
                "appointment_missing_info",
                {"shop_id": shop_id},
                extra_instructions=(
                    "Ask the customer which service they want and when they'd like to come in. "
                    "Be helpful and suggest checking available slots."
                ),
            )
        )
        return {"messages": list(state["messages"]) + [response], "tool_results": None}

    result = appointment_tools.book_appointment(
        shop_id=shop_id,
        service_id=service_id,
        scheduled_start=scheduled_start,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email,
        employee_id=employee_id,
    )

    if result.get("error"):
        response = AIMessage(content=f"I couldn't book the appointment: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=_generate_receptionist_response(
            state,
            "appointment_booked",
            result,
            extra_instructions="Confirm the appointment with date, time, service, and any employee assigned. Mention they'll get a reminder.",
        )
    )
    return {"messages": list(state["messages"]) + [response], "tool_results": result}


def handle_list_appointments(state: AgentState) -> dict:
    """List today's or upcoming appointments."""
    shop_id = state["tenant_id"]
    result = appointment_tools.list_appointments(shop_id=shop_id)

    if result.get("error"):
        response = AIMessage(content=f"I couldn't load appointments: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=_generate_receptionist_response(
            state,
            "list_appointments",
            result,
            extra_instructions="Present appointments clearly with time, service, and customer name. State the total count.",
        )
    )
    return {"messages": list(state["messages"]) + [response], "tool_results": result}


def handle_cancel_appointment(state: AgentState) -> dict:
    """Cancel or reschedule an appointment."""
    shop_id = state["tenant_id"]
    metadata = state.get("metadata") or {}
    appointment_id = metadata.get("appointment_id")

    if not appointment_id:
        response = AIMessage(
            content=_generate_receptionist_response(
                state,
                "cancel_missing_id",
                {"shop_id": shop_id},
                extra_instructions="Ask which appointment they want to cancel — by ID, time, or customer name.",
            )
        )
        return {"messages": list(state["messages"]) + [response], "tool_results": None}

    reason = metadata.get("cancel_reason", "Requested by owner")
    result = appointment_tools.cancel_appointment(
        shop_id=shop_id, appointment_id=appointment_id, reason=reason,
    )

    if result.get("error"):
        response = AIMessage(content=f"Could not cancel appointment: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=_generate_receptionist_response(
            state,
            "appointment_cancelled",
            result,
            extra_instructions="Confirm the cancellation clearly and offer to reschedule.",
        )
    )
    return {"messages": list(state["messages"]) + [response], "tool_results": result}


def handle_available_slots(state: AgentState) -> dict:
    """Show available appointment slots for a service/day."""
    shop_id = state["tenant_id"]
    metadata = state.get("metadata") or {}
    service_id = metadata.get("service_id")
    date = metadata.get("date")

    if not service_id:
        response = AIMessage(
            content=_generate_receptionist_response(
                state,
                "slots_missing_service",
                {"shop_id": shop_id},
                extra_instructions="Ask which service and date the customer is interested in to check availability.",
            )
        )
        return {"messages": list(state["messages"]) + [response], "tool_results": None}

    from datetime import datetime as _dt
    if not date:
        date = _dt.now().strftime("%Y-%m-%d")

    result = appointment_tools.get_available_slots(
        shop_id=shop_id, service_id=service_id, date=date,
    )

    if result.get("error"):
        response = AIMessage(content=f"I couldn't check availability: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=_generate_receptionist_response(
            state,
            "available_slots",
            result,
            extra_instructions="List available time slots clearly and invite the customer to pick one.",
        )
    )
    return {"messages": list(state["messages"]) + [response], "tool_results": result}


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
                    "Booking appointments",
                    "Checking available slots",
                    "Cancelling or rescheduling appointments",
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
    graph.add_node("book_appointment", handle_book_appointment)
    graph.add_node("list_appointments", handle_list_appointments)
    graph.add_node("cancel_appointment", handle_cancel_appointment)
    graph.add_node("available_slots", handle_available_slots)
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
            "book_appointment": "book_appointment",
            "list_appointments": "list_appointments",
            "cancel_appointment": "cancel_appointment",
            "available_slots": "available_slots",
            "other": "other"
        }
    )
    
    # All handlers end
    graph.add_edge("queue_status", END)
    graph.add_edge("join_queue", END)
    graph.add_edge("services", END)
    graph.add_edge("close_queue", END)
    graph.add_edge("book_appointment", END)
    graph.add_edge("list_appointments", END)
    graph.add_edge("cancel_appointment", END)
    graph.add_edge("available_slots", END)
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
