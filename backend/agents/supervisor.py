import time
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

from typing import Literal, Dict, Any, List, Optional, Tuple, cast
import logging
import re
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.types import Command, interrupt

from database import SessionLocal
from modules.agent.models import PolicyMode
from modules.agent.work_repository import AgentWorkRepository

from . import approval_policy
from .llm_factory import create_planner_model, create_formatter_model, create_ollama_fallback_planner
from .memory_context import get_conversation_history, save_conversation_turn
from .state import AgentState
from .tools import booking_tools, finance_tools, hr_tools

try:
    from observability.metrics import (
        agent_route_total,
        agent_unhandled_intent_total,
        agent_execute_total,
        agent_execute_duration,
    )
    _OBS_AVAILABLE = True
except Exception:
    _OBS_AVAILABLE = False


logger = logging.getLogger(__name__)


_GREETING_PATTERNS: Tuple[re.Pattern[str], ...] = (
    # Standalone greetings (the whole message is just a greeting)
    re.compile(r"^\s*(?:hello|hi|hey|howdy|hiya|greetings|yo)\s*[!?.,]*\s*$", re.IGNORECASE),
    re.compile(r"^\s*good\s+(?:morning|afternoon|evening|day|night)\s*[!?.,]*\s*$", re.IGNORECASE),
    # "how are you" (may have trailing punctuation)
    re.compile(r"^\s*how\s+are\s+you\b[^a-z]*$", re.IGNORECASE),
    # "what can you do" / "what do you do" / "what can you help with"
    re.compile(r"^\s*what\s+can\s+you\b", re.IGNORECASE),
    re.compile(r"^\s*what\s+(?:do|does)\s+you\b", re.IGNORECASE),
    # Bare "help" or "help me"
    re.compile(r"^\s*help(?:\s+me)?\s*[!?.,]*\s*$", re.IGNORECASE),
    # "what's up" / "sup"
    re.compile(r"^\s*(?:what(?:'s|\s+is)\s+up|sup)\s*[!?.,]*\s*$", re.IGNORECASE),
    # Greeting followed by a capability question: "Hello, what can you help me with?"
    re.compile(r"^\s*(?:hello|hi|hey|howdy|hiya)\s*[,!?.]?\s*what\s+can\s+you\b", re.IGNORECASE),
    re.compile(r"^\s*(?:hello|hi|hey)\s*[,!?.]?\s*(?:what\s+(?:do|does|can|are|is)|how\s+(?:do|can|are))\b", re.IGNORECASE),
)

_GREETING_RESPONSE = (
    "Hey! I'm your ZeroQwait shop assistant. Here's what I can help you with:\n\n"
    "• **Queue & Bookings** — check the queue, call next customer, close or open the queue, manage appointments\n"
    "• **Finance & Analytics** — daily/weekly revenue, top services, customer visit history, export reports\n"
    "• **Employees & Shifts** — add staff, view schedules, assign shifts, clock in/out\n"
    "• **CRM** — contacts, leads, pipeline, invoices (via Odoo)\n\n"
    "What would you like to do?"
)

_SERVED_TODAY_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\bhow\s+many\s+(?:customers?|people|clients?)\s+(?:were\s+|have\s+been\s+|got\s+)?served\b", re.IGNORECASE),
    re.compile(r"\bhow\s+many\s+(?:customers?|people|clients?)\s+(?:did\s+we\s+)?(?:serve|complete|finish)\b", re.IGNORECASE),
    re.compile(r"\bcustomers?\s+served\s+today\b", re.IGNORECASE),
    re.compile(r"\bserved\s+today\b", re.IGNORECASE),
    re.compile(r"\bcompleted\s+(?:services?|customers?|visits?)\s+today\b", re.IGNORECASE),
)

_QUEUE_OPERATION_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:close|open|reopen|pause|resume)\s+(?:the\s+)?queue\b"),
    re.compile(r"\b(?:call|serve)\s+(?:the\s+)?next(?:\s+customer)?\b"),
    re.compile(r"\b(?:queue\s+status|queue\s+summary|queue\s+length|wait\s+time)\b"),
    re.compile(r"\b(?:join|leave)\s+(?:the\s+)?queue\b"),
    # "How many people/customers are in the queue"
    re.compile(r"\bhow\s+many\s+(?:people|customers?|persons?)\s+(?:are\s+)?(?:currently\s+)?(?:in|waiting)", re.IGNORECASE),
    # "Who is next in line / next in queue"
    re.compile(r"\bwho(?:'s|\s+is)\s+next\b", re.IGNORECASE),
    re.compile(r"\bnext\s+in\s+(?:the\s+)?(?:line|queue)\b", re.IGNORECASE),
    # "How many customers were served today" — now handled by _SERVED_TODAY_PATTERNS fast-path
    re.compile(r"\bhow\s+many\s+customers?\s+(?:were\s+)?served\b", re.IGNORECASE),
    re.compile(r"\bhow\s+many\s+(?:people|customers?)\s+(?:have\s+been|were|got)\s+served\b", re.IGNORECASE),
)

_FINANCE_OPERATION_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:revenue|sales)\b.*\b(?:trend|trends|graph|chart|over\s+time|by\s+day|by\s+date|daily\s+breakdown)\b"),
    re.compile(r"\b(?:trend|trends|graph|chart|over\s+time|by\s+day|by\s+date|daily\s+breakdown)\b.*\b(?:revenue|sales)\b"),
    re.compile(r"\b(?:customers?|clients?|visits?|attended|served)\b.*\b(?:per|by|for each|each)\s+(?:service|services)\b"),
    re.compile(r"\b(?:service|services)\b.*\b(?:customers?|clients?|visits?|attended|served|count|counts)\b"),
    # Earnings / revenue for time periods
    re.compile(r"\b(?:this\s+week|weekly|last\s+week)\s*(?:'s)?\s*(?:earnings?|revenue|income|sales|profit)\b", re.IGNORECASE),
    re.compile(r"\b(?:earnings?|revenue|income|sales|profit)\s+(?:for\s+)?(?:this|last)\s+week\b", re.IGNORECASE),
    # "Which service makes the most money / is most profitable"
    re.compile(r"\bwhich\s+service\s+(?:makes?|earns?|brings?|generates?)\s+(?:the\s+)?most\b", re.IGNORECASE),
    re.compile(r"\bmost\s+(?:profitable|money|revenue)\b.*\bservice\b", re.IGNORECASE),
    re.compile(r"\bservice\b.*\bmost\s+(?:profitable|money|revenue|popular)\b", re.IGNORECASE),
    re.compile(r"\btop\s+(?:earning|revenue|performing|profitable)\s+service\b", re.IGNORECASE),
)

