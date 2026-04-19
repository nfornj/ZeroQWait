"""
Supervisor Agent Graph - Central router for owner commands.
The Supervisor:
1. Receives owner's natural-language command
2. Classifies intent (booking/queue, finance/analytics, hr/employees, general)
3. Routes to appropriate sub-agent (Receptionist, Finance, HR) via conditional edge
4. Collects sub-agent result and formats response
5. Checkpoints state after each step

Routing Logic:
- Queue/booking → Receptionist sub-agent
- Revenue/analytics → Finance sub-agent
- Employees/shifts → HR sub-agent
- General/unclear → Supervisor (self-respond)

Multi-tenancy:
- tenant_id is immutable in state (injected at entry point)
- All tool calls inherit tenant_id context
- Checkpoint thread_id = f"tenant_{shop_id}_{user_id}"

Phase 1 (Current): Basic Supervisor without actual sub-agents
Phase 2: Add conditional edges to real sub-agents
"""

from typing import Literal, Dict, Any, List, Optional
import logging
import re
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langgraph.types import Command, interrupt

from .state import AgentState
from .tools import booking_tools, hr_tools
from .memory_context import get_conversation_history, save_conversation_turn
from redis_client import redis_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured-output model for intent classification
# ---------------------------------------------------------------------------

class RoutingDecision(BaseModel):
    """LLM-produced routing decision for the supervisor."""
    thought_process: str = Field(
        description="Brief reasoning (1-2 sentences) explaining why this intent was chosen."
    )
    next_agent: Literal["booking", "finance", "hr", "crm", "general"] = Field(
        description=(
            "The specialist to route to. "
            "booking = queue, appointments, wait times, services, bookings. "
            "finance = revenue, analytics, reports, invoices, payments, POS, client retention, visit history, inactive customers. "
            "hr = employees, shifts, scheduling, availability, clock in/out. "
            "crm = CRM leads, contacts, companies, pipeline, deals, Odoo ERP operations. "
            "general = greetings, help, capabilities, anything that doesn't fit above."
        )
    )
    is_followup: bool = Field(
        default=False,
        description="True if the message is a follow-up that continues the previous specialist context."
    )


def _clarifying_prompt(user_text: str, mixed_intents: Optional[List[str]] = None) -> str:
    if mixed_intents:
        mapped = {
            "booking": "queue and services",
            "finance": "revenue and analytics",
            "hr": "employees and staffing",
        }
        options = [mapped.get(intent, intent) for intent in mixed_intents]
        return (
            "I can help with multiple parts of that request. "
            f"Should we start with {', '.join(options)} first? "
            "If you prefer, send it as separate steps and I will handle each one in order."
        )
    return (
        "I can help with queue/services, revenue analytics, or employee staffing. "
        "What should I handle first for your shop?"
    )


def _get_previous_specialist(state: AgentState) -> Optional[str]:
    """Get the last specialist that handled a message, for follow-up routing."""
    metadata = state.get("metadata") or {}
    previous = (metadata.get("route") or {}).get("to")
    if previous in {"receptionist", "finance", "hr", "crm"}:
        return previous
    previous = metadata.get("last_specialist_target")
    if previous in {"receptionist", "finance", "hr", "crm"}:
        return previous
    current = state.get("current_agent")
    if current in {"receptionist", "finance", "hr", "crm"}:
        return current
    return None


# Initialize LLM (qwen3:14b-q4_K_M via Ollama)
def get_llm():
    """Create LLM instance for agent graphs."""
    import os
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
    model_name = os.getenv("MODEL_NAME", "qwen3:14b-q4_K_M")

    # ChatOllama uses the native Ollama REST API (/api/chat), NOT the OpenAI-compatible
    # /v1 endpoint. Strip the /v1 suffix when present so URLs like
    # http://host:30002/v1 don't result in http://host:30002/v1/api/chat (404).
    base_url = ollama_url[:-3] if ollama_url.endswith("/v1") else ollama_url

    return ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0.3,  # Deterministic for tool calling
        top_p=0.9,
        num_gpu=-1,
    )


