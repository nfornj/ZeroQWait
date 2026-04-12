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

from typing import Literal, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langgraph.types import Command, interrupt

from .state import AgentState
from .tools import booking_tools, hr_tools


# Initialize LLM (gpt-oss:20b via Ollama)
def get_llm():
    """Create LLM instance for agent graphs."""
    import os
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
    model_name = os.getenv("MODEL_NAME", "gpt-oss:20b")
    
    return ChatOllama(
        model=model_name,
        base_url=ollama_url,
        temperature=0.3,  # Deterministic for tool calling
        top_p=0.9,
    )


def classify_intent(state: AgentState) -> Command[Literal["route_to_agent"]]:
    """
    Classify owner's intent from the latest message.
    
    Returns the intent category to determine routing.
    
    Categories:
    - "booking": Queue, appointments, wait times, close queue
    - "finance": Revenue, analytics, reports, invoices
    - "hr": Employees, shifts, scheduling, availability
    - "general": Help, capabilities, general chat
    """
    
    # Extract latest user message
    messages = state.get("messages", [])
    if not messages:
        return Command(goto="route_to_agent", update={"current_agent": "general"})
    
    latest_message = messages[-1]
    if isinstance(latest_message, BaseMessage):
        user_input = latest_message.content
    else:
        user_input = str(latest_message)
    
    # Fast local heuristic first for reliability when LLM is unavailable.
    heuristic_text = str(user_input).lower()
    if any(token in heuristic_text for token in ["queue", "booking", "appointment", "wait", "service"]):
        intent = "booking"
        return Command(goto="route_to_agent", update={"current_agent": intent})
    if any(token in heuristic_text for token in [
        "revenue", "finance", "analytics", "report", "sales",
        "trend", "monthly", "month", "weekly", "week", "daily", "day",
        "yearly", "year", "quarter", "income", "profit", "transaction"
    ]):
        intent = "finance"
        return Command(goto="route_to_agent", update={"current_agent": intent})
    if any(token in heuristic_text for token in [
        "csv", "export", "download", "xlsx", "excel", "file",
        "dates only", "date only", "list dates", "only dates", "just dates",
        "revenue only", "only revenue", "just revenue",
    ]):
        intent = "finance"
        return Command(goto="route_to_agent", update={"current_agent": intent})
    if any(token in heuristic_text for token in ["employee", "staff", "shift", "schedule", "hire"]):
        intent = "hr"
        return Command(goto="route_to_agent", update={"current_agent": intent})

    llm = get_llm()

    # Classification prompt
    classification_prompt = f"""Classify the following shop owner command into one of these categories:
    
1. "booking" - Queue management, appointments, wait times, closing queue, customer service
2. "finance" - Revenue, analytics, financial reports, invoices, daily/weekly summaries  
3. "hr" - Employees, shifts, scheduling, availability, staffing
4. "general" - Help, capabilities, greeting, general chat

Owner's command: {user_input}

Respond with ONLY the category name (one word): booking, finance, hr, or general"""
    
    # Get classification
    try:
        response = llm.invoke([HumanMessage(content=classification_prompt)])
        raw_content = response.content
        if isinstance(raw_content, str):
            intent = raw_content.strip().lower()
        else:
            intent = str(raw_content).strip().lower()
    except Exception:
        intent = "general"
    
    # Validate and default
    valid_intents = ["booking", "finance", "hr", "general"]
    if intent not in valid_intents:
        intent = "general"
    
    # Update state with classified intent
    return Command(
        goto="route_to_agent",
        update={"current_agent": intent}
    )


def route_to_agent(state: AgentState) -> dict:
    """
    Route to the appropriate sub-agent based on classified intent.
    
    Phase 1: Returns intent as routing hint (no actual sub-agents yet)
    Phase 2: Will route to actual sub-agent graphs via invoke()
    """
    
    # No-op node: branching is controlled by conditional edges on current_agent.
    return {}


def respond(state: AgentState) -> dict:
    """
    Supervisor response node. Called when:
    - Intent is "general" (handled by Supervisor directly)
    - Sub-agent has completed and returned result
    
    Formats final response to owner.
    """
    
    # Get conversation history
    messages = state.get("messages", [])

    # If a sub-agent already produced a direct reply, do not call LLM again.
    current_agent = state.get("current_agent", "supervisor")
    if current_agent in {"receptionist", "finance", "hr"} and messages:
        last_message = messages[-1]
        if isinstance(last_message, AIMessage):
            return {
                "messages": list(messages),
                "tool_results": state.get("tool_results")
            }

    llm = get_llm()
    
    # Build response prompt
    system_prompt = f"""You are ZeroQwait Supervisor Agent, managing the AI operations team for shop owner (shop_id={state.get('tenant_id')}).

You have three specialized sub-agents available:
1. Receptionist - handles bookings, queue management, customer service
2. Finance Manager - handles revenue, analytics, financial reporting
3. HR Assistant - handles employees, shifts, scheduling

As the Supervisor, you:
- Help the owner manage their business via natural chat
- Route complex requests to appropriate sub-agents
- Provide summaries and recommendations
- Ask clarifying questions when needed

Always be helpful, concise, and professional."""
    
    # Invoke LLM
    try:
        response = llm.invoke(messages)
    except Exception:
        fallback = AIMessage(
            content="I can help with operations across receptionist, finance, and HR. "
                    "Tell me what you want to do and I will route it to the right agent."
        )
        return {
            "messages": list(messages) + [fallback],
            "tool_results": state.get("tool_results")
        }
    
    # Add response to messages
    messages_with_response = list(messages) + [response]
    
    return {
        "messages": messages_with_response,
        "tool_results": None
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
    2. route_to_agent - decide which agent should handle it
    3. [receptionist/finance/hr OR respond] - handle or delegate
    4. END
    
    Returns:
        langgraph.graph.StateGraph instance ready to compile
    """
    
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("route_to_agent", route_to_agent)
    graph.add_node("receptionist", placeholder_receptionist)
    graph.add_node("finance", placeholder_finance)
    graph.add_node("hr", placeholder_hr)
    graph.add_node("approval_gate", approval_gate)
    graph.add_node("respond", respond)
    
    # Add edges
    graph.add_edge("classify_intent", "route_to_agent")
    
    # Conditional routing from route_to_agent
    graph.add_conditional_edges(
        "route_to_agent",
        lambda state: state.get("current_agent", "general"),
        {
            "booking": "receptionist",
            "finance": "finance",
            "hr": "hr",
            "general": "respond"
        }
    )
    
    # Sub-agents go through HITL gate before final response.
    graph.add_edge("receptionist", "approval_gate")
    graph.add_edge("finance", "approval_gate")
    graph.add_edge("hr", "approval_gate")
    graph.add_edge("approval_gate", "respond")
    
    # respond leads to END
    graph.add_edge("respond", END)
    
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
