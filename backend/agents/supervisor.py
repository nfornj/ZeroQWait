"""
Supervisor Agent Graph - Central router for owner commands.
























































    unittest.main()if __name__ == "__main__":        self.assertEqual(granularity, "week")        self.assertEqual(label, "last_8_weeks")        )            "show customer traffic for last 8 weeks"        _, _, granularity, label = finance_tools._parse_time_window(    def test_parse_last_n_weeks_window_long_range_uses_week_granularity(self):        self.assertLessEqual(start_dt, end_dt)        self.assertEqual(granularity, "day")        self.assertEqual(label, "last_3_weeks")        )            "show customer traffic for last 3 weeks"        start_dt, end_dt, granularity, label = finance_tools._parse_time_window(    def test_parse_last_n_weeks_window(self):        self.assertEqual(end_dt.month, 2)        self.assertEqual(start_dt.day, 1)        self.assertEqual(start_dt.month, 2)        self.assertEqual(start_dt.year, expected_year)        self.assertEqual(label, f"month_{expected_year}_02")        self.assertEqual(granularity, "day")        )            "total customers in february"        start_dt, end_dt, granularity, label = finance_tools._parse_time_window(        expected_year = now.year if now.month >= 2 else now.year - 1        now = datetime.now()    def test_parse_named_month_window(self):        self.assertGreaterEqual((end_dt.date() - start_dt.date()).days, 9)        self.assertLessEqual(start_dt, end_dt)        self.assertEqual(granularity, "day")        self.assertEqual(label, "last_10_days")        )            "how many customers have visited last 10 days"        start_dt, end_dt, granularity, label = finance_tools._parse_time_window(    def test_parse_last_10_days_window(self):class TestFinanceCustomerWindows(unittest.TestCase):from agents.tools import finance_toolssys.path.append(os.path.dirname(os.path.abspath(__file__)))# Add backend directory to import path when executed directly.from datetime import datetimeimport unittest
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
import difflib
import re
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langgraph.types import Command, interrupt

from .state import AgentState
from .tools import booking_tools, hr_tools
from .memory_context import get_conversation_history, save_conversation_turn
from redis_client import redis_client


_FINANCE_MONTH_TOKENS = [
    "jan", "january", "feb", "february", "mar", "march", "apr", "april", "may",
    "jun", "june", "jul", "july", "aug", "august", "sep", "sept", "september",
    "oct", "october", "nov", "november", "dec", "december",
]

_BOOKING_KEYWORDS = ["queue", "booking", "appointment", "wait", "service", "services", "customer", "schedule", "slot", "reschedule", "book"]
_FINANCE_KEYWORDS = [
    "revenue", "finance", "analytics", "report", "sales", "trend", "monthly", "month", "weekly", "week",
    "daily", "day", "yearly", "year", "quarter", "income", "profit", "transaction", "customers", "visited", "visits",
    "invoice", "payment", "refund", "pos", "billing", "receipt", "tip",
]
_CLIENT_KEYWORDS = [
    "client", "clients", "customer", "customers", "who hasn't",
    "inactive", "lapsed", "top client", "frequent", "loyalty",
    "hasn't visited", "not been in", "profile", "visit history",
]
_HR_KEYWORDS = ["employee", "employees", "staff", "shift", "schedule", "hire", "availability", "clock in", "clock out", "working", "on duty", "roster"]
_CRM_KEYWORDS = [
    "crm", "lead", "leads", "contact", "contacts", "client", "clients",
    "company", "companies", "opportunity", "opportunities", "pipeline",
    "deal", "deals", "prospect", "prospects", "note", "notes", "task", "tasks",
]


def _detect_intent_domains(text: str) -> list[str]:
    domains = []
    if _contains_any_fuzzy(text, _BOOKING_KEYWORDS):
        domains.append("booking")
    if _contains_any_fuzzy(text, _FINANCE_KEYWORDS) or _contains_any_fuzzy(text, _FINANCE_MONTH_TOKENS) or _contains_any_fuzzy(text, _CLIENT_KEYWORDS):
        domains.append("finance")
    if _contains_any_fuzzy(text, _HR_KEYWORDS):
        domains.append("hr")
    if _contains_any_fuzzy(text, _CRM_KEYWORDS):
        domains.append("crm")
    return domains


def _select_primary_domain(text: str, domains: list[str]) -> str:
    """Pick domain by earliest keyword occurrence to better handle mixed questions."""
    lowered = (text or "").lower()
    keyword_map = {
        "booking": _BOOKING_KEYWORDS,
        "finance": _FINANCE_KEYWORDS + _FINANCE_MONTH_TOKENS + _CLIENT_KEYWORDS,
        "hr": _HR_KEYWORDS,
        "crm": _CRM_KEYWORDS,
    }
    best_domain = domains[0] if domains else "general"
    best_index = 10**9
    for domain in domains:
        for keyword in keyword_map.get(domain, []):
            idx = lowered.find(keyword)
            if idx != -1 and idx < best_index:
                best_index = idx
                best_domain = domain
    return best_domain


def _is_probably_greeting(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return lowered in {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}


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


def _is_followup_phrase(text: str) -> bool:
    lowered = (text or "").lower()
    return any(
        phrase in lowered
        for phrase in [
            "what about",
            "how about",
            "and what about",
            "same for",
            "what if",
            "and for",
            "for feb",
            "for march",
            "for april",
            "for may",
            "for june",
            "for july",
            "for august",
            "for september",
            "for october",
            "for november",
            "for december",
        ]
    )


def _is_contextual_followup(text: str) -> bool:
    """Detect short referential follow-ups that rely on previous specialist context."""
    lowered = (text or "").strip().lower()
    tokens = _tokenize_text(lowered)
    if not tokens:
        return False

    referential_tokens = {
        "their", "them", "those", "these", "that", "it", "its", "they", "there", "ones",
        "name", "names", "status", "details", "list",
    }
    question_starts = {
        "what", "who", "which", "where", "when", "how", "show", "list", "give",
    }

    # Typical short follow-up pattern: "what are their names?"
    if len(tokens) <= 8 and any(token in referential_tokens for token in tokens):
        return True

    # Compact question right after a specialist answer usually means continuation.
    if len(tokens) <= 6 and tokens[0] in question_starts and lowered.endswith("?"):
        return True

    return False


def _tokenize_text(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _matches_keyword_fuzzy(token: str, keyword: str) -> bool:
    if token == keyword:
        return True
    # Short keywords (e.g., month abbreviations like "may") are too noisy for
    # fuzzy matching and can create false mixed-intent classifications.
    if len(keyword) <= 3 or len(token) <= 3:
        return False
    if abs(len(token) - len(keyword)) > 2:
        return False
    return difflib.SequenceMatcher(a=token, b=keyword).ratio() >= 0.82


def _contains_any_fuzzy(text: str, keywords: list[str]) -> bool:
    tokens = _tokenize_text(text)
    if not tokens:
        return False
    for token in tokens:
        for keyword in keywords:
            if _matches_keyword_fuzzy(token, keyword):
                return True
    return False


def _infer_previous_target_from_history(state: AgentState) -> Optional[str]:
    """Infer prior specialist from recent conversation history when metadata is unavailable."""
    messages = list(state.get("messages", []) or [])
    if not messages:
        return None

    skipped_latest_user = False
    for msg in reversed(messages):
        if not isinstance(msg, HumanMessage):
            continue
        content = str(msg.content).strip().lower()
        if not content:
            continue
        if not skipped_latest_user:
            skipped_latest_user = True
            continue

        domains = _detect_intent_domains(content)
        if "crm" in domains:
            return "crm"
        if "hr" in domains:
            return "hr"
        if "finance" in domains:
            return "finance"
        if "booking" in domains:
            return "receptionist"

    return None


# Initialize LLM (qwen3:14b-q4_K_M via Ollama)
def get_llm():
    """Create LLM instance for agent graphs."""
    import os
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
    model_name = os.getenv("MODEL_NAME", "qwen3:14b-q4_K_M")
    
    return ChatOllama(
        model=model_name,
        base_url=ollama_url,
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
    Classify owner's intent from the latest message.
    
    Returns the intent category to determine routing.
    
    Categories:
    - "booking": Queue, appointments, wait times, close queue
    - "finance": Revenue, analytics, reports, invoices, client retention, visit history, inactive customers
    - "hr": Employees, shifts, scheduling, availability
    - "general": Help, capabilities, general chat
    """
    
    # Extract latest user message
    messages = state.get("messages", [])
    if not messages:
        return Command(
            goto="plan_execution",
            update={
                "current_agent": "general",
                "metadata": _merge_metadata(state, {"classified_intent": "general", "classification_source": "empty_messages"}),
            },
        )
    
    user_input = _latest_user_text(state)
    
    # Fast local heuristic first for reliability when LLM is unavailable.
    heuristic_text = str(user_input).lower()

    if _contains_any_fuzzy(heuristic_text, _CLIENT_KEYWORDS):
        return Command(
            goto="plan_execution",
            update={
                "current_agent": "finance",
                "metadata": _merge_metadata(
                    state,
                    {
                        "classified_intent": "finance",
                        "classification_source": "client_heuristic",
                        "mixed_intents": [],
                        "requires_clarification": False,
                    },
                ),
            },
        )

    metadata = state.get("metadata") or {}
    previous_target = (metadata.get("route") or {}).get("to")
    if previous_target not in {"receptionist", "finance", "hr", "crm"}:
        previous_target = metadata.get("last_specialist_target")
    if previous_target not in {"receptionist", "finance", "hr", "crm"}:
        previous_target = state.get("current_agent") if state.get("current_agent") in {"receptionist", "finance", "hr", "crm"} else None
    if previous_target not in {"receptionist", "finance", "hr", "crm"}:
        previous_target = _infer_previous_target_from_history(state)

    domain_hits = _detect_intent_domains(heuristic_text)

    intent_by_target = {
        "receptionist": "booking",
        "finance": "finance",
        "hr": "hr",
        "crm": "crm",
    }

    # Follow-up continuity: short elliptical prompts should continue the last specialist context.
    # Example: "what about february?" right after a finance question.
    if previous_target and _is_followup_phrase(heuristic_text):
        followup_intent = intent_by_target.get(previous_target, "general")
        return Command(
            goto="plan_execution",
            update={
                "current_agent": followup_intent,
                "metadata": _merge_metadata(
                    state,
                    {
                        "classified_intent": followup_intent,
                        "classification_source": "followup_context",
                        "followup_from": previous_target,
                        "mixed_intents": [],
                        "requires_clarification": False,
                    },
                ),
            },
        )

    # Context-driven follow-up continuity for referential prompts that do not
    # carry explicit domain keywords (e.g., "what are their names?").
    if previous_target and not domain_hits and _is_contextual_followup(heuristic_text):
        followup_intent = intent_by_target.get(previous_target, "general")
        return Command(
            goto="plan_execution",
            update={
                "current_agent": followup_intent,
                "metadata": _merge_metadata(
                    state,
                    {
                        "classified_intent": followup_intent,
                        "classification_source": "followup_contextual",
                        "followup_from": previous_target,
                        "mixed_intents": [],
                        "requires_clarification": False,
                    },
                ),
            },
        )

    if len(domain_hits) > 1:
        primary = _select_primary_domain(heuristic_text, domain_hits)
        return Command(
            goto="plan_execution",
            update={
                "current_agent": primary,
                "metadata": _merge_metadata(
                    state,
                    {
                        "classified_intent": primary,
                        "classification_source": "mixed_heuristic",
                        "mixed_intents": domain_hits,
                        "requires_clarification": True,
                    },
                ),
            },
        )

    if len(domain_hits) == 1:
        intent = domain_hits[0]
        return Command(
            goto="plan_execution",
            update={
                "current_agent": intent,
                "metadata": _merge_metadata(
                    state,
                    {
                        "classified_intent": intent,
                        "classification_source": "heuristic",
                        "mixed_intents": [],
                        "requires_clarification": False,
                    },
                ),
            },
        )
    if _contains_any_fuzzy(heuristic_text, [
        "csv", "export", "download", "xlsx", "excel", "file",
        "dates", "date", "list", "only", "just",
        "revenue",
    ]):
        intent = "finance"
        return Command(
            goto="plan_execution",
            update={
                "current_agent": intent,
                "metadata": _merge_metadata(
                    state,
                    {
                        "classified_intent": intent,
                        "classification_source": "heuristic",
                        "mixed_intents": [],
                        "requires_clarification": False,
                    },
                ),
            },
        )

    llm = get_llm()
    history_messages = _conversation_history_messages(state)

    # Classification prompt
    classification_prompt = f"""Classify the following shop owner command into one of these categories:
    
1. "booking" - Queue management, appointments, booking, wait times, closing queue, available slots, rescheduling
2. "finance" - Revenue, analytics, financial reports, invoices, payments, POS, billing, refunds, daily/weekly summaries, client retention, inactive customers, visit history  
3. "hr" - Employees, shifts, scheduling, availability, staffing, clock in/out
4. "crm" - Clients, leads, contacts, companies, CRM pipeline, notes, tasks
5. "general" - Help, capabilities, greeting, general chat

Owner's command: {user_input}

Respond with ONLY the category name (one word): booking, finance, hr, crm, or general"""
    
    # Get classification
    try:
        response = llm.invoke(history_messages + [HumanMessage(content=classification_prompt)])
        raw_content = response.content
        if isinstance(raw_content, str):
            intent = raw_content.strip().lower()
        else:
            intent = str(raw_content).strip().lower()
    except Exception:
        intent = "general"
    
    # Validate and default
    valid_intents = ["booking", "finance", "hr", "crm", "general"]
    if intent not in valid_intents:
        intent = "general"

    needs_clarification = intent == "general" and not _is_probably_greeting(user_input)
    
    # Update state with classified intent
    return Command(
        goto="plan_execution",
        update={
            "current_agent": intent,
            "metadata": _merge_metadata(
                state,
                {
                    "classified_intent": intent,
                    "classification_source": "llm",
                    "requires_clarification": needs_clarification,
                    "mixed_intents": [] if intent != "general" else (state.get("metadata") or {}).get("mixed_intents", []),
                },
            ),
        }
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
    """Dispatch CRM query to Twenty CRM and return LLM-formatted response."""
    import re as _re
    from .tools import crm_tools

    user_text = _latest_user_text(state)
    messages = list(state.get("messages", []) or [])
    shop_id = state.get("tenant_id")
    lowered = user_text.lower()

    try:
        if any(w in lowered for w in ["pipeline", "opportunity", "opportunities", "deal", "deals"]):
            if any(w in lowered for w in ["summary", "overview", "how many", "total"]):
                data = await crm_tools.crm_get_pipeline_summary()
            else:
                data = await crm_tools.crm_get_opportunities()
        elif any(w in lowered for w in ["note", "notes"]):
            data = await crm_tools.crm_get_notes()
        elif any(w in lowered for w in ["task", "tasks", "todo"]):
            data = await crm_tools.crm_get_tasks()
        elif any(w in lowered for w in ["compan", "companies"]):
            data = await crm_tools.crm_get_companies()
        else:
            name_match = _re.search(
                r'(?:about|details|show|find|search|who is|contact)\s+'
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                user_text,
            )
            if name_match:
                data = await crm_tools.crm_search_person(name_match.group(1))
            else:
                data = await crm_tools.crm_get_people()
    except Exception as e:
        data = {"error": str(e)}

    llm = get_llm()
    history_messages = _conversation_history_messages(state)

    crm_system_prompt = f"""You are the CRM assistant for shop (shop_id={shop_id}).
You have the owner's Twenty CRM data below. Answer naturally and concisely.

Formatting rules:
- People: "Name (email) — Company"
- Opportunities: "Deal Name — $X,XXX (Stage)"
- Pipeline summary: table by stage
- Empty results: "Your CRM doesn't have any [type] yet"
- Always state the total count when listing items
- NEVER invent data — only use what is provided

CRM data:
{data}

Owner asked: {user_text}"""

    try:
        response = llm.invoke(
            history_messages + messages + [SystemMessage(content=crm_system_prompt)]
        )
    except Exception as e:
        response = AIMessage(
            content=f"I retrieved your CRM data but had trouble formatting it: {e}"
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


def placeholder_receptionist(state: AgentState) -> dict:
    """
    Route to Receptionist sub-agent (Phase 2).
    Invokes the receptionist graph.
    """
    from .receptionist import create_receptionist_runnable
    
    receptionist = create_receptionist_runnable()
    result = receptionist.invoke(state)
    
    return {
        **result,
        "current_agent": "receptionist"
    }


def placeholder_finance(state: AgentState) -> dict:
    """
    Route to Finance sub-agent (Phase 2).
    Invokes the finance graph.
    """
    from .finance import create_finance_runnable
    
    finance = create_finance_runnable()
    result = finance.invoke(state)
    
    return {
        **result,
        "current_agent": "finance"
    }


def placeholder_hr(state: AgentState) -> dict:
    """
    Route to HR sub-agent (Phase 2).
    Invokes the HR graph.
    """
    from .hr import create_hr_runnable
    
    hr = create_hr_runnable()
    result = hr.invoke(state)
    
    return {
        **result,
        "current_agent": "hr"
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
