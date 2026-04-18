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


def _prior_ai_text(state: AgentState) -> str:
    """Return the content of the last AIMessage in the conversation (before the latest user message)."""
    messages = state.get("messages", [])
    # Walk backwards skipping the latest message (the user's), find the last AI message
    for msg in reversed(messages[:-1] if len(messages) > 1 else []):
        if isinstance(msg, AIMessage):
            return str(msg.content).lower()
    return ""


def _get_recent_context(state: AgentState, max_turns: int = 4) -> str:
    """Build a short conversation context string from recent messages for LLM classification."""
    messages = state.get("messages", [])
    recent = messages[-max_turns:] if len(messages) > max_turns else messages
    parts = []
    for msg in recent:
        if isinstance(msg, AIMessage):
            parts.append(f"ASSISTANT: {str(msg.content)[:300]}")
        elif isinstance(msg, BaseMessage):
            parts.append(f"USER: {str(msg.content)[:300]}")
        else:
            parts.append(f"USER: {str(msg)[:300]}")
    return "\n".join(parts)


def receptionist_intent_classifier(state: AgentState) -> str:
    """
    Use the LLM to classify the receptionist request type based on conversation context.
    
    Returns: "queue_status", "join_queue", "services", "close_queue",
             "book_appointment", "list_appointments", "cancel_appointment",
             "available_slots", "create_service", "update_service",
             "delete_service", "call_next", "other"
    """
    messages = state.get("messages", [])
    if not messages:
        return "other"

    context = _get_recent_context(state)
    user_text = _latest_user_text(state)

    llm = _get_receptionist_writer_llm()
    prompt = (
        "You are an intent classifier for a receptionist agent in a service business.\n"
        "Given the conversation context and the latest user message, classify the intent into EXACTLY ONE of these categories:\n\n"
        "- queue_status: checking queue length, wait times, who is in line\n"
        "- join_queue: customer wants to join the queue\n"
        "- call_next: serve next customer, call next in line\n"
        "- close_queue: close or end the queue for the day\n"
        "- services: asking about available services, prices, what the shop offers (read-only inquiry)\n"
        "- create_service: adding a NEW service to the shop catalog (owner action)\n"
        "- update_service: changing an existing service's price, duration, or details\n"
        "- delete_service: removing or deactivating a service\n"
        "- book_appointment: scheduling a new appointment or booking\n"
        "- list_appointments: viewing existing appointments\n"
        "- cancel_appointment: cancelling or rescheduling an appointment\n"
        "- available_slots: checking open time slots\n"
        "- other: general help, greetings, or anything that doesn't fit above\n\n"
        "IMPORTANT: Consider the full conversation context. If the assistant previously asked for "
        "service details (name, price) and the user is now providing them, classify as 'create_service'. "
        "If the assistant asked what to change about a service, classify as 'update_service'.\n\n"
        f"CONVERSATION:\n{context}\n\n"
        f"LATEST USER MESSAGE: {user_text}\n\n"
        "Respond with ONLY the intent label (one of the categories above), nothing else. No explanation."
    )

    try:
        response = llm.invoke([{"role": "user", "content": prompt}])
        raw = str(response.content).strip().lower()
        # Clean up: remove any markdown, quotes, extra text
        raw = re.sub(r"[`\"']", "", raw).strip()
        # Extract just the first word/phrase that matches a valid intent
        valid_intents = {
            "queue_status", "join_queue", "call_next", "close_queue",
            "services", "create_service", "update_service", "delete_service",
            "book_appointment", "list_appointments", "cancel_appointment",
            "available_slots", "other",
        }
        # Try exact match first
        if raw in valid_intents:
            return raw
        # Try to find a valid intent within the response
        for intent in valid_intents:
            if intent in raw:
                return intent
        return "other"
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"LLM intent classification failed: {e}, falling back to 'other'")
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


def handle_call_next(state: AgentState) -> dict:
    """Call the next waiting customer in the queue."""
    shop_id = state["tenant_id"]
    result = booking_tools.call_next(shop_id)

    if result.get("error"):
        response = AIMessage(content=f"Couldn't call the next customer: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=_generate_receptionist_response(
            state,
            "call_next",
            result,
            extra_instructions=(
                "Announce that the next customer has been called. "
                "Include their name, position number, and service if available. "
                "Keep it very brief — one or two sentences."
            ),
        )
    )
    return {"messages": list(state["messages"]) + [response], "tool_results": result}