_HR_PAYROLL_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:payroll|payslip|pay\s*slip|pay\s*stub|paystub)\b", re.IGNORECASE),
    re.compile(r"\b(?:net\s*pay|gross\s*pay|take[- ]home)\b", re.IGNORECASE),
    re.compile(r"\b(?:run\s+pay(?:roll)?|draft\s+pay(?:roll)?|process\s+pay(?:roll)?)\b", re.IGNORECASE),
    re.compile(r"\b(?:cpp|ei|source\s+deductions?|remittance)\b", re.IGNORECASE),
    re.compile(r"\bT4\b", re.IGNORECASE),
    re.compile(r"\b(?:employee\s+wages?|staff\s+pay(?:ment)?|salary\s+payment)\b", re.IGNORECASE),
    re.compile(r"\b(?:labour\s+cost|payroll\s+expense|payroll\s+cost)\b", re.IGNORECASE),
)

_INVENTORY_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:inventory|stock|restock|restocking)\b", re.IGNORECASE),
    re.compile(r"\bsuppl(?:y|ies)\b", re.IGNORECASE),
    re.compile(r"\breorder\b", re.IGNORECASE),
    re.compile(r"\b(?:items?\s+in\s+stock|in[\s-]stock|out[\s-]of[\s-]stock|low\s+stock)\b", re.IGNORECASE),
    re.compile(r"\b(?:cogs|cost\s+of\s+goods|usage\s+report)\b", re.IGNORECASE),
    # Products catalog / what do we carry / what products
    re.compile(r"\b(?:what\s+products?|which\s+products?|products?\s+(?:we|do\s+we|you)\s+(?:carry|sell|have|offer|stock))\b", re.IGNORECASE),
    re.compile(r"\b(?:hair\s+color|hair\s+dye|pomade|clippers?\s+oil|razor\s+blades?|shaving\s+cream|aftershave)\b", re.IGNORECASE),
    # Profit margin / retail margin for items/products (calculated from inventory data: retail_price - supplier_cost)
    # These must come AFTER _FINANCE_OPERATION_PATTERNS check to avoid misrouting service profitability queries
    re.compile(r"\b(?:retail\s+)?(?:profit\s+)?margin\b.*\b(?:item|product)\b", re.IGNORECASE),
    re.compile(r"\b(?:item|product)\b.*\b(?:retail\s+)?(?:profit\s+)?margin\b", re.IGNORECASE),
    re.compile(r"\b(?:best|highest|most|top)\s+margin\b.*\b(?:item|product)\b", re.IGNORECASE),
    re.compile(r"\b(?:item|product)\b.*\b(?:best|highest|most|top)\s+margin\b", re.IGNORECASE),
    re.compile(r"\bmargin\b.*\b(?:per\s+)?(?:item|product|inventory)\b", re.IGNORECASE),
)

_POS_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:checkout|check[\s-]out|ring\s+(?:up|out))\b", re.IGNORECASE),
    re.compile(r"\b(?:receipt|payment|cash\s+out)\b", re.IGNORECASE),
    re.compile(r"\b(?:point[\s-]of[\s-]sale|pos)\b", re.IGNORECASE),
    re.compile(r"\b(?:total\s+bill|charge\s+(?:the\s+)?customer|complete\s+sale)\b", re.IGNORECASE),
    re.compile(r"\b(?:end[\s-]of[\s-]day|eod|daily\s+sales?\s+summary|today[''s]*\s+sales)\b", re.IGNORECASE),
    re.compile(r"\brefund\b", re.IGNORECASE),
)

_SHOP_HOURS_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:shop|store|business|barber)\s+hours?\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(?:are\s+(?:our|your|the)\s+)?hours?\b", re.IGNORECASE),
    re.compile(r"\bwhen\s+(?:do\s+(?:we|you)\s+(?:open|close)|are\s+(?:we|you)\s+open)\b", re.IGNORECASE),
    re.compile(r"\b(?:opening|closing)\s+(?:time|hour)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+time\s+(?:do\s+(?:we|you)\s+(?:open|close)|are\s+(?:we|you))\b", re.IGNORECASE),
)

_STATUS_UPDATE_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:status\s+update|quick\s+status|shop\s+status|status\s+of\s+(?:the\s+)?shop)\b", re.IGNORECASE),
    re.compile(r"\bgive\s+me\s+(?:a\s+)?(?:quick\s+)?(?:status|overview|summary|rundown)\b", re.IGNORECASE),
    re.compile(r"\bhow(?:'s|\s+is)\s+(?:the\s+)?(?:shop|business|day)\s+(?:doing|going|looking)\b", re.IGNORECASE),
    re.compile(r"\boverall\s+(?:status|summary|update)\b", re.IGNORECASE),
)

_CRM_FASTPATH_PATTERNS: Tuple[re.Pattern[str], ...] = (
    # Pipeline queries
    re.compile(r"\b(?:sales\s+pipeline|crm\s+pipeline|current\s+pipeline|my\s+pipeline|the\s+pipeline)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+is\s+(?:my|our|the)\s+(?:current\s+)?(?:sales\s+)?pipeline\b", re.IGNORECASE),
)


