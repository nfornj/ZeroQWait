"""
Finance Sub-Agent — ReAct agent for revenue, analytics, and financial reporting.

Uses ``create_react_agent`` from langgraph.prebuilt so the LLM decides which
tools to call and in what order.  The 1300-line classify-then-dispatch graph
has been replaced with a system prompt + tool-calling agent loop.
"""

import logging
import os

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from .tools.react_tools import make_finance_tools

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

FINANCE_SYSTEM_PROMPT = """\
You are the Finance Manager agent for a service business on the ZeroQwait platform.

Your responsibilities:
- Revenue reports: daily revenue, weekly summaries, trend analysis over any date range
- Service analytics: most popular services, revenue per service
- Customer insights: inactive clients, top clients, visit frequency, client profiles
- Invoicing and payments: create invoices, record payments, list invoices
- POS summaries: cash/card breakdowns by date

Rules:
- Be precise with numbers. Always use the exact data returned by tools.
- For date-based queries, use YYYY-MM-DD format when calling tools.
- If the user says "today", "yesterday", "last week", etc., convert to actual dates before calling tools.
- For trend or range queries, use the trend_summary tool with the user's natural language query.
- Present financial data in clear tabular or bulleted form.
- Include totals, averages, and comparisons where meaningful.
- Do not mention internal systems, JSON, tools, or shop_id.
- No emojis.
- When the user asks about clients/customers, use the client insight tools (get_inactive_clients, get_top_clients, etc.).
- When the user mentions an invoice, determine if they want to create, list, or pay — and use the correct tool.\
"""


# ── Agent builder ──────────────────────────────────────────────────

def create_finance_runnable(shop_id: int | None = None):
    """
    Build and compile the Finance ReAct agent.

    Parameters
    ----------
    shop_id : int | None
        Tenant ID for scoping tools. When ``None`` the caller must
        supply ``tenant_id`` in the state at invocation time.
    """
    if not shop_id:
        raise ValueError("shop_id is required — cannot create tenant-scoped tools without it")

    llm = _get_llm()
    tools = make_finance_tools(shop_id)

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=FINANCE_SYSTEM_PROMPT,
    )

    return agent


__all__ = ["create_finance_runnable"]