def _extract_booking_entities_from_message(message: str, shop_id: int) -> Dict[str, Any]:
    """
    Parse a natural-language booking request into structured fields.

    Returns a dict with keys: customer_name, service_id, scheduled_start (ISO str),
    customer_phone, customer_email.  Any field that cannot be reliably extracted is None.
    """
    from datetime import datetime, timedelta

    result: Dict[str, Any] = {
        "customer_name": None,
        "service_id": None,
        "scheduled_start": None,
        "customer_phone": None,
        "customer_email": None,
    }

    # ── Customer name ────────────────────────────────────────────────
    # Match "for customer <Name>" or "for <Name>"
    name_m = re.search(
        r"(?:for customer|for client|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        message,
    )
    if name_m:
        result["customer_name"] = name_m.group(1).strip()

    # ── Date/time ────────────────────────────────────────────────────
    now = datetime.utcnow()
    date_part: datetime | None = None

    if re.search(r"\btomorrow\b", message, re.I):
        date_part = now + timedelta(days=1)
    elif re.search(r"\btoday\b", message, re.I):
        date_part = now
    else:
        # Try "YYYY-MM-DD"
        date_str_m = re.search(r"(\d{4}-\d{2}-\d{2})", message)
        if date_str_m:
            try:
                date_part = datetime.strptime(date_str_m.group(1), "%Y-%m-%d")
            except ValueError:
                pass
        if not date_part:
            # "next monday" etc. — skip complex parsing for now
            date_part = now + timedelta(days=1)  # default tomorrow

    time_m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", message, re.I)
    if time_m and date_part:
        hour = int(time_m.group(1))
        minute = int(time_m.group(2) or "0")
        period = time_m.group(3).lower()
        if period == "pm" and hour < 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        scheduled = date_part.replace(hour=hour, minute=minute, second=0, microsecond=0)
        result["scheduled_start"] = scheduled.isoformat()
    elif date_part:
        scheduled = date_part.replace(hour=10, minute=0, second=0, microsecond=0)
        result["scheduled_start"] = scheduled.isoformat()

    # ── Service lookup ───────────────────────────────────────────────
    # Fetch all active services for this shop and fuzzy-match against message
    try:
        import difflib
        from db_interface import db_interface as _dbi
        services = _dbi.get_shop_services(shop_id)  # returns list of dicts
        if services:
            msg_lower = message.lower()
            best_ratio = 0.0
            best_id = None
            for svc in services:
                svc_name = (svc.get("name") if isinstance(svc, dict) else getattr(svc, "name", None) or "").lower()
                if not svc_name:
                    continue
                # Exact substring match first
                if svc_name in msg_lower:
                    best_id = svc.get("id") if isinstance(svc, dict) else getattr(svc, "id", None)
                    best_ratio = 1.0
                    break
                ratio = difflib.SequenceMatcher(None, svc_name, msg_lower).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_id = svc.get("id") if isinstance(svc, dict) else getattr(svc, "id", None)
            if best_id and best_ratio >= 0.4:
                result["service_id"] = best_id
    except Exception:
        pass

    return result


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

    # If critical fields are missing, attempt to extract from the latest message
    if not service_id or not scheduled_start:
        user_text = _latest_user_text(state)
        extracted = _extract_booking_entities_from_message(user_text, shop_id)
        if not service_id and extracted.get("service_id"):
            service_id = extracted["service_id"]
        if not scheduled_start and extracted.get("scheduled_start"):
            scheduled_start = extracted["scheduled_start"]
        if customer_name == "Walk-in" and extracted.get("customer_name"):
            customer_name = extracted["customer_name"]
        if not customer_phone and extracted.get("customer_phone"):
            customer_phone = extracted["customer_phone"]
        if not customer_email and extracted.get("customer_email"):
            customer_email = extracted["customer_email"]

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


# ── Service management handlers ────────────────────────────────────