def _merge_metadata(state: AgentState, updates: Dict[str, Any]) -> Dict[str, Any]:
    metadata = dict(state.get("metadata") or {})
    metadata.update(updates)
    return metadata


def _latest_user_text(state: AgentState) -> str:
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    if messages:
        latest = messages[-1]
        if isinstance(latest, BaseMessage):
            return str(latest.content)
        return str(latest)
    return ""


def _conversation_history_messages(state: AgentState) -> List[BaseMessage]:
    """Load persisted per-shop conversation history from Redis and map to messages."""
    shop_id = state.get("tenant_id")
    user_id = state.get("user_id")
    if shop_id is None or user_id is None:
        return []

    history_items = get_conversation_history(redis_client, str(shop_id), str(user_id))
    history_messages: List[BaseMessage] = []
    for item in history_items:
        role = item.get("role")
        content = str(item.get("content", ""))
        if not content:
            continue
        if role == "user":
            history_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            history_messages.append(AIMessage(content=content))
    return history_messages


def _persist_conversation_turns(state: AgentState, assistant_text: str) -> None:
    """Persist user and assistant turns to Redis conversation history."""
    shop_id = state.get("tenant_id")
    user_id = state.get("user_id")
    if shop_id is None or user_id is None:
        return

    user_text = _latest_user_text(state).strip()
    assistant_text = str(assistant_text or "").strip()

    if user_text:
        save_conversation_turn(
            redis_client,
            str(shop_id),
            str(user_id),
            "user",
            user_text,
        )
    if assistant_text:
        save_conversation_turn(
            redis_client,
            str(shop_id),
            str(user_id),
            "assistant",
            assistant_text,
        )


def classify_intent(state: AgentState) -> Command[Literal["plan_execution"]]:
    """
    Classify owner's intent using LLM structured output.

    A single ``llm.with_structured_output(RoutingDecision)`` call replaces
    the previous 300+ lines of keyword arrays and fuzzy heuristics.
    """

    messages = state.get("messages", [])
    if not messages:
        return Command(
            goto="plan_execution",
            update={
                "current_agent": "general",
                "metadata": _merge_metadata(state, {
                    "classified_intent": "general",
                    "classification_source": "empty_messages",
                }),
            },
        )

    user_input = _latest_user_text(state)
    previous_specialist = _get_previous_specialist(state)
    history_messages = _conversation_history_messages(state)

    # Build context for the LLM
    context_lines = []
    if previous_specialist:
        target_to_intent = {
            "receptionist": "booking", "finance": "finance",
            "hr": "hr", "crm": "crm",
        }
        prev_intent = target_to_intent.get(previous_specialist, previous_specialist)
        context_lines.append(
            f"The previous message was handled by the '{prev_intent}' specialist. "
            "If the new message is a follow-up (e.g. 'what about february?', 'show their names'), "
            "set is_followup=true and route to the same specialist."
        )

    system_prompt = (
        "You are a routing classifier for ZeroQwait, a shop management platform. "
        "Classify the shop owner's message into exactly one specialist.\n\n"
        "Specialists:\n"
        "- booking: queue management, appointments, wait times, services, bookings, slots, close/open queue, call next customer\n"
        "- finance: revenue, analytics, financial reports, invoices, payments, POS, billing, "
        "refunds, daily/weekly/monthly summaries, client retention, inactive customers, visit history, top clients, export CSV\n"
        "- hr: employees, shifts, scheduling, availability, staffing, clock in/out, roster\n"
        "- crm: CRM leads, contacts, companies, pipeline, deals, Odoo ERP operations, "
        "accounting, journal entries, products catalog\n"
        "- general: greetings, help, capabilities, general chat\n\n"
        + ("\n".join(context_lines) + "\n" if context_lines else "")
        + "Respond with your classification."
    )

    llm = get_llm()

    try:
        structured_llm = llm.with_structured_output(RoutingDecision)
        decision: RoutingDecision = structured_llm.invoke(
            [SystemMessage(content=system_prompt)]
            + history_messages
            + [HumanMessage(content=user_input)]
        )
        intent = decision.next_agent
        source = "llm_structured"
        logger.info(
            "classify_intent: %r → %s (followup=%s, reason=%s)",
            user_input[:80], intent, decision.is_followup, decision.thought_process,
        )
    except Exception as e:
        logger.warning("classify_intent structured output failed, falling back: %s", e)
        # Single-shot fallback — bare LLM call with plain text
        try:
            fallback_prompt = (
                "Classify this shop owner command into exactly one word: "
                "booking, finance, hr, crm, or general.\n\n"
                f"Command: {user_input}\n\nCategory:"
            )
            resp = llm.invoke([HumanMessage(content=fallback_prompt)])
            raw = str(resp.content).strip().lower()
            intent = raw if raw in {"booking", "finance", "hr", "crm", "general"} else "general"
            source = "llm_fallback"
        except Exception:
            intent = "general"
            source = "error_fallback"

    return Command(
        goto="plan_execution",
        update={
            "current_agent": intent,
            "metadata": _merge_metadata(state, {
                "classified_intent": intent,
                "classification_source": source,
                "requires_clarification": False,
            }),
        },
    )


