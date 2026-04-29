"""
CRM Agent — dispatches owner CRM/ERP commands to Odoo via structured LLM output.

The agent uses ``llm.with_structured_output(CRMToolCall)`` to pick the right
Odoo tool and extract arguments, replacing the previous 200-line regex if/elif
chain that lived in supervisor.py.

Follows the same ``run_crm_agent(state) -> dict`` async interface used by
``execute_plan`` in the Supervisor graph.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from .state import AgentState
from .tools import odoo_tools

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured output model — the LLM fills this in for each CRM request
# ---------------------------------------------------------------------------

class CRMToolCall(BaseModel):
    """LLM-selected CRM tool and extracted arguments."""

    thought: str = Field(
        description="One-sentence reason why this tool was chosen."
    )
    tool: Literal[
        "get_pipeline_summary",
        "get_leads",
        "get_companies",
        "get_lead_stages",
        "move_lead_stage",
        "create_lead",
        "add_lead_note",
        "get_contacts",
        "create_contact",
        "update_contact",
        "search_contact",
        "get_invoices",
        "create_invoice",
        "get_payments",
        "get_products",
        "get_revenue_summary",
        "get_account_balance",
    ] = Field(description="The Odoo tool to call.")

    # --- identity fields (used by multiple tools) ---
    lead_id: Optional[int] = Field(None, description="Odoo lead/opportunity ID.")
    contact_id: Optional[int] = Field(None, description="Odoo contact (res.partner) ID.")

    # --- name / text fields ---
    name: Optional[str] = Field(None, description="Name for a new lead or contact.")
    search_name: Optional[str] = Field(None, description="Name to search for in contacts.")
    note_text: Optional[str] = Field(None, description="Body text for a lead note.")
    stage_name: Optional[str] = Field(None, description="Target pipeline stage name.")

    # --- contact create/update fields ---
    email: Optional[str] = Field(None, description="Email address for contact create/update.")
    phone: Optional[str] = Field(None, description="Phone number for contact create/update.")

    # --- financial fields ---
    expected_revenue: Optional[float] = Field(None, description="Expected revenue for a new lead.")
    invoice_amount: Optional[float] = Field(None, description="Invoice line amount.")


# ---------------------------------------------------------------------------
# Tool dispatcher — maps CRMToolCall → actual odoo_tools call
# ---------------------------------------------------------------------------

async def _dispatch(call: CRMToolCall, shop_id: int) -> Dict[str, Any]:
    """Execute the tool selected by the LLM."""
    t = call.tool

    if t == "get_pipeline_summary":
        return await odoo_tools.odoo_get_pipeline_summary(shop_id=shop_id)
    if t == "get_leads":
        return await odoo_tools.odoo_get_leads(shop_id=shop_id)
    if t == "get_companies":
        return await odoo_tools.odoo_get_companies(shop_id=shop_id)
    if t == "get_lead_stages":
        return await odoo_tools.odoo_get_lead_stages(shop_id=shop_id)
    if t == "move_lead_stage":
        if not call.lead_id or not call.stage_name:
            return {"error": "move_lead_stage requires a lead_id and stage_name"}
        return await odoo_tools.odoo_update_lead_stage(call.lead_id, call.stage_name)
    if t == "create_lead":
        return await odoo_tools.odoo_create_lead(
            name=call.name or "New Lead",
            shop_id=shop_id,
            expected_revenue=call.expected_revenue or 0.0,
        )
    if t == "add_lead_note":
        if not call.lead_id or not call.note_text:
            return {"error": "add_lead_note requires a lead_id and note_text"}
        return await odoo_tools.odoo_add_note_to_lead(call.lead_id, call.note_text)
    if t == "get_contacts":
        return await odoo_tools.odoo_get_contacts(shop_id=shop_id)
    if t == "create_contact":
        if not call.name:
            return {"error": "create_contact requires a name"}
        return await odoo_tools.odoo_create_contact(
            name=call.name,
            shop_id=shop_id,
            email=call.email,
            phone=call.phone,
        )
    if t == "update_contact":
        if not call.contact_id:
            return {"error": "update_contact requires a contact_id"}
        return await odoo_tools.odoo_update_contact(
            contact_id=call.contact_id,
            email=call.email,
            phone=call.phone,
        )
    if t == "search_contact":
        return await odoo_tools.odoo_search_contact(
            name=call.search_name or call.name or "",
            shop_id=shop_id,
        )
    if t == "get_invoices":
        return await odoo_tools.odoo_get_invoices(shop_id=shop_id)
    if t == "create_invoice":
        amount = call.invoice_amount or 0.0
        lines = [{"name": call.name or "Service", "quantity": 1, "price_unit": amount}]
        return await odoo_tools.odoo_create_invoice(partner_id=1, lines=lines, shop_id=shop_id)
    if t == "get_payments":
        return await odoo_tools.odoo_get_payments(shop_id=shop_id)
    if t == "get_products":
        return await odoo_tools.odoo_get_products(shop_id=shop_id)
    if t == "get_revenue_summary":
        return await odoo_tools.odoo_get_revenue_summary(shop_id=shop_id)
    if t == "get_account_balance":
        return await odoo_tools.odoo_get_account_balance(shop_id=shop_id)

    return {"error": f"Unknown CRM tool: {t}"}


# ---------------------------------------------------------------------------
# Main entry point — called by execute_plan in supervisor.py
# ---------------------------------------------------------------------------

_TOOL_SELECTION_SYSTEM_PROMPT = """\
You are the CRM tool selector for ZeroQwait. Your job is to pick the single
best Odoo CRM/ERP tool that answers the shop owner's request.