def _parse_service_fields(text: str) -> Dict[str, Any]:
    """Use the LLM to extract service name, cost, duration, and currency from natural language."""
    llm = _get_receptionist_writer_llm()
    prompt = (
        "Extract service details from the following text. Return ONLY a JSON object with these fields:\n"
        '- "name": the service name (string or null)\n'
        '- "cost": the price as a number (float or null)\n'
        '- "duration_minutes": duration in minutes (integer or null)\n'
        '- "currency": currency code like USD, CAD, EUR, GBP (string, default "USD")\n'
        '- "description": brief description if mentioned (string or null)\n\n'
        "Rules:\n"
        "- If the user says 'Canadian dollars' or 'CAD', set currency to 'CAD'.\n"
        "- If the user says 'euros' or 'EUR', set currency to 'EUR'.\n"
        "- If no currency is mentioned, default to 'USD'.\n"
        "- Return ONLY valid JSON, no explanation or markdown.\n\n"
        f'Text: "{text}"\n\n'
        "JSON:"
    )

    try:
        response = llm.invoke([{"role": "user", "content": prompt}])
        raw = str(response.content).strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw).rstrip("`").strip()
        parsed = _json.loads(raw)
        # Validate and clean types
        fields: Dict[str, Any] = {}
        if parsed.get("name") and isinstance(parsed["name"], str):
            fields["name"] = parsed["name"].strip()
        if parsed.get("cost") is not None:
            try:
                fields["cost"] = float(parsed["cost"])
            except (ValueError, TypeError):
                pass
        if parsed.get("duration_minutes") is not None:
            try:
                fields["duration_minutes"] = int(parsed["duration_minutes"])
            except (ValueError, TypeError):
                pass
        if parsed.get("currency") and isinstance(parsed["currency"], str):
            fields["currency"] = parsed["currency"].upper().strip()
        if parsed.get("description") and isinstance(parsed["description"], str):
            fields["description"] = parsed["description"].strip()
        return fields
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"LLM service field extraction failed: {e}")
        return {}


def handle_create_service(state: AgentState) -> dict:
    """Create a new shop service from owner's message."""
    shop_id = state["tenant_id"]
    text = _latest_user_text(state)
    fields = _parse_service_fields(text)

    name = fields.get("name")
    cost = fields.get("cost")

    if not name or cost is None:
        response = AIMessage(
            content=_generate_receptionist_response(
                state,
                "create_service_missing",
                {"parsed": fields},
                extra_instructions=(
                    "The owner wants to add a service but some details are missing. "
                    "Ask for the service name and price. Mention duration is optional (default 30 min)."
                ),
            )
        )
        return {"messages": list(state["messages"]) + [response], "tool_results": None}

    result = booking_tools.create_service(
        shop_id=shop_id,
        name=name,
        cost=cost,
        duration_minutes=fields.get("duration_minutes", 30),
        description=fields.get("description"),
        currency=fields.get("currency", "USD"),
    )

    if result.get("error"):
        response = AIMessage(content=f"I couldn't create the service: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=_generate_receptionist_response(
            state,
            "service_created",
            result,
            extra_instructions="Confirm the new service was created with its name, price, and duration.",
        )
    )
    return {"messages": list(state["messages"]) + [response], "tool_results": result}


