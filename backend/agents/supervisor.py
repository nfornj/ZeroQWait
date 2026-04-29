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
from .llm_factory import create_chat_model
from .state import AgentState
from .tools import booking_tools, finance_tools, hr_tools


logger = logging.getLogger(__name__)


_QUEUE_OPERATION_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:close|open|reopen|pause|resume)\s+(?:the\s+)?queue\b"),
    re.compile(r"\b(?:call|serve)\s+(?:the\s+)?next(?:\s+customer)?\b"),
    re.compile(r"\b(?:queue\s+status|queue\s+summary|queue\s+length|wait\s+time)\b"),
    re.compile(r"\b(?:join|leave)\s+(?:the\s+)?queue\b"),
)

_FINANCE_OPERATION_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:revenue|sales)\b.*\b(?:trend|trends|graph|chart|over\s+time|by\s+day|by\s+date|daily\s+breakdown)\b"),
    re.compile(r"\b(?:trend|trends|graph|chart|over\s+time|by\s+day|by\s+date|daily\s+breakdown)\b.*\b(?:revenue|sales)\b"),
    re.compile(r"\b(?:today|today's|yesterday|yesterday's|this\s+week|last\s+week|this\s+month|last\s+month|this\s+quarter|last\s+quarter|this\s+year|last\s+year)\b.*\b(?:revenue|sales)\b"),
    re.compile(r"\b(?:revenue|sales)\b.*\b(?:today|today's|yesterday|yesterday's|this\s+week|last\s+week|this\s+month|last\s+month|this\s+quarter|last\s+quarter|this\s+year|last\s+year)\b"),
    re.compile(r"\b(?:weekly|monthly|quarterly|yearly)\s+(?:revenue|sales)\s+(?:summary|summaries)\b"),
    re.compile(r"\b(?:summary|summaries)\s+of\s+(?:weekly|monthly|quarterly|yearly)\s+(?:revenue|sales)\b"),
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


def _classify_intent_fastpath(user_input: str) -> Optional[Tuple[str, str]]:
    normalized = " ".join(str(user_input or "").lower().split())
    if not normalized:
        return None

    for pattern in _QUEUE_OPERATION_PATTERNS:
        if pattern.search(normalized):
            return "booking", "fastpath_queue_operation"

    for pattern in _FINANCE_OPERATION_PATTERNS:
        if pattern.search(normalized):
            return "finance", "fastpath_finance_operation"

    return None


def get_llm(state: Optional[AgentState] = None, *, temperature: float = 0.3):
    """Create the shop-aware chat model for agent graphs."""
    shop_id = None
    if state is not None:
        shop_id = state.get("tenant_id")
    return create_chat_model(shop_id, temperature=temperature)


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




def classify_intent(state: AgentState) -> Command[Literal["plan_and_route"]]:
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

    fastpath = _classify_intent_fastpath(user_input)
    if fastpath is not None:
        intent, source = fastpath
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info("classify_intent fast-path: %r → %s in %.1fms", user_input[:80], intent, elapsed_ms)
        reasoning = f"I routed this directly to {intent} because the request clearly matched the {source.replace('_', ' ')} pattern."
        return Command(
            goto="plan_and_route",
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
        "- hr: employees, shifts, scheduling, availability, staffing, clock in/out, roster\n"
        "- crm: CRM leads, contacts, companies, pipeline, deals, Odoo ERP operations, "
        "accounting, journal entries, products catalog\n"
        "- general: greetings, help, capabilities, general chat\n\n"
        + ("\n".join(context_lines) + "\n" if context_lines else "")
        + "Respond with your classification."
    )

    llm = get_llm(state)

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
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.info("classify_intent fallback: %r → %s in %.1fms", user_input[:80], intent, elapsed_ms)
        except Exception:
            intent = "general"
            source = "error_fallback"

    return Command(
        goto="plan_and_route",
        update={
            "current_agent": intent,
            "metadata": _merge_metadata(state, {
                "classified_intent": intent,
                "classification_source": source,
                "routing_reasoning": decision.thought_process.strip(),
                "is_followup": decision.is_followup,
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
        from .crm import run_crm_agent
        result = asyncio.run(run_crm_agent(state))
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
    
    messages = list(state.get("messages", []) or [])
    metadata = state.get("metadata") or {}

    current_agent = state.get("current_agent", "supervisor")

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

    llm = get_llm(state)

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
    graph.add_node("plan_and_route", plan_and_route)
    graph.add_node("execute_plan", execute_plan)
    graph.add_node("approval_gate", approval_gate)
    graph.add_node("synthesize_response", synthesize_response)
    
    # Add edges
    graph.add_edge("classify_intent", "plan_and_route")
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
