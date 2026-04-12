"""
LangGraph agent framework for ZeroQwait AaaS platform.

This package contains:
- state.py: AgentState TypedDict shared across all graphs
- checkpoints.py: PostgreSQL checkpoint persistence setup
- supervisor.py: Central Supervisor agent graph (routes to sub-agents)
- receptionist.py: Customer-facing Receptionist sub-agent (bookings, queue)
- finance.py: Finance manager sub-agent (revenue, analytics)
- hr.py: HR assistant sub-agent (employees, shifts)
- tools/: Tool definitions for sub-agents (wraps MCP calls)

Architecture:
  Owner message → POST /api/v2/agent/chat/stream
    → JWT auth + tenant_id extraction
    → Load/create Supervisor graph checkpoint
    → Supervisor classifies intent → routes to sub-agent
    → Sub-agent executes tools via MCP servers
    → If HITL required: pause at interrupt_before, emit approval event
    → If no HITL: Supervisor formats response
    → SSE stream response to frontend + checkpoint to PostgreSQL
"""

__version__ = "0.1.0"