def handle_update_service(state: AgentState) -> dict:
    """Update an existing service (price, name, duration)."""
    shop_id = state["tenant_id"]
    text = _latest_user_text(state)
    fields = _parse_service_fields(text)

    # Try to resolve service by name from existing catalog
    target_name = fields.get("name")
    service_id = None

    if target_name:
        catalog = booking_tools.search_services(shop_id)
        for svc in catalog.get("services", []):
            if svc.get("name", "").lower() == target_name.lower():
                service_id = svc["id"]
                break

    # If no name quoted, try fuzzy match against message
    if not service_id:
        catalog = booking_tools.search_services(shop_id)
        import difflib
        text_lower = text.lower()
        best_ratio, best_id = 0.0, None
        for svc in catalog.get("services", []):
            svc_name = svc.get("name", "").lower()
            if svc_name and svc_name in text_lower:
                best_id = svc["id"]
                best_ratio = 1.0
                break
            ratio = difflib.SequenceMatcher(None, svc_name, text_lower).ratio()
            if ratio > best_ratio:
                best_ratio, best_id = ratio, svc["id"]
        if best_id and best_ratio >= 0.4:
            service_id = best_id

    if not service_id:
        response = AIMessage(
            content=_generate_receptionist_response(
                state,
                "update_service_not_found",
                {"parsed": fields, "shop_id": shop_id},
                extra_instructions=(
                    "Could not identify which service the owner wants to update. "
                    "List the current services and ask the owner to specify which one."
                ),
            )
        )
        return {"messages": list(state["messages"]) + [response], "tool_results": None}

    updates = {}
    if fields.get("cost") is not None:
        updates["cost"] = fields["cost"]
    if fields.get("duration_minutes") is not None:
        updates["duration_minutes"] = fields["duration_minutes"]
    # Don't update name to the matched name — only if a new name was explicitly given
    # (future: handle "rename X to Y" patterns)

    if not updates:
        response = AIMessage(
            content=_generate_receptionist_response(
                state,
                "update_service_no_changes",
                {"service_id": service_id},
                extra_instructions="Ask what the owner wants to change about this service (price, duration, etc.).",
            )
        )
        return {"messages": list(state["messages"]) + [response], "tool_results": None}

    result = booking_tools.update_service(shop_id=shop_id, service_id=service_id, **updates)

    if result.get("error"):
        response = AIMessage(content=f"Could not update the service: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=_generate_receptionist_response(
            state,
            "service_updated",
            result,
            extra_instructions="Confirm what was changed with the new values.",
        )
    )
    return {"messages": list(state["messages"]) + [response], "tool_results": result}


def handle_delete_service(state: AgentState) -> dict:
    """Deactivate a service."""
    shop_id = state["tenant_id"]
    text = _latest_user_text(state)

    # Resolve service by name
    catalog = booking_tools.search_services(shop_id)
    import difflib
    text_lower = text.lower()
    best_ratio, best_id, best_name = 0.0, None, None
    for svc in catalog.get("services", []):
        svc_name = svc.get("name", "").lower()
        if svc_name and svc_name in text_lower:
            best_id, best_name = svc["id"], svc.get("name")
            best_ratio = 1.0
            break
        ratio = difflib.SequenceMatcher(None, svc_name, text_lower).ratio()
        if ratio > best_ratio:
            best_ratio, best_id, best_name = ratio, svc["id"], svc.get("name")

    if not best_id or best_ratio < 0.4:
        response = AIMessage(
            content=_generate_receptionist_response(
                state,
                "delete_service_not_found",
                {"shop_id": shop_id},
                extra_instructions="Could not identify the service to remove. List current services and ask which one.",
            )
        )
        return {"messages": list(state["messages"]) + [response], "tool_results": None}

    result = booking_tools.delete_service(shop_id=shop_id, service_id=best_id)

    if result.get("error"):
        response = AIMessage(content=f"Could not remove the service: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=_generate_receptionist_response(
            state,
            "service_deleted",
            {"name": best_name, **result},
            extra_instructions="Confirm the service has been deactivated.",
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
    graph.add_node("call_next", handle_call_next)
    graph.add_node("book_appointment", handle_book_appointment)
    graph.add_node("list_appointments", handle_list_appointments)
    graph.add_node("cancel_appointment", handle_cancel_appointment)
    graph.add_node("available_slots", handle_available_slots)
    graph.add_node("create_service", handle_create_service)
    graph.add_node("update_service", handle_update_service)
    graph.add_node("delete_service", handle_delete_service)
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
            "call_next": "call_next",
            "book_appointment": "book_appointment",
            "list_appointments": "list_appointments",
            "cancel_appointment": "cancel_appointment",
            "available_slots": "available_slots",
            "create_service": "create_service",
            "update_service": "update_service",
            "delete_service": "delete_service",
            "other": "other"
        }
    )
    
    # All handlers end
    graph.add_edge("queue_status", END)
    graph.add_edge("join_queue", END)
    graph.add_edge("services", END)
    graph.add_edge("close_queue", END)
    graph.add_edge("call_next", END)
    graph.add_edge("book_appointment", END)
    graph.add_edge("list_appointments", END)
    graph.add_edge("cancel_appointment", END)
    graph.add_edge("available_slots", END)
    graph.add_edge("create_service", END)
    graph.add_edge("update_service", END)
    graph.add_edge("delete_service", END)
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