def plan_execution(state: AgentState) -> dict:
    """
    Build a lightweight execution plan from classified intent.

    This separates planning from routing so the graph can reason about
    target agent and strategy before execution.
    """

    intent = state.get("current_agent", "general")
    owner_request = _latest_user_text(state)

    target_by_intent = {
        "booking": "receptionist",
        "finance": "finance",
        "hr": "hr",
        "crm": "crm",
        "general": "general",
    }
    execution_target = target_by_intent.get(intent, "general")

    plan = {
        "intent": intent,
        "execution_target": execution_target,
        "owner_request": owner_request,
        "strategy": "delegate_to_specialist" if execution_target != "general" else "supervisor_direct",
    }

    return {
        "metadata": _merge_metadata(
            state,
            {
                "plan": plan,
                "execution_target": execution_target,
            },
        )
    }


def route_to_agent(state: AgentState) -> dict:
    """
    Route to the appropriate sub-agent based on classified intent.
    
    Phase 1: Returns intent as routing hint (no actual sub-agents yet)
    Phase 2: Will route to actual sub-agent graphs via invoke()
    """
    
    metadata = state.get("metadata") or {}
    execution_target = metadata.get("execution_target")

    routed_target = execution_target if execution_target in {"receptionist", "finance", "hr", "crm", "general"} else "general"

    return {
        "metadata": _merge_metadata(
            state,
            {
                "route": {
                    "from_intent": state.get("current_agent", "general"),
                    "to": routed_target,
                },
                "execution_target": routed_target,
            },
        )
    }