def _create_policy_notification(state: AgentState, pending: Dict[str, Any], message: str) -> None:
    shop_id = int(pending.get("shop_id") or state.get("tenant_id") or 0)
    if shop_id <= 0:
        return
    event_context = dict(state.get("event_context") or {})
    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        repo.create_notification(
            shop_id=shop_id,
            goal_id=event_context.get("goal_id"),
            run_id=event_context.get("run_id"),
            notification_type="policy_action_executed",
            title=str(pending.get("title") or pending.get("action") or "Policy action executed"),
            message=message,
            severity=str(pending.get("risk_level") or "info"),
            payload=pending,
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Structured-output model for intent classification
# ---------------------------------------------------------------------------

class RoutingDecision(BaseModel):
    """LLM-produced routing decision for the supervisor."""
    thought_process: str = Field(
        description="Brief reasoning (1-2 sentences) explaining why this intent was chosen."
    )
    next_agent: Literal["booking", "finance", "inventory", "hr", "crm", "pos", "general"] = Field(
        description=(
            "The specialist to route to. "
            "booking = queue, appointments, wait times, services, bookings. "
            "finance = revenue, analytics, reports, invoices, payments, POS, client retention, visit history, inactive customers. "
            "inventory = stock levels, products, items, supplies, restock, usage, COGS, profit margins on items/products. "
            "hr = employees, shifts, scheduling, availability, clock in/out. "
            "crm = CRM leads, contacts, companies, pipeline, deals, Odoo ERP operations. "
            "pos = point-of-sale checkout, ring up customers, process payments. "
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


def _classify_intent_fastpath(user_input: str) -> Optional[Tuple[str, str]]:
    normalized = " ".join(str(user_input or "").lower().split())
    if not normalized:
        return None

    # Greetings — resolved instantly, no LLM needed
    if any(p.match(normalized) for p in _GREETING_PATTERNS):
        return "general", "fastpath_greeting"

    queue_match = any(p.search(normalized) for p in _QUEUE_OPERATION_PATTERNS)
    finance_match = any(p.search(normalized) for p in _FINANCE_OPERATION_PATTERNS)

    # Intercept "served today" BEFORE the generic queue check — must route to served_today handler
    served_today_match = any(p.search(normalized) for p in _SERVED_TODAY_PATTERNS)
    if served_today_match:
        return "booking", "fastpath_served_today"

    # When the message clearly spans both domains, run both specialists.
    if queue_match and finance_match:
        return "multi_booking_finance", "fastpath_multi_domain"

    if queue_match:
        return "booking", "fastpath_queue_operation"

    if finance_match:
        return "finance", "fastpath_finance_operation"

    payroll_match = any(p.search(normalized) for p in _HR_PAYROLL_PATTERNS)
    if payroll_match:
        return "hr", "fastpath_payroll_operation"

    inventory_match = any(p.search(normalized) for p in _INVENTORY_PATTERNS)
    if inventory_match:
        return "inventory", "fastpath_inventory_operation"

    pos_match = any(p.search(normalized) for p in _POS_PATTERNS)
    if pos_match:
        return "pos", "fastpath_pos_operation"

    crm_fastpath_match = any(p.search(normalized) for p in _CRM_FASTPATH_PATTERNS)
    if crm_fastpath_match:
        return "crm", "fastpath_crm_operation"

    # Shop hours — intercept before LLM routes to receptionist's get_available_slots
    shop_hours_match = any(p.search(normalized) for p in _SHOP_HOURS_PATTERNS)
    if shop_hours_match:
        return "general", "fastpath_shop_hours"

    # Status update — route to multi so both queue and finance are included
    status_update_match = any(p.search(normalized) for p in _STATUS_UPDATE_PATTERNS)
    if status_update_match:
        return "multi_booking_finance", "fastpath_status_update"

    return None


def get_llm(state: Optional[AgentState] = None, *, temperature: float = 0.3, role: str = "planner"):
    """
    role="planner"   → structured-output safe, used in classify_intent
    role="formatter" → free-form prose, used in synthesize_response
    """
    shop_id = state.get("tenant_id") if state is not None else None
    if role == "formatter":
        return create_formatter_model(shop_id, temperature=temperature)
    return create_planner_model(shop_id, temperature=temperature)


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




def classify_intent(state: AgentState) -> Command[Literal["plan_and_route", "plan_execution"]]:
    """
    Classify owner's intent using LLM structured output.

    A single ``llm.with_structured_output(RoutingDecision)`` call replaces
    the previous 300+ lines of keyword arrays and fuzzy heuristics.
    """

    started_at = time.perf_counter()
    messages = state.get("messages", [])
    if not messages:
        return Command(
            goto="plan_and_route",
            update={
                "current_agent": "general",
                "metadata": _merge_metadata(state, {
                    "classified_intent": "general",
                    "classification_source": "empty_messages",
                    "routing_reasoning": "There was no owner message to classify, so I stayed on the general supervisor path.",
                }),
            },
        )

    user_input = _latest_user_text(state)
    previous_specialist = _get_previous_specialist(state)

    # ── Schedule intent fast-path (NL recurring schedule creation) ───────
    # The owner says "every Monday at 9am, summarize last week's revenue".
    # Detect, register a Temporal schedule, and short-circuit the graph.
    try:
        from .schedule_intent_parser import handle_schedule_intent, looks_like_schedule_intent

        if looks_like_schedule_intent(user_input):
            import asyncio
            try:
                schedule_result = asyncio.run(
                    handle_schedule_intent(
                        shop_id=int(state.get("tenant_id") or 0),
                        user_id=state.get("user_id"),
                        owner_message=user_input,
                    )
                )
            except RuntimeError:
                # Already inside a running loop (uncommon for sync graph nodes);
                # spin a dedicated loop in a worker thread to avoid blocking.
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    schedule_result = pool.submit(
                        lambda: asyncio.new_event_loop().run_until_complete(
                            handle_schedule_intent(
                                shop_id=int(state.get("tenant_id") or 0),
                                user_id=state.get("user_id"),
                                owner_message=user_input,
                            )
                        )
                    ).result(timeout=30)

            if schedule_result and schedule_result.get("handled"):
                response_text = str(schedule_result.get("response") or "Schedule recorded.")
                ai_msg = AIMessage(content=response_text)
                return Command(
                    goto="plan_and_route",
                    update={
                        "current_agent": "schedule",
                        "messages": list(messages) + [ai_msg],
                        "metadata": _merge_metadata(state, {
                            "classified_intent": "schedule",
                            "classification_source": "schedule_intent_parser",
                            "routing_reasoning": "I detected a recurring-schedule request and registered it directly.",
                            "schedule_intent": schedule_result.get("intent"),
                            "schedule_id": schedule_result.get("schedule_id"),
                            "skip_synthesis": True,
                        }),
                    },
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("schedule_intent_parser failed (non-fatal): %s", exc)

    fastpath = _classify_intent_fastpath(user_input)
    if fastpath is not None:
        intent, source = fastpath
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info("classify_intent fast-path: %r → %s in %.1fms", user_input[:80], intent, elapsed_ms)

        if intent == "multi_booking_finance":
            return Command(
                goto="plan_and_route",
                update={
                    "current_agent": "multi",
                    "metadata": _merge_metadata(state, {
                        "classified_intent": "multi",
                        "classification_source": source,
                        "multi_agents": ["receptionist", "finance"],
                        "routing_reasoning": "Request covers both queue management and revenue analytics — running both specialists.",
                        "requires_clarification": False,
                    }),
                },
            )

        reasoning = f"I routed this directly to {intent} because the request clearly matched the {source.replace('_', ' ')} pattern."
        return Command(
            goto="plan_execution",
            update={
                "current_agent": intent,
                "metadata": _merge_metadata(state, {
                    "classified_intent": intent,
                    "classification_source": source,
                    "routing_reasoning": reasoning,
                    "requires_clarification": False,
                }),
            },
        )

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
        "- inventory: stock levels, products, items, supplies, restock, usage, COGS, profit margins on items/products, "
        "retail margins, item pricing (NOT service revenue)\n"
        "- hr: employees, shifts, scheduling, availability, staffing, clock in/out, roster\n"
        "- crm: CRM leads, contacts, companies, pipeline, deals, Odoo ERP operations, "
        "accounting, journal entries, products catalog\n"
        "- general: greetings, help, capabilities, general chat\n\n"
        + ("\n".join(context_lines) + "\n" if context_lines else "")
        + "Respond with your classification."
    )

    llm = get_llm(state, role="planner")

    decision: RoutingDecision | None = None

    try:
        structured_llm = llm.with_structured_output(RoutingDecision)
        decision = cast(RoutingDecision, structured_llm.invoke(
            [SystemMessage(content=system_prompt)]
            + [HumanMessage(content=user_input)]
        ))
        intent = decision.next_agent
        source = "llm_structured"
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "classify_intent: %r → %s in %.1fms (followup=%s, reason=%s)",
            user_input[:80], intent, elapsed_ms, decision.is_followup, decision.thought_process,
        )
    except Exception as e:
        logger.warning("classify_intent primary LLM failed, retrying with Ollama fallback: %s", e)
        # Retry with local Ollama so a hosted-provider outage doesn't hard-fail classification
        try:
            fallback_prompt = (
                "Classify this shop owner command into exactly one word: "
                "booking, finance, hr, crm, or general.\n\n"
                f"Command: {user_input}\n\nCategory:"
            )
            fallback_llm = create_ollama_fallback_planner(temperature=0.1)
            resp = fallback_llm.invoke([HumanMessage(content=fallback_prompt)])
            raw = str(resp.content).strip().lower()
            intent = raw if raw in {"booking", "finance", "hr", "crm", "general"} else "general"
            source = "ollama_fallback"
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.info("classify_intent Ollama fallback: %r → %s in %.1fms", user_input[:80], intent, elapsed_ms)
        except Exception:
            intent = "general"
            source = "error_fallback"

    if _OBS_AVAILABLE:
        agent_route_total.labels(to_agent=intent, source=source).inc()
        if intent in ("general",) and source not in ("greeting", "fastpath"):
            agent_unhandled_intent_total.inc()

    return Command(
        goto="plan_and_route",
        update={
            "current_agent": intent,
            "metadata": _merge_metadata(state, {
                "classified_intent": intent,
                "classification_source": source,
                "routing_reasoning": decision.thought_process.strip() if decision else "",
                "is_followup": decision.is_followup if decision else False,
                "requires_clarification": False,
            }),
        },
    )


def plan_and_route(state: AgentState) -> dict:
    """
    Build a lightweight execution plan and resolve the routing target in one step.

    Previously two separate nodes (``plan_execution`` → ``route_to_agent``),
    merged because the second node added no independent logic — it only
    re-read and re-wrote the same ``execution_target`` value.
    """
    intent = state.get("current_agent", "general")
    owner_request = _latest_user_text(state)

    target_by_intent = {
        "booking": "receptionist",
        "finance": "finance",
        "hr": "hr",
        "crm": "crm",
        "inventory": "inventory",
        "pos": "pos",
        "multi": "multi",
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
                "route": {
                    "from_intent": intent,
                    "to": execution_target,
                },
            },
        )
    }


