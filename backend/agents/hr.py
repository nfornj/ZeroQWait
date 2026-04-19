"""
HR Sub-Agent — ReAct agent for employees, shifts, and scheduling.

Uses ``create_react_agent`` from langgraph.prebuilt so the LLM decides which
tools to call and in what order.

HITL breakpoints:
- add_employee: ``interrupt_before`` pauses for owner approval.
"""

import logging
import os

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from .tools.react_tools import make_hr_tools

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
        temperature=0.2,
        top_p=0.9,
        num_gpu=-1,
    )


# ── System prompt ──────────────────────────────────────────────────

HR_SYSTEM_PROMPT = """\
You are the HR assistant agent for a service business on the ZeroQwait platform.

Your responsibilities:
- Employee management: list, add, deactivate employees
- Shift scheduling: view, assign, manage shifts
- Attendance tracking: clock in/out
- Availability checks: who is working, who is free

Rules:
- Be concise, professional, and action-oriented.
- Use ONLY data returned by your tools. Never fabricate names, schedules, or statuses.
- Do not mention internal systems, JSON, tools, or shop_id.
- No emojis.
- Use bullets only when listing employees, shifts, or availability groups.
- add_employee is a HIGH-IMPACT action — it will pause for owner approval automatically.
- When the user wants to add an employee, you must collect name and email at minimum before calling add_employee.\
"""


# ── Agent builder ──────────────────────────────────────────────────

def create_hr_runnable(shop_id: int | None = None):
    """
    Build and compile the HR ReAct agent.

    Parameters
    ----------
    shop_id : int | None
        Tenant ID for scoping tools. When ``None`` the caller must
        supply ``tenant_id`` in the state at invocation time.
    """
    if not shop_id:
        raise ValueError("shop_id is required — cannot create tenant-scoped tools without it")

    llm = _get_llm()
    tools = make_hr_tools(shop_id)

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=HR_SYSTEM_PROMPT,
    )

    return agent


__all__ = ["create_hr_runnable"]