async def _run_crm_agent(state: AgentState) -> dict:
    """Dispatch CRM query to Odoo ERP via XML-RPC."""
    import re as _re

    user_text = _latest_user_text(state)
    messages = list(state.get("messages", []) or [])
    shop_id = state.get("tenant_id")
    lowered = user_text.lower()

    from .tools import odoo_tools

    try:
        if any(w in lowered for w in ["pipeline", "opportunity", "opportunities", "deal", "deals"]):
            if any(w in lowered for w in ["summary", "overview", "how many", "total"]):
                data = await odoo_tools.odoo_get_pipeline_summary(shop_id=shop_id)
            else:
                data = await odoo_tools.odoo_get_leads(shop_id=shop_id)
        elif any(w in lowered for w in ["compan", "companies"]):
            data = await odoo_tools.odoo_get_companies(shop_id=shop_id)
        elif any(w in lowered for w in ["stage", "stages"]):
            if any(w in lowered for w in ["list", "show", "what", "available"]):
                data = await odoo_tools.odoo_get_lead_stages(shop_id=shop_id)
            else:
                # Move lead to stage: "move lead 5 to won"
                move_m = _re.search(r'(?:move|change|update)\s+(?:lead|deal|opportunity)\s+#?(\d+)\s+(?:to|→)\s+(.+)', user_text, _re.IGNORECASE)
                if move_m:
                    data = await odoo_tools.odoo_update_lead_stage(int(move_m.group(1)), move_m.group(2).strip())
                else:
                    data = await odoo_tools.odoo_get_lead_stages(shop_id=shop_id)
        elif any(w in lowered for w in ["lead", "leads"]):
            if any(w in lowered for w in ["create", "make", "add", "new"]):
                # Extract lead name from quotes or after keyword
                name_m = _re.search(r'["\']([^"\']+)["\']', user_text)
                if not name_m:
                    name_m = _re.search(r'(?:called|named|titled)\s+(.+?)(?:\s+(?:with|for|worth)|\s*$)', user_text, _re.IGNORECASE)
                lead_name = name_m.group(1) if name_m else user_text[:80]
                # Extract revenue if mentioned
                rev_m = _re.search(r'\$?([\d,]+(?:\.\d+)?)', user_text)
                revenue = float(rev_m.group(1).replace(",", "")) if rev_m else 0.0
                data = await odoo_tools.odoo_create_lead(
                    name=lead_name, shop_id=shop_id, expected_revenue=revenue
                )
            elif any(w in lowered for w in ["note", "comment"]):
                # Add note to lead: "add note to lead 5: Great meeting"
                note_m = _re.search(r'(?:lead|deal|opportunity)\s+#?(\d+)[:\s]+(.+)', user_text, _re.IGNORECASE)
                if note_m:
                    data = await odoo_tools.odoo_add_note_to_lead(int(note_m.group(1)), note_m.group(2).strip())
                else:
                    data = {"error": "Please specify lead ID and note text, e.g. 'add note to lead 5: Great meeting'"}
            else:
                data = await odoo_tools.odoo_get_leads(shop_id=shop_id)
        elif any(w in lowered for w in ["contact", "contacts"]):
            if any(w in lowered for w in ["create", "make", "add", "new"]):
                name_m = _re.search(r'["\']([^"\']+)["\']', user_text)
                if not name_m:
                    name_m = _re.search(r'(?:called|named)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', user_text)
                contact_name = name_m.group(1) if name_m else None
                email_m = _re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', user_text)
                phone_m = _re.search(r'(?:phone|tel|call)\s*[:#]?\s*([\d\s\-+()]+)', user_text, _re.IGNORECASE)
                if contact_name:
                    data = await odoo_tools.odoo_create_contact(
                        name=contact_name, shop_id=shop_id,
                        email=email_m.group(0) if email_m else None,
                        phone=phone_m.group(1).strip() if phone_m else None,
                    )
                else:
                    data = {"error": "Please specify the contact name, e.g. 'create contact called John Smith'"}
            elif any(w in lowered for w in ["update", "edit", "change"]):
                upd_m = _re.search(r'(?:contact|person)\s+#?(\d+)', user_text, _re.IGNORECASE)
                if upd_m:
                    cid = int(upd_m.group(1))
                    email_m = _re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', user_text)
                    phone_m = _re.search(r'(?:phone|tel)\s*[:#]?\s*([\d\s\-+()]+)', user_text, _re.IGNORECASE)
                    data = await odoo_tools.odoo_update_contact(
                        contact_id=cid,
                        email=email_m.group(0) if email_m else None,
                        phone=phone_m.group(1).strip() if phone_m else None,
                    )
                else:
                    data = {"error": "Please specify the contact ID, e.g. 'update contact #12 email: new@email.com'"}
            else:
                data = await odoo_tools.odoo_get_contacts(shop_id=shop_id)
        elif any(w in lowered for w in ["invoice", "invoices", "bill", "bills"]):
            if any(w in lowered for w in ["create", "make", "add", "new", "generate"]):
                import re as _re2
                amount_m = _re2.search(r'\$?([\d,]+(?:\.\d+)?)', user_text)
                amount = float(amount_m.group(1).replace(",", "")) if amount_m else 0.0
                lines = [{"name": user_text[:80], "quantity": 1, "price_unit": amount}]
                data = await odoo_tools.odoo_create_invoice(
                    partner_id=1, lines=lines, shop_id=shop_id
                )
            else:
                data = await odoo_tools.odoo_get_invoices(shop_id=shop_id)
        elif any(w in lowered for w in ["payment", "payments", "paid"]):
            data = await odoo_tools.odoo_get_payments(shop_id=shop_id)
        elif any(w in lowered for w in ["product", "products", "service", "services", "catalog"]):
            data = await odoo_tools.odoo_get_products(shop_id=shop_id)
        elif any(w in lowered for w in ["revenue", "sales", "income", "earnings"]):
            data = await odoo_tools.odoo_get_revenue_summary(shop_id=shop_id)
        elif any(w in lowered for w in ["journal", "accounting", "balance", "trial balance"]):
            data = await odoo_tools.odoo_get_account_balance(shop_id=shop_id)
        elif any(w in lowered for w in ["note", "notes"]):
            # Add note to a specific lead
            note_m = _re.search(r'(?:lead|deal|opportunity)\s+#?(\d+)[:\s]+(.+)', user_text, _re.IGNORECASE)
            if note_m:
                data = await odoo_tools.odoo_add_note_to_lead(int(note_m.group(1)), note_m.group(2).strip())
            else:
                data = {"message": "To add a note, say: 'add note to lead #5: Your note text'"}
        else:
            name_match = _re.search(
                r'(?:about|details|show|find|search|who is|contact)\s+'
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                user_text,
            )
            if name_match:
                data = await odoo_tools.odoo_search_contact(name_match.group(1), shop_id=shop_id)
            else:
                data = await odoo_tools.odoo_get_contacts(shop_id=shop_id)
    except Exception as e:
        data = {"error": str(e)}

    llm = get_llm()
    history_messages = _conversation_history_messages(state)

    crm_system_prompt = f"""You are the CRM/ERP assistant for shop (shop_id={shop_id}).
You have the owner's Odoo data below. Answer naturally and concisely.

Formatting rules:
- People/Contacts: "Name (email) — Company"
- Opportunities/Leads: "Deal Name — $X,XXX (Stage)"
- Pipeline summary: table by stage
- Invoices: "Invoice # — $Amount (Status)"
- Payments: "Payment # — $Amount (Status, Date)"
- Empty results: "Your Odoo doesn't have any [type] yet"
- Always state the total count when listing items
- NEVER invent data — only use what is provided

Odoo data:
{data}

Owner asked: {user_text}"""

    try:
        response = llm.invoke(
            history_messages + messages + [SystemMessage(content=crm_system_prompt)]
        )
    except Exception as e:
        response = AIMessage(
            content=f"I retrieved your Odoo data but had trouble formatting it: {e}"
        )

    return {
        "messages": messages + [response],
        "current_agent": "crm",
        "tool_results": {"crm_data": data},
    }