Available tools:
- get_pipeline_summary: Overview of all pipeline stages with totals
- get_leads: List all leads/opportunities
- get_companies: List all Odoo companies
- get_lead_stages: List available pipeline stages
- move_lead_stage: Move lead to a different stage (needs lead_id + stage_name)
- create_lead: Create a new CRM lead (needs name; optional expected_revenue)
- add_lead_note: Add a note/comment to a lead (needs lead_id + note_text)
- get_contacts: List all contacts
- create_contact: Create a new contact (needs name; optional email, phone)
- update_contact: Update contact email/phone (needs contact_id)
- search_contact: Search contacts by name (needs search_name)
- get_invoices: List invoices
- create_invoice: Create an invoice (needs name + invoice_amount)
- get_payments: List payments
- get_products: List products/services catalog
- get_revenue_summary: Odoo revenue summary
- get_account_balance: Accounting balances and journal entries

Always extract IDs and names precisely from the owner's message.
"""

_RESPONSE_SYSTEM_PROMPT = """\
You are the CRM assistant for shop (shop_id={shop_id}).
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

Owner asked: {user_text}\
"""


async def run_crm_agent(state: AgentState) -> dict:
    """
    CRM specialist agent — dispatches to Odoo via LLM-selected tool.

    1. LLM selects the right Odoo tool and extracts arguments.
    2. Tool is called against the Odoo XML-RPC API.
    3. LLM formats the raw Odoo data into a natural response.
    """
    user_text = _latest_user_text(state)
    messages = list(state.get("messages", []) or [])
    shop_id = state.get("tenant_id") or 0

    llm = _get_llm(state)

    # --- Step 1: tool selection via structured output ---
    tool_call: Optional[CRMToolCall] = None
    try:
        structured_llm = llm.with_structured_output(CRMToolCall)
        tool_call = structured_llm.invoke(
            [
                SystemMessage(content=_TOOL_SELECTION_SYSTEM_PROMPT),
                HumanMessage(content=user_text),
            ]
        )
        logger.info(
            "CRM tool selected: %s (thought: %s)",
            tool_call.tool if tool_call else "None",
            tool_call.thought if tool_call else "",
        )
    except Exception as exc:
        logger.warning("CRM tool selection failed: %s", exc)

    # --- Step 2: execute the tool ---
    if tool_call is not None:
        try:
            data: Dict[str, Any] = await _dispatch(tool_call, shop_id)
        except Exception as exc:
            logger.error("CRM tool dispatch error: %s", exc)
            data = {"error": str(exc)}
    else:
        # Fallback: list contacts as a safe default
        try:
            data = await odoo_tools.odoo_get_contacts(shop_id=shop_id)
        except Exception as exc:
            data = {"error": str(exc)}

    # --- Step 3: format with LLM ---
    response_prompt = _RESPONSE_SYSTEM_PROMPT.format(
        shop_id=shop_id,
        data=data,
        user_text=user_text,
    )
    try:
        response = llm.invoke(
            messages + [SystemMessage(content=response_prompt)]
        )
    except Exception as exc:
        response = AIMessage(
            content=f"I retrieved your Odoo data but had trouble formatting it: {exc}"
        )

    return {
        "messages": messages + [response],
        "current_agent": "crm",
        "tool_results": {"crm_data": data},
    }


# ---------------------------------------------------------------------------
# Private helpers (avoid circular imports — replicate what supervisor uses)
# ---------------------------------------------------------------------------

def _latest_user_text(state: AgentState) -> str:
    """Return the most recent HumanMessage content from state."""
    for msg in reversed(list(state.get("messages", []) or [])):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    return ""


def _get_llm(state: AgentState):
    """Return the configured chat model via the shared supervisor helper."""
    from .supervisor import get_llm
    return get_llm(state, temperature=0)