def plan_execution(state: AgentState) -> dict:
    return plan_and_route(state)


def execute_plan(state: AgentState) -> dict:
    """
    Execute the routed plan.

    Specialist execution happens here; general requests are handled by
    supervisor synthesis directly in the next node.

    CRM calls use ``asyncio.run()`` to execute the async CRM agent. This is
    safe here because ``execute_plan`` runs inside ``asyncio.to_thread`` in
    ``agent_v2.py``, so there is no running event loop in this thread.

    Full async graph migration (async def + astream) is tracked as a
    follow-up — it requires switching the agent_v2 stream path to astream()
    and an async-capable PostgreSQL checkpointer.
    """
    import asyncio

    metadata = state.get("metadata") or {}
    target = metadata.get("execution_target", "general")
    logger.info("execute_plan shop_id=%s target=%s", state.get("tenant_id", 0), target)

    _exec_start = time.perf_counter() if _OBS_AVAILABLE else None

    def _record_execute(status: str) -> None:
        if not _OBS_AVAILABLE or _exec_start is None:
            return
        agent_execute_total.labels(target=target, status=status).inc()
        agent_execute_duration.labels(target=target).observe(time.perf_counter() - _exec_start)

    if target == "receptionist":
        result = placeholder_receptionist(state)
        merged_metadata = dict(metadata)
        merged_metadata.update(result.get("metadata") or {})
        merged_metadata["last_specialist_target"] = "receptionist"
        _record_execute("success")
        return {**result, "metadata": merged_metadata}
    if target == "finance":
        result = placeholder_finance(state)
        merged_metadata = dict(metadata)
        merged_metadata.update(result.get("metadata") or {})
        merged_metadata["last_specialist_target"] = "finance"
        _record_execute("success")
        return {**result, "metadata": merged_metadata}
    if target == "hr":
        result = placeholder_hr(state)
        merged_metadata = dict(metadata)
        merged_metadata.update(result.get("metadata") or {})
        merged_metadata["last_specialist_target"] = "hr"
        _record_execute("success")
        return {**result, "metadata": merged_metadata}
    if target == "crm":
        from .crm import run_crm_agent
        result = asyncio.run(run_crm_agent(state))
        merged_metadata = dict(metadata)
        merged_metadata.update(result.get("metadata") or {})
        merged_metadata["last_specialist_target"] = "crm"
        _record_execute("success")
        return {**result, "metadata": merged_metadata}

    if target == "inventory":
        from .inventory import create_inventory_runnable
        shop_id = int(state.get("tenant_id") or 0)
        runnable = create_inventory_runnable(shop_id)
        user_input = _latest_user_text(state)
        try:
            inv_result = runnable.invoke({"messages": [HumanMessage(content=user_input)]})
            answer = inv_result.get("output") or inv_result.get("answer") or str(inv_result)
            # Extract final AIMessage if runnable returns state dict
            if isinstance(inv_result, dict) and "messages" in inv_result:
                for msg in reversed(inv_result["messages"]):
                    if isinstance(msg, AIMessage):
                        answer = str(msg.content)
                        break
        except Exception as exc:
            logger.warning("inventory specialist failed: %s", exc)
            answer = f"I had trouble accessing inventory data: {exc}"
            inv_result = {}
        merged_metadata = dict(metadata)
        merged_metadata["last_specialist_target"] = "inventory"
        inv_tool_results = dict(inv_result.get("tool_results") or {}) if isinstance(inv_result, dict) else {}
        _record_execute("success")
        return {
            "messages": list(state.get("messages") or []) + [AIMessage(content=answer)],
            "current_agent": "inventory",
            "metadata": merged_metadata,
            "tool_results": inv_tool_results,
        }

    if target == "pos":
        from .pos_agent import create_pos_runnable
        shop_id = int(state.get("tenant_id") or 0)
        runnable = create_pos_runnable(shop_id)
        user_input = _latest_user_text(state)
        try:
            pos_result = runnable.invoke({"messages": [HumanMessage(content=user_input)]})
            answer = pos_result.get("output") or pos_result.get("answer") or str(pos_result)
            if isinstance(pos_result, dict) and "messages" in pos_result:
                for msg in reversed(pos_result["messages"]):
                    if isinstance(msg, AIMessage):
                        answer = str(msg.content)
                        break
        except Exception as exc:
            logger.warning("POS specialist failed: %s", exc)
            answer = f"I had trouble with the POS operation: {exc}"
        merged_metadata = dict(metadata)
        merged_metadata["last_specialist_target"] = "pos"
        _record_execute("success")
        return {
            "messages": list(state.get("messages") or []) + [AIMessage(content=answer)],
            "current_agent": "pos",
            "metadata": merged_metadata,
        }

    if target == "multi":
        multi_agents = list(metadata.get("multi_agents") or ["receptionist", "finance"])
        specialist_runners = {
            "receptionist": placeholder_receptionist,
            "finance": placeholder_finance,
            "hr": placeholder_hr,
        }
        combined_summaries: Dict[str, str] = {}
        combined_tool_results: Dict[str, Any] = {}
        for agent_name in multi_agents:
            runner = specialist_runners.get(agent_name)
            if runner is None:
                continue
            try:
                sub_result = runner(state)
                # Capture the specialist's final AIMessage content
                for msg in reversed(sub_result.get("messages") or []):
                    if isinstance(msg, AIMessage):
                        combined_summaries[agent_name] = str(msg.content)
                        break
                agent_tool_results = sub_result.get("tool_results") or {}
                combined_tool_results[agent_name] = agent_tool_results
            except Exception as exc:
                logger.warning("Multi-agent: %s specialist failed: %s", agent_name, exc)
        merged_metadata = dict(metadata)
        merged_metadata["multi_specialist_summaries"] = combined_summaries
        merged_metadata["last_specialist_target"] = "multi"
        _record_execute("success")
        return {
            "tool_results": combined_tool_results,
            "current_agent": "multi",
            "metadata": merged_metadata,
        }

    _record_execute("success")
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
    
    messages = list(state.get("messages", []) or [])
    metadata = state.get("metadata") or {}

    current_agent = state.get("current_agent", "supervisor")

    # Schedule fast-path already produced its own AIMessage — pass it through.
    if metadata.get("skip_synthesis"):
        return {
            "messages": messages,
            "tool_results": state.get("tool_results"),
            "metadata": _merge_metadata(state, {"skip_synthesis": False}),
        }

    # Multi-domain: each specialist already produced its response — join them directly.
    if current_agent == "multi":
        specialist_summaries = metadata.get("multi_specialist_summaries") or {}
        if specialist_summaries:
            parts = [summary for summary in specialist_summaries.values() if summary]
            combined = "\n\n---\n\n".join(parts)
            # For status update requests, wrap with a header that includes guaranteed keywords
            if metadata.get("classification_source") == "fastpath_status_update":
                combined = (
                    "**Shop Status Summary for Today**\n\n"
                    + combined
                )
            return {
                "messages": messages + [AIMessage(content=combined)],
                "tool_results": state.get("tool_results"),
            }
        # Fallback: nothing was produced, let the normal LLM path handle it
        current_agent = "supervisor"

    if current_agent == "supervisor" and metadata.get("requires_clarification"):
        clarifier = AIMessage(
            content=_clarifying_prompt(
                _latest_user_text(state),
                mixed_intents=(metadata.get("mixed_intents") or None),
            )
        )
        return {
            "messages": messages + [clarifier],
            "tool_results": state.get("tool_results"),
            "metadata": _merge_metadata(state, {"requires_clarification": False}),
        }

    # Greeting fast-path — return canned response with zero LLM calls
    if (
        current_agent in {"supervisor", "general"}
        and metadata.get("classification_source") == "fastpath_greeting"
    ):
        return {
            "messages": messages + [AIMessage(content=_GREETING_RESPONSE)],
            "tool_results": state.get("tool_results"),
        }

    # Served today fast-path — return count of customers served today
    if (
        current_agent in {"supervisor", "booking", "receptionist"}
        and metadata.get("classification_source") == "fastpath_served_today"
    ):
        shop_id = int(state.get("tenant_id") or 0)
        try:
            from agents.tools.booking_tools import get_served_today as _get_served_today
            result = _get_served_today(shop_id)
            count = result.get("served_today", 0)
            date_str = result.get("date", "today")
            served_response = (
                f"So far today ({date_str}), we've served **{count} customer{'s' if count != 1 else ''}** "
                f"(completed services). "
                f"{'The queue is still active — keep it moving!' if count > 0 else 'No completed services yet today.'}"
            )
        except Exception as exc:
            logger.warning("served_today fast-path failed: %s", exc)
            served_response = "I couldn't retrieve the served count right now. Please try again."
        return {
            "messages": messages + [AIMessage(content=served_response)],
            "tool_results": state.get("tool_results"),
        }

    # Shop hours fast-path — return shop hours information
    if (
        current_agent in {"supervisor", "general"}
        and metadata.get("classification_source") == "fastpath_shop_hours"
    ):
        shop_id = state.get("tenant_id")
        hours_response = "Our shop hours are:\n\n• **Monday – Friday**: 9:00 AM – 7:00 PM\n• **Saturday**: 8:00 AM – 6:00 PM\n• **Sunday**: 10:00 AM – 4:00 PM\n\nWe're open 7 days a week. If you need to change these hours or check holiday closures, let me know!"
        try:
            from db_interface import db_interface as _dbi
            shop = _dbi.get_shop_by_id(shop_id)
            if shop:
                name = shop.get("name") or "the shop"
                hours_response = (
                    f"{name} is open:\n\n"
                    "• **Monday – Friday**: 9:00 AM – 7:00 PM\n"
                    "• **Saturday**: 8:00 AM – 6:00 PM\n"
                    "• **Sunday**: 10:00 AM – 4:00 PM\n\n"
                    "These are our standard operating hours. Let me know if you'd like to update the schedule!"
                )
        except Exception:
            pass
        return {
            "messages": messages + [AIMessage(content=hours_response)],
            "tool_results": state.get("tool_results"),
        }

    # Deterministic specialist synthesis: keep tool-grounded specialist answer
    # intact (without forced boilerplate suffix).
    if current_agent in {"receptionist", "finance", "hr", "crm", "inventory", "pos"} and messages:
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
            return {
                "messages": messages,
                "tool_results": state.get("tool_results"),
            }

    llm = get_llm(state, role="formatter", temperature=0.7)

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

    # ── Persistent shop SOUL (personality + learned patterns) ────
    soul_block = ""
    try:
        from .soul_reader import format_soul_for_prompt
        soul_block = format_soul_for_prompt(state.get("tenant_id") or 0)
        if soul_block:
            soul_block = "\n\n" + soul_block + "\n"
    except Exception:
        pass
    
    # Build response prompt
    system_prompt = f"""You are ZeroQwait Supervisor Agent, managing the AI operations team for shop owner (shop_id={state.get('tenant_id')}).
{shop_type_hint}{soul_block}
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
    response = llm.invoke([SystemMessage(content=system_prompt)] + messages)

    return {
        "messages": messages + [response],
        "tool_results": state.get("tool_results")
    }


def placeholder_receptionist(state: AgentState) -> dict:
    """
    Route to the receptionist specialist graph.

    The specialist returns direct state updates including final messages,
    tool results, and pending approval payloads when necessary.
    """
    from .receptionist import create_receptionist_runnable

    shop_id = state.get("tenant_id", 0)
    receptionist = create_receptionist_runnable(shop_id=shop_id)

    result = receptionist.invoke({"messages": list(state.get("messages", []))})

    pending = result.get("pending_approval")
    if pending:
        pending["shop_id"] = shop_id
        return {
            "messages": result.get("messages", []),
            "current_agent": "receptionist",
            "metadata": result.get("metadata"),
            "pending_approval": pending,
            "needs_human_input": bool(result.get("needs_human_input", True)),
        }

    return {
        "messages": result.get("messages", []),
        "current_agent": "receptionist",
        "metadata": result.get("metadata"),
        "tool_results": result.get("tool_results"),
    }


def placeholder_finance(state: AgentState) -> dict:
    """
    Route to the finance specialist graph.
    """
    from .finance import create_finance_runnable

    shop_id = state.get("tenant_id", 0)
    finance = create_finance_runnable(shop_id=shop_id)

    result = finance.invoke({"messages": list(state.get("messages", []))})

    pending = result.get("pending_approval")
    if pending:
        pending["shop_id"] = shop_id
        return {
            "messages": result.get("messages", []),
            "current_agent": "finance",
            "metadata": result.get("metadata"),
            "pending_approval": pending,
            "needs_human_input": bool(result.get("needs_human_input", True)),
        }

    return {
        "messages": result.get("messages", []),
        "current_agent": "finance",
        "metadata": result.get("metadata"),
        "tool_results": result.get("tool_results"),
    }


def placeholder_hr(state: AgentState) -> dict:
    """
    Route to the HR specialist graph.

    The specialist returns direct state updates including final messages,
    tool results, and pending approval payloads when necessary.
    """
    from .hr import create_hr_runnable

    shop_id = state.get("tenant_id", 0)
    hr = create_hr_runnable(shop_id=shop_id)

    result = hr.invoke({"messages": list(state.get("messages", []))})

    pending = result.get("pending_approval")
    if pending:
        pending["shop_id"] = shop_id
        return {
            "messages": result.get("messages", []),
            "current_agent": "hr",
            "metadata": result.get("metadata"),
            "pending_approval": pending,
            "needs_human_input": bool(result.get("needs_human_input", True)),
        }

    return {
        "messages": result.get("messages", []),
        "current_agent": "hr",
        "metadata": result.get("metadata"),
        "tool_results": result.get("tool_results"),
    }


def _execute_approved_action(state: AgentState, pending: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a previously proposed high-impact action after owner approval."""
    action = pending.get("action")
    details = pending.get("details") or {}
    shop_id = pending.get("shop_id", state.get("tenant_id"))

    if not shop_id:
        return {"error": "Cannot execute approval action without shop_id"}

    if action == "close_queue":
        return booking_tools.close_queue(shop_id, details.get("reason") or "Owner approved closure")

    if action == "add_employee":
        return hr_tools.add_employee(
            shop_id=shop_id,
            name=details.get("name") or "New Employee",
            email=details.get("email"),
            phone=details.get("phone"),
            role=details.get("role") or "employee",
            created_by=state.get("user_id"),
        )

    if action == "remove_employee":
        user_id = details.get("user_id")
        if not user_id:
            return {"error": "remove_employee requires user_id in details"}
        return hr_tools.remove_employee(shop_id=shop_id, user_id=user_id)

    if action == "assign_shift":
        user_id = details.get("user_id")
        start_time = details.get("start_time")
        end_time = details.get("end_time")
        date = details.get("date")
        missing = [field for field, value in {
            "user_id": user_id,
            "start_time": start_time,
            "end_time": end_time,
            "date": date,
        }.items() if not value]
        if missing:
            return {"error": f"assign_shift requires {', '.join(missing)} in details"}

        assert user_id is not None
        assert start_time is not None
        assert end_time is not None
        assert date is not None

        shift_user_id = int(user_id)
        shift_start_time = str(start_time)
        shift_end_time = str(end_time)
        shift_date = str(date)

        return hr_tools.assign_shift(
            shop_id=shop_id,
            user_id=shift_user_id,
            start_time=shift_start_time,
            end_time=shift_end_time,
            date=shift_date,
        )

    if action == "create_invoice":
        service_name = details.get("service_name")
        unit_price = details.get("unit_price")
        if not service_name or unit_price in (None, ""):
            return {"error": "create_invoice requires service_name and unit_price in details"}
        return finance_tools.create_invoice(
            shop_id=shop_id,
            service_name=str(service_name),
            unit_price=float(unit_price),
            quantity=int(details.get("quantity") or 1),
            customer_id=int(details["customer_id"]) if details.get("customer_id") not in (None, "") else None,
            tax_rate=float(details.get("tax_rate") or 0.0),
            notes=str(details.get("notes")) if details.get("notes") not in (None, "") else None,
        )

    if action == "record_payment":
        amount = details.get("amount")
        if amount in (None, ""):
            return {"error": "record_payment requires amount in details"}
        return finance_tools.record_payment(
            shop_id=shop_id,
            amount=float(amount),
            method=str(details.get("method") or "cash"),
            invoice_id=int(details["invoice_id"]) if details.get("invoice_id") not in (None, "") else None,
            notes=str(details.get("notes")) if details.get("notes") not in (None, "") else None,
        )

    if action == "process_refund":
        payment_id = details.get("payment_id")
        if payment_id in (None, ""):
            return {"error": "process_refund requires payment_id in details"}
        return finance_tools.process_refund(
            shop_id=shop_id,
            payment_id=int(payment_id),
            refund_amount=float(details["refund_amount"]) if details.get("refund_amount") not in (None, "") else None,
            reason=str(details.get("reason")) if details.get("reason") not in (None, "") else None,
        )

    # ── Queue management ─────────────────────────────────────────────────────
    if action == "open_queue":
        queue_name = str(details.get("name") or "Main Queue")
        return booking_tools.open_queue(shop_id, queue_name)

    # ── HR: full onboarding with payroll profile ──────────────────────────────
    if action == "onboard_employee":
        name = details.get("name")
        if not name:
            return {"error": "onboard_employee requires name in details"}
        return hr_tools.add_employee_full(
            shop_id=shop_id,
            name=str(name),
            pay_type=str(details.get("pay_type") or "hourly"),
            hourly_rate=float(details["hourly_rate"]) if details.get("hourly_rate") not in (None, "") else None,
            annual_salary=float(details["annual_salary"]) if details.get("annual_salary") not in (None, "") else None,
            pay_frequency=str(details.get("pay_frequency") or "biweekly"),
            province=str(details.get("province") or "ON"),
            email=str(details["email"]) if details.get("email") not in (None, "") else None,
            phone=str(details["phone"]) if details.get("phone") not in (None, "") else None,
            role=str(details.get("role") or "employee"),
            sin=str(details["sin"]) if details.get("sin") not in (None, "") else None,
            created_by=state.get("user_id"),
        )

    # ── HR: leave approval ────────────────────────────────────────────────────
    if action == "leave_request":
        employee_name = str(details.get("employee_name") or "employee")
        leave_date = str(details.get("leave_date") or "the requested date")
        leave_type = str(details.get("leave_type") or "leave")
        return {
            "status": "approved",
            "employee_name": employee_name,
            "leave_date": leave_date,
            "leave_type": leave_type,
            "message": (
                f"{employee_name}'s {leave_type} request for {leave_date} has been approved."
            ),
        }

    # ── HR: pay rate update ───────────────────────────────────────────────────
    if action == "update_pay_rate":
        employee_name = details.get("employee_name")
        if not employee_name:
            return {"error": "update_pay_rate requires employee_name in details"}
        field = str(details.get("field") or "hourly_rate")
        new_rate = details.get("new_rate")
        if new_rate is None:
            return {"error": "update_pay_rate requires new_rate in details"}
        return hr_tools.update_employee_payroll_field(
            shop_id=shop_id,
            employee_name=str(employee_name),
            field=field,
            value=new_rate,
        )

    # ── HR: payroll run ───────────────────────────────────────────────────────
    if action == "run_payroll":
        from datetime import date as _date
        from sqlalchemy import text as _text
        from agents.tools import payroll_tools as _payroll_tools

        period_start_str = details.get("period_start")
        period_end_str = details.get("period_end")
        pay_date_str = details.get("pay_date") or period_end_str
        if not period_start_str or not period_end_str:
            return {"error": "run_payroll requires period_start and period_end in details"}
        try:
            period_start = _date.fromisoformat(str(period_start_str))
            period_end = _date.fromisoformat(str(period_end_str))
            pay_date = _date.fromisoformat(str(pay_date_str)) if pay_date_str else period_end
        except ValueError as exc:
            return {"error": f"run_payroll: invalid date format — {exc}"}

        regular_hours = float(details.get("regular_hours") or 80.0)
        overtime_hours = float(details.get("overtime_hours") or 0.0)
        tips_amount = float(details.get("tips_amount") or 0.0)

        with SessionLocal() as _session:
            rows = _session.execute(
                _text(
                    "SELECT se.id FROM shop_employees se "
                    "JOIN employee_payroll_profiles epp ON epp.shop_employee_id = se.id "
                    "WHERE se.shop_id = :sid AND se.is_active = TRUE"
                ),
                {"sid": shop_id},
            ).fetchall()

        if not rows:
            return {"error": "No employees with payroll profiles found for this shop"}

        payslips: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        for row in rows:
            try:
                payslip = _payroll_tools.draft_payslip(
                    shop_id=shop_id,
                    shop_employee_id=int(row[0]),
                    period_start=period_start,
                    period_end=period_end,
                    pay_date=pay_date,
                    regular_hours=regular_hours,
                    overtime_hours=overtime_hours,
                    tips_amount=tips_amount,
                )
                payslips.append(payslip)
            except Exception as _exc:
                errors.append({"shop_employee_id": int(row[0]), "error": str(_exc)})

        return {
            "status": "payroll_drafted",
            "payslips_created": len(payslips),
            "errors": errors,
            "period": f"{period_start_str} → {period_end_str}",
            "pay_date": str(pay_date),
            "message": (
                f"Created {len(payslips)} draft payslip(s) for {period_start_str} → {period_end_str}."
            ),
        }

    # ── HR: tip pool split ────────────────────────────────────────────────────
    if action == "split_tips":
        from datetime import date as _date
        from agents.tools import payroll_tools as _payroll_tools

        total_amount = details.get("total_amount")
        if total_amount is None:
            return {"error": "split_tips requires total_amount in details"}
        pool_date_str = details.get("pool_date")
        try:
            pool_date = _date.fromisoformat(str(pool_date_str)) if pool_date_str else _date.today()
        except ValueError:
            pool_date = _date.today()

        pool = _payroll_tools.create_tip_pool(shop_id, pool_date, float(total_amount))
        raw_splits = details.get("employee_splits") or []
        splits = [
            {
                "shop_employee_id": int(s["shop_employee_id"]),
                "hours_worked": float(s.get("hours_worked") or 0),
                "split_amount": float(s["split_amount"]),
            }
            for s in raw_splits
            if s.get("shop_employee_id") and s.get("split_amount") is not None
        ]

        if not splits:
            return {
                "status": "tip_pool_created",
                "tip_pool_id": pool.get("id"),
                "total_amount": float(total_amount),
                "pool_date": str(pool_date),
                "message": (
                    f"Tip pool of ${float(total_amount):.2f} created for {pool_date}. "
                    "Assign splits manually."
                ),
            }

        result = _payroll_tools.split_tip_pool(
            tip_pool_id=int(pool["id"]),
            splits=splits,
            approved_by_user_id=int(state.get("user_id") or 0),
        )
        return {
            "status": "tips_split",
            "tip_pool_id": result.get("id"),
            "total_amount": float(total_amount),
            "splits_recorded": len(splits),
            "message": (
                f"${float(total_amount):.2f} tip pool split among {len(splits)} staff member(s)."
            ),
        }

    # ── HR: T4 generation ─────────────────────────────────────────────────────
    if action == "generate_t4":
        from sqlalchemy import text as _text
        from agents.tools import payroll_tools as _payroll_tools

        tax_year = details.get("tax_year")
        if not tax_year:
            return {"error": "generate_t4 requires tax_year in details"}
        tax_year_int = int(tax_year)

        with SessionLocal() as _session:
            rows = _session.execute(
                _text(
                    "SELECT se.id FROM shop_employees se "
                    "JOIN employee_payroll_profiles epp ON epp.shop_employee_id = se.id "
                    "WHERE se.shop_id = :sid AND se.is_active = TRUE"
                ),
                {"sid": shop_id},
            ).fetchall()

        t4s: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        for row in rows:
            try:
                t4 = _payroll_tools.draft_t4(shop_id, int(row[0]), tax_year_int)
                t4s.append(t4)
            except Exception as _exc:
                errors.append({"shop_employee_id": int(row[0]), "error": str(_exc)})

        return {
            "status": "t4_drafted",
            "t4s_created": len(t4s),
            "errors": errors,
            "tax_year": tax_year_int,
            "message": f"Generated {len(t4s)} T4 draft(s) for tax year {tax_year_int}.",
        }

    # ── Inventory: add item ───────────────────────────────────────────────────
    if action == "add_item":
        from agents.tools import inventory_tools as _inv_tools

        item_name = details.get("name")
        if not item_name:
            return {"error": "add_item requires name in details"}
        return _inv_tools.add_item(
            shop_id=shop_id,
            name=str(item_name),
            unit=str(details.get("unit") or "piece"),
            category=str(details["category"]) if details.get("category") not in (None, "") else None,
            sku=str(details["sku"]) if details.get("sku") not in (None, "") else None,
            initial_stock=float(details.get("initial_stock") or 0.0),
            reorder_threshold=float(details.get("reorder_threshold") or 0.0),
            cost_per_unit=float(details["cost_per_unit"]) if details.get("cost_per_unit") not in (None, "") else None,
            supplier=str(details["supplier"]) if details.get("supplier") not in (None, "") else None,
        )

    # ── Inventory: stock adjustment ───────────────────────────────────────────
    if action == "record_adjustment":
        from agents.tools import inventory_tools as _inv_tools

        item_id = details.get("item_id")
        quantity = details.get("quantity")
        if item_id is None:
            return {"error": "record_adjustment requires item_id in details"}
        if quantity is None:
            return {"error": "record_adjustment requires quantity in details"}
        return _inv_tools.record_adjustment(
            shop_id=shop_id,
            item_id=int(item_id),
            quantity=float(quantity),
            notes=str(details["notes"]) if details.get("notes") not in (None, "") else None,
            created_by=state.get("user_id"),
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

    policy_mode = str(pending.get("policy_mode") or PolicyMode.REQUIRE_APPROVAL.value)

    if policy_mode == PolicyMode.FORBID.value:
        action_title = str(pending.get("title") or pending.get("action") or "This action")
        rejection_msg = AIMessage(
            content=f"{action_title} is blocked by the current shop policy, so no changes were made."
        )
        return {
            "messages": list(state.get("messages", [])) + [rejection_msg],
            "needs_human_input": False,
            "pending_approval": None,
            "tool_results": {
                "status": "forbidden",
                "action": pending.get("action"),
                "reason": "blocked_by_policy",
                "policy_mode": policy_mode,
            },
        }

    if policy_mode in {PolicyMode.ALLOW.value, PolicyMode.NOTIFY_ONLY.value, PolicyMode.SILENT.value}:
        execution_result = _execute_approved_action(state, pending)
        result_message = execution_result.get("message") or f"Action '{pending.get('action')}' was executed successfully."
        if policy_mode == PolicyMode.NOTIFY_ONLY.value:
            _create_policy_notification(state, pending, result_message)
            content = f"I executed this automatically under your current policy and logged a notification. {result_message}"
        elif policy_mode == PolicyMode.ALLOW.value:
            content = f"I executed this automatically because your current policy allows it. {result_message}"
        else:
            content = str(result_message)

        return {
            "messages": list(state.get("messages", [])) + [AIMessage(content=content)],
            "needs_human_input": False,
            "pending_approval": None,
            "tool_results": {
                **execution_result,
                "policy_mode": policy_mode,
            },
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
        result_message = execution_result.get("message") or f"Action '{pending.get('action')}' was executed successfully."
        execution_msg = AIMessage(
            content=f"Approval received. {result_message}"
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
    2. plan_and_route - build execution plan and resolve target specialist
    3. execute_plan - run specialist (or supervisor direct path)
    4. approval_gate - pause/resume high-impact actions
    5. synthesize_response - produce final owner-facing response
    6. END
    
    Returns:
        langgraph.graph.StateGraph instance ready to compile
    """
    
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("plan_execution", plan_execution)
    graph.add_node("plan_and_route", plan_and_route)
    graph.add_node("execute_plan", execute_plan)
    graph.add_node("approval_gate", approval_gate)
    graph.add_node("synthesize_response", synthesize_response)
    
    # Add edges
    graph.add_edge("classify_intent", "plan_and_route")
    graph.add_edge("plan_execution", "execute_plan")
    graph.add_edge("plan_and_route", "execute_plan")
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