def execute_plan(state: AgentState) -> dict:
    """
    Execute the routed plan.

    Specialist execution happens here; general requests are handled by
    supervisor synthesis directly in the next node.
    """

    metadata = state.get("metadata") or {}
    target = metadata.get("execution_target", "general")

    if target == "receptionist":
        result = placeholder_receptionist(state)
        merged_metadata = dict(metadata)
        merged_metadata.update(result.get("metadata") or {})
        merged_metadata["last_specialist_target"] = "receptionist"
        return {**result, "metadata": merged_metadata}
    if target == "finance":
        result = placeholder_finance(state)
        merged_metadata = dict(metadata)
        merged_metadata.update(result.get("metadata") or {})
        merged_metadata["last_specialist_target"] = "finance"
        return {**result, "metadata": merged_metadata}
    if target == "hr":
        result = placeholder_hr(state)
        merged_metadata = dict(metadata)
        merged_metadata.update(result.get("metadata") or {})
        merged_metadata["last_specialist_target"] = "hr"
        return {**result, "metadata": merged_metadata}
    if target == "crm":
        import asyncio
        import concurrent.futures
        loop = asyncio.new_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, _run_crm_agent(state))
            result = future.result()
        merged_metadata = dict(metadata)
        merged_metadata.update(result.get("metadata") or {})
        merged_metadata["last_specialist_target"] = "crm"
        return {**result, "metadata": merged_metadata}

    return {
        "current_agent": "supervisor",
    }


