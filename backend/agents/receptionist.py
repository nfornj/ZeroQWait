"""
Receptionist Sub-Agent — ReAct agent for booking, queue, and customer service.

Uses ``create_react_agent`` from langgraph.prebuilt so the LLM decides which
tools to call and in what order.  The 941-line classify-then-dispatch graph has
been replaced with:

1. A system prompt encoding the Receptionist's business rules.
2. Tenant-scoped tools created by ``make_receptionist_tools(shop_id)``.
3. ``create_react_agent`` which iterates: LLM → tool call → LLM → … → final answer.

HITL breakpoints:
- close_queue: ``interrupt_before`` pauses the graph for owner approval.
"""

import logging
import os

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from .tools.react_tools import make_receptionist_tools

logger = logging.getLogger(__name__)

# ── LLM factory ────────────────────────────────────────────────────

def _ollama_base_url() -> str:
    base_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1").rstrip("/")
    if base_url.endswith("/v1"):
        return base_url[:-3]
    return base_url


def _get_llm() -> ChatOllama:
    return ChatOllama(
        model=os.getenv("MODEL_NAME", "qwen3:14b-q4_K_M"),
        base_url=_ollama_base_url(),
        temperature=0.25,
        top_p=0.9,
        num_gpu=-1,
    )


# ── System prompt ──────────────────────────────────────────────────

RECEPTIONIST_SYSTEM_PROMPT = """\
You are the Receptionist agent for a service business on the ZeroQwait platform.

Your responsibilities:
- Queue management: check status, add customers, call next, close queue
- Service catalog: list, create, update, delete services
- Appointments: book, list, cancel, check available slots
- Customer guidance: provide wait times, service info, and clear next steps

Rules:
- Be warm, concise, and practical.
- Use ONLY data returned by your tools. Never invent numbers, names, or events.
- Do not mention internal systems, JSON, tools, or shop_id.
- No emojis.
- When you need to look up a service to update or delete it, call search_services first to find the ID.
- When booking an appointment, if the user hasn't specified a service or time, ask them before calling book_appointment.
- close_queue is a HIGH-IMPACT action — it will pause for owner approval automatically.
- Keep replies to short prose; bullets only for lists of services, queue items, or time slots.\
"""


# ── Agent builder ──────────────────────────────────────────────────

def create_receptionist_runnable(shop_id: int | None = None):
    """
    Build and compile the Receptionist ReAct agent.

    Parameters
    ----------
    shop_id : int | None
        Tenant ID for scoping tools. When ``None`` the caller must
        supply ``tenant_id`` in the state at invocation time.
    """
    if not shop_id:
        raise ValueError("shop_id is required — cannot create tenant-scoped tools without it")

    llm = _get_llm()
    tools = make_receptionist_tools(shop_id)

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=RECEPTIONIST_SYSTEM_PROMPT,
    )

    return agent


__all__ = ["create_receptionist_runnable"]
