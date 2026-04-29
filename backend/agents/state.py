"""
Shared AgentState TypedDict for all LangGraph agent graphs.

This state is:
- Immutable for tenant_id (injected at entry point, agents cannot change)
- Thread-scoped per tenant: thread_id = f"tenant_{shop_id}_{user_id}"
- Checkpointed to PostgreSQL after each graph step
- Passed through all sub-agents and tool nodes
"""

from typing import TypedDict, Annotated, Sequence, Optional, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Unified state passed through all agent graphs.
    
    Fields:
    - messages: LangChain message history (reduced via add_messages)
    - tenant_id: Shop ID (immutable, injected at entry point)
    - user_id: Authenticated owner's user ID
    - current_agent: Name of active agent ("supervisor", "receptionist", "finance", "hr")
    - active_goal_id: Durable goal currently being worked
    - active_task_id: Durable task currently being worked
    - execution_mode: Interactive chat vs background/autonomous execution mode
    - autonomy_policy: Current policy mode or policy bundle being applied
    - event_context: Trigger metadata for scheduled jobs, anomalies, reminders, etc.
    - proposed_actions: Structured actions under consideration before execution
    - run_summary: Summary of the current run for notifications/history
    - pending_approval: High-impact action awaiting owner approval (dict or None)
    - tool_results: Latest tool execution results (dict or None)
    - needs_human_input: True when at interrupt_before breakpoint
    - metadata: Optional extra context (routing hints, conversation context, etc.)
    """
    
    # Message history (Annotated with add_messages reducer)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Multi-tenancy isolation
    tenant_id: int
    user_id: int
    
    # Agent routing & state
    current_agent: str
    active_goal_id: Optional[int]
    active_task_id: Optional[int]
    execution_mode: Optional[str]
    autonomy_policy: Optional[dict]
    event_context: Optional[dict]
    proposed_actions: Optional[list[dict[str, Any]]]
    run_summary: Optional[dict]
    
    # Human-in-the-Loop (HITL) breakpoints
    pending_approval: Optional[dict]
    needs_human_input: bool
    
    # Tool execution results
    tool_results: Optional[dict]
    
    # Optional metadata
    metadata: Optional[dict]


# Export for graph builders
__all__ = ["AgentState"]