def synthesize_response(state: AgentState) -> dict:
    """
    Supervisor response node. Called when:
    - Intent is "general" (handled by Supervisor directly)
    - Sub-agent has completed and returned result
    
    Formats final response to owner.
    """
    
    # Get conversation history
    messages = list(state.get("messages", []) or [])
    history_messages = _conversation_history_messages(state)
    llm_messages = history_messages + messages
    metadata = state.get("metadata") or {}

    current_agent = state.get("current_agent", "supervisor")

    if current_agent == "supervisor" and metadata.get("requires_clarification"):
        clarifier = AIMessage(
            content=_clarifying_prompt(
                _latest_user_text(state),
                mixed_intents=(metadata.get("mixed_intents") or None),
            )
        )
        _persist_conversation_turns(state, str(clarifier.content))
        return {
            "messages": messages + [clarifier],
            "tool_results": state.get("tool_results"),
            "metadata": _merge_metadata(state, {"requires_clarification": False}),
        }

    # Deterministic specialist synthesis: keep tool-grounded specialist answer
    # intact (without forced boilerplate suffix).
    if current_agent in {"receptionist", "finance", "hr", "crm"} and messages:
        last_message = messages[-1]
        if isinstance(last_message, AIMessage):
            mixed_intents = list(metadata.get("mixed_intents") or [])
            requires_clarification = bool(metadata.get("requires_clarification"))
            if requires_clarification and len(mixed_intents) > 1:
                next_domains = [intent for intent in mixed_intents if intent != current_agent]
                if next_domains:
                    followup = AIMessage(
                        content=_clarifying_prompt(_latest_user_text(state), mixed_intents=next_domains)
                    )
                    _persist_conversation_turns(state, str(followup.content))
                    return {
                        "messages": messages + [followup],
                        "tool_results": state.get("tool_results"),
                        "metadata": _merge_metadata(
                            state,
                            {
                                "mixed_intents": next_domains,
                                "requires_clarification": False,
                            },
                        ),
                    }
            _persist_conversation_turns(state, str(last_message.content))
            return {
                "messages": messages,
                "tool_results": state.get("tool_results"),
            }

    llm = get_llm()

    # ── Shop-type adaptive prompt ────────────────────────────────
    shop_type_hint = ""
    try:
        from db_interface import db_interface
        from .vertical_profiles import build_vertical_system_prompt
        shop_data = db_interface.get_shop_by_id(state.get("tenant_id"))
        if shop_data:
            shop_type_hint = "\n" + build_vertical_system_prompt(
                shop_data.get("shop_type", ""), agent_role="supervisor"
            )
    except Exception:
        pass
    
    # Build response prompt
    system_prompt = f"""You are ZeroQwait Supervisor Agent, managing the AI operations team for shop owner (shop_id={state.get('tenant_id')}).
{shop_type_hint}
You have specialized sub-agents available:
1. Receptionist - handles bookings, queue management, appointments, customer service
2. Finance Manager - handles revenue, analytics, POS/payments, invoicing, financial reporting
3. HR Assistant - handles employees, shifts, scheduling
4. CRM Assistant - handles client contacts, leads, companies, pipeline, notes, tasks

As the Supervisor, you:
- Help the owner manage their business via natural chat
- Route complex requests to appropriate sub-agents
- Provide summaries and recommendations
- Ask clarifying questions when needed

Always be helpful, concise, and professional.

If a specialist agent already produced raw output, synthesize it into:
1) direct answer,
2) notable evidence/metric,
3) next best action for owner."""
    
    # Invoke LLM
    # No fallback during stabilization — let LLM errors surface.
    response = llm.invoke([SystemMessage(content=system_prompt)] + llm_messages)
    
    # Add response to messages
    messages_with_response = messages + [response]
    _persist_conversation_turns(state, str(getattr(response, "content", "")))
    
    return {
        "messages": messages_with_response,
        "tool_results": state.get("tool_results")
    }


# ---------------------------------------------------------------------------
# HITL bridging — scan ReAct agent output for approval proposals
# ---------------------------------------------------------------------------

def _extract_pending_from_messages(messages) -> Optional[Dict[str, Any]]:
    """Scan tool messages (newest-first) for a ``requires_approval`` proposal.

    When a ReAct agent calls a proposal-only tool (e.g. close_queue), the
    ToolMessage content will contain a JSON dict with ``requires_approval: True``.
    This helper extracts the first such proposal so the supervisor can set
    ``pending_approval`` and let ``approval_gate`` handle the interrupt.
    """
    import json as _json

    for msg in reversed(list(messages)):
        # ToolMessages carry the tool return value
        if not hasattr(msg, "type") or getattr(msg, "type", None) != "tool":
            continue
        content = getattr(msg, "content", None)
        if content is None:
            continue
        # Content may be a JSON string or already a dict (depending on serialiser)
        parsed = content
        if isinstance(parsed, str):
            try:
                parsed = _json.loads(parsed)
            except (ValueError, TypeError):
                continue
        if isinstance(parsed, dict) and parsed.get("requires_approval"):
            return {
                "action": parsed.get("action"),
                "details": parsed.get("details", {}),
            }
    return None


def placeholder_receptionist(state: AgentState) -> dict:
    """
    Route to Receptionist ReAct agent.
    Invokes the receptionist tool-calling loop with tenant-scoped tools.
    After execution, checks for HITL proposal tools and bridges them
    into ``pending_approval`` so ``approval_gate`` can interrupt.
    """
    from .receptionist import create_receptionist_runnable

    shop_id = state.get("tenant_id", 0)
    receptionist = create_receptionist_runnable(shop_id=shop_id)

    # Sub-agent uses its own built-in schema; pass only messages
    result = receptionist.invoke({"messages": list(state.get("messages", []))})

    # Bridge proposal-only tools into the HITL approval flow
    pending = _extract_pending_from_messages(result.get("messages", []))
    if pending:
        pending["shop_id"] = shop_id
        return {
            "messages": result.get("messages", []),
            "current_agent": "receptionist",
            "pending_approval": pending,
            "needs_human_input": True,
        }

    return {
        "messages": result.get("messages", []),
        "current_agent": "receptionist",
    }


def placeholder_finance(state: AgentState) -> dict:
    """
    Route to Finance ReAct agent.
    Invokes the finance tool-calling loop with tenant-scoped tools.
    """
    from .finance import create_finance_runnable

    shop_id = state.get("tenant_id", 0)
    finance = create_finance_runnable(shop_id=shop_id)

    # Sub-agent uses its own built-in schema; pass only messages
    result = finance.invoke({"messages": list(state.get("messages", []))})

    return {
        "messages": result.get("messages", []),
        "current_agent": "finance",
    }


def placeholder_hr(state: AgentState) -> dict:
    """
    Route to HR ReAct agent.
    Invokes the HR tool-calling loop with tenant-scoped tools.
    After execution, checks for HITL proposal tools and bridges them
    into ``pending_approval`` so ``approval_gate`` can interrupt.
    """
    from .hr import create_hr_runnable

    shop_id = state.get("tenant_id", 0)
    hr = create_hr_runnable(shop_id=shop_id)

    # Sub-agent uses its own built-in schema; pass only messages
    result = hr.invoke({"messages": list(state.get("messages", []))})

    # Bridge proposal-only tools into the HITL approval flow
    pending = _extract_pending_from_messages(result.get("messages", []))
    if pending:
        pending["shop_id"] = shop_id
        return {
            "messages": result.get("messages", []),
            "current_agent": "hr",
            "pending_approval": pending,
            "needs_human_input": True,
        }

    return {
        "messages": result.get("messages", []),
        "current_agent": "hr",
    }


def _execute_approved_action(state: AgentState, pending: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a previously proposed high-impact action after owner approval."""
    action = pending.get("action")
    details = pending.get("details") or {}
    shop_id = state.get("tenant_id")

    if action == "close_queue":
        return booking_tools.close_queue(shop_id, details.get("reason") or "Owner approved closure")

    if action == "add_employee":
        return hr_tools.add_employee(
            shop_id=shop_id,
            name=details.get("name") or "New Employee",
            email=details.get("email") or f"employee_{shop_id}@zeroqwait.local",
            phone=details.get("phone"),
            role=details.get("role") or "employee",
        )

    return {"error": f"Unsupported approval action: {action}"}


def approval_gate(state: AgentState) -> dict:
    """
    HITL node: pauses graph when a sub-agent requests owner approval.

    Resume payload is expected as:
    {"approved": bool, "reason": str | None}
    """
    pending = state.get("pending_approval")
    if not pending:
        return {
            "needs_human_input": False,
            "pending_approval": None,
        }

    # Pause execution and emit the action payload for owner confirmation.
    decision = interrupt({
        "action": pending.get("action"),
        "details": pending.get("details", {}),
        "shop_id": pending.get("shop_id", state.get("tenant_id")),
    })

    approved = bool((decision or {}).get("approved", False))
    reason = (decision or {}).get("reason")

    if not approved:
        rejection_msg = AIMessage(
            content=f"Action '{pending.get('action')}' was rejected. No changes were made."
        )
        return {
            "messages": list(state.get("messages", [])) + [rejection_msg],
            "needs_human_input": False,
            "pending_approval": None,
            "tool_results": {
                "status": "rejected",
                "action": pending.get("action"),
                "reason": reason,
            },
        }

    execution_result = _execute_approved_action(state, pending)
    if execution_result.get("error"):
        execution_msg = AIMessage(
            content=f"Approval received, but the action failed: {execution_result.get('error')}"
        )
    else:
        execution_msg = AIMessage(
            content=f"Approval received. Action '{pending.get('action')}' was executed successfully."
        )

    return {
        "messages": list(state.get("messages", [])) + [execution_msg],
        "needs_human_input": False,
        "pending_approval": None,
        "tool_results": execution_result,
    }


def build_supervisor_graph():
    """
    Build the LangGraph StateGraph for the Supervisor agent.
    
    Graph flow:
    1. classify_intent - determine what owner is asking about
    2. plan_execution - build explicit execution plan
    3. route_to_agent - map plan to target specialist
    4. execute_plan - run specialist (or supervisor direct path)
    5. approval_gate - pause/resume high-impact actions
    6. synthesize_response - produce final owner-facing response
    7. END
    
    Returns:
        langgraph.graph.StateGraph instance ready to compile
    """
    
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("plan_execution", plan_execution)
    graph.add_node("route_to_agent", route_to_agent)
    graph.add_node("execute_plan", execute_plan)
    graph.add_node("approval_gate", approval_gate)
    graph.add_node("synthesize_response", synthesize_response)
    
    # Add edges
    graph.add_edge("classify_intent", "plan_execution")
    graph.add_edge("plan_execution", "route_to_agent")
    graph.add_edge("route_to_agent", "execute_plan")
    graph.add_edge("execute_plan", "approval_gate")
    graph.add_edge("approval_gate", "synthesize_response")

    # Final synthesis leads to END.
    graph.add_edge("synthesize_response", END)
    
    # Set entry point
    graph.set_entry_point("classify_intent")
    
    return graph


def create_supervisor_runnable(checkpointer=None):
    """
    Compile the Supervisor graph into an executable runnable.
    
    Returns:
        Compiled LangGraph runnable (sync version for now)
    """
    graph = build_supervisor_graph()
    return graph.compile(checkpointer=checkpointer)


async def create_supervisor_runnable_async(checkpointer=None):
    """
    Async version of supervisor runnable.
    
    Returns:
        Compiled LangGraph runnable (async version)
    """
    graph = build_supervisor_graph()
    return graph.compile(checkpointer=checkpointer)


__all__ = [
    "build_supervisor_graph",
    "create_supervisor_runnable",
    "create_supervisor_runnable_async",
    "AgentState"
]
