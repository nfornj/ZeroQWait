"""Odoo MCP server — wraps OdooClient as REST + MCP tools for agent use."""

from pathlib import Path
from typing import Optional
import logging
import os
import sys

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from integrations.odoo_client import OdooClient  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("odoo-mcp")

app = FastAPI(title="ZeroQwait Odoo MCP", version="1.0.0")

_client: Optional[OdooClient] = None


def _odoo() -> OdooClient:
    global _client
    if _client is None:
        _client = OdooClient()
    return _client


# ── Pydantic request models ────────────────────────────────────────────────────


class ShopRequest(BaseModel):
    shop_id: int


class ContactsListRequest(ShopRequest):
    limit: int = 50
    customer_only: bool = True


class ContactSearchRequest(ShopRequest):
    name: str


class ContactCreateRequest(ShopRequest):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None


class ContactUpdateRequest(ShopRequest):
    contact_id: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None


class LeadsListRequest(ShopRequest):
    stage: Optional[str] = None
    limit: int = 50


class LeadCreateRequest(ShopRequest):
    name: str
    partner_id: Optional[int] = None
    expected_revenue: Optional[float] = None
    description: Optional[str] = None
    lead_type: str = "opportunity"


class LeadMoveRequest(ShopRequest):
    lead_id: int
    stage_name: str


class LeadNoteRequest(ShopRequest):
    lead_id: int
    note: str


class InvoicesListRequest(ShopRequest):
    state: Optional[str] = None
    limit: int = 50


class InvoiceCreateRequest(ShopRequest):
    partner_id: int
    lines: list
    currency: str = "USD"


class PaymentRegisterRequest(ShopRequest):
    amount: float
    partner_id: int
    invoice_id: Optional[int] = None
    payment_date: Optional[str] = None
    journal_name: Optional[str] = None


# ── REST endpoints ─────────────────────────────────────────────────────────────


def _company_id(shop_id: int) -> Optional[int]:
    """Look up shop's odoo_company_id from DB if available, else None."""
    try:
        from database import SessionLocal
        from modules.shops.models import Shop  # noqa: F401
        import models  # noqa: F401
        from sqlalchemy import text
        db = SessionLocal()
        try:
            row = db.execute(
                text("SELECT odoo_company_id FROM shops WHERE id = :sid"),
                {"sid": shop_id},
            ).fetchone()
            return row[0] if row and row[0] else None
        finally:
            db.close()
    except Exception as e:
        logger.debug("Could not resolve odoo_company_id for shop %s: %s", shop_id, e)
        return None


@app.post("/contacts/list")
async def rest_contacts_list(req: ContactsListRequest):
    cid = _company_id(req.shop_id)
    return _odoo().get_contacts(limit=req.limit, customer_only=req.customer_only, company_id=cid)


@app.post("/contacts/search")
async def rest_contacts_search(req: ContactSearchRequest):
    cid = _company_id(req.shop_id)
    return _odoo().search_contact(req.name, company_id=cid)


@app.post("/contacts/create")
async def rest_contacts_create(req: ContactCreateRequest):
    cid = _company_id(req.shop_id)
    return _odoo().create_contact(
        name=req.name,
        email=req.email,
        phone=req.phone,
        company_name=req.company_name,
        company_id=cid,
    )


@app.post("/contacts/update")
async def rest_contacts_update(req: ContactUpdateRequest):
    return _odoo().update_contact(
        contact_id=req.contact_id,
        name=req.name,
        email=req.email,
        phone=req.phone,
        city=req.city,
    )


@app.post("/leads/list")
async def rest_leads_list(req: LeadsListRequest):
    cid = _company_id(req.shop_id)
    return _odoo().get_leads(stage=req.stage, limit=req.limit, company_id=cid)


@app.post("/leads/create")
async def rest_leads_create(req: LeadCreateRequest):
    cid = _company_id(req.shop_id)
    return _odoo().create_lead(
        name=req.name,
        partner_id=req.partner_id,
        expected_revenue=req.expected_revenue or 0.0,
        description=req.description,
        lead_type=req.lead_type,
        company_id=cid,
    )


@app.post("/leads/move")
async def rest_leads_move(req: LeadMoveRequest):
    return _odoo().update_lead_stage(lead_id=req.lead_id, stage_name=req.stage_name)


@app.post("/leads/note")
async def rest_leads_note(req: LeadNoteRequest):
    return _odoo().add_note_to_lead(lead_id=req.lead_id, body=req.note)


@app.post("/pipeline/summary")
async def rest_pipeline_summary(req: ShopRequest):
    cid = _company_id(req.shop_id)
    return _odoo().get_pipeline_summary(company_id=cid)


@app.post("/invoices/list")
async def rest_invoices_list(req: InvoicesListRequest):
    cid = _company_id(req.shop_id)
    return _odoo().get_invoices(state=req.state, limit=req.limit, company_id=cid)


@app.post("/invoices/create")
async def rest_invoices_create(req: InvoiceCreateRequest):
    cid = _company_id(req.shop_id)
    return _odoo().create_invoice(
        partner_id=req.partner_id,
        lines=req.lines,
        currency=req.currency,
        company_id=cid,
    )


@app.post("/invoices/confirm")
async def rest_invoices_confirm(req: ShopRequest):
    return {"error": "Missing invoice_id in request"}


@app.post("/payments/register")
async def rest_payments_register(req: PaymentRegisterRequest):
    cid = _company_id(req.shop_id)
    return _odoo().register_payment(
        amount=req.amount,
        partner_id=req.partner_id,
        company_id=cid,
    )


@app.post("/revenue/summary")
async def rest_revenue_summary(req: ShopRequest):
    cid = _company_id(req.shop_id)
    return _odoo().get_revenue_summary(company_id=cid)


@app.get("/health")
async def health():
    odoo_status = _odoo().health_check()
    return {"status": "ok", "service": "odoo-mcp", "odoo": odoo_status}


# ── MCP tools ─────────────────────────────────────────────────────────────────


try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        name="zeroqwait-odoo",
        instructions="Odoo ERP tools for CRM contacts, leads, invoices, and pipeline management.",
    )

    @mcp.tool(description="List CRM contacts for a shop.")
    async def list_contacts(shop_id: int, limit: int = 50, customer_only: bool = True) -> dict:
        return await rest_contacts_list(ContactsListRequest(shop_id=shop_id, limit=limit, customer_only=customer_only))

    @mcp.tool(description="Search CRM contacts by name for a shop.")
    async def search_contact(shop_id: int, name: str) -> dict:
        return await rest_contacts_search(ContactSearchRequest(shop_id=shop_id, name=name))

    @mcp.tool(description="Create a new CRM contact for a shop.")
    async def create_contact(
        shop_id: int,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        company_name: Optional[str] = None,
    ) -> dict:
        return await rest_contacts_create(
            ContactCreateRequest(shop_id=shop_id, name=name, email=email, phone=phone, company_name=company_name)
        )

    @mcp.tool(description="Update an existing CRM contact.")
    async def update_contact(
        shop_id: int,
        contact_id: int,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        city: Optional[str] = None,
    ) -> dict:
        return await rest_contacts_update(
            ContactUpdateRequest(shop_id=shop_id, contact_id=contact_id, name=name, email=email, phone=phone, city=city)
        )

    @mcp.tool(description="List CRM leads/opportunities for a shop.")
    async def list_leads(shop_id: int, stage: Optional[str] = None, limit: int = 50) -> dict:
        return await rest_leads_list(LeadsListRequest(shop_id=shop_id, stage=stage, limit=limit))

    @mcp.tool(description="Create a new CRM lead/opportunity for a shop.")
    async def create_lead(
        shop_id: int,
        name: str,
        partner_id: Optional[int] = None,
        expected_revenue: Optional[float] = None,
        description: Optional[str] = None,
        lead_type: str = "opportunity",
    ) -> dict:
        return await rest_leads_create(
            LeadCreateRequest(
                shop_id=shop_id,
                name=name,
                partner_id=partner_id,
                expected_revenue=expected_revenue,
                description=description,
                lead_type=lead_type,
            )
        )

    @mcp.tool(description="Move a CRM lead to a different pipeline stage.")
    async def move_lead(shop_id: int, lead_id: int, stage_name: str) -> dict:
        return await rest_leads_move(LeadMoveRequest(shop_id=shop_id, lead_id=lead_id, stage_name=stage_name))

    @mcp.tool(description="Add a note to a CRM lead.")
    async def add_lead_note(shop_id: int, lead_id: int, note: str) -> dict:
        return await rest_leads_note(LeadNoteRequest(shop_id=shop_id, lead_id=lead_id, note=note))

    @mcp.tool(description="Get CRM pipeline summary grouped by stage for a shop.")
    async def get_pipeline_summary(shop_id: int) -> dict:
        return await rest_pipeline_summary(ShopRequest(shop_id=shop_id))

    @mcp.tool(description="List invoices for a shop.")
    async def list_invoices(shop_id: int, state: Optional[str] = None, limit: int = 50) -> dict:
        return await rest_invoices_list(InvoicesListRequest(shop_id=shop_id, state=state, limit=limit))

    @mcp.tool(description="Get revenue summary from Odoo accounting for a shop.")
    async def get_revenue_summary(shop_id: int) -> dict:
        return await rest_revenue_summary(ShopRequest(shop_id=shop_id))

    try:
        app.mount("/mcp", mcp.sse_app())
    except AttributeError:
        logger.info("FastMCP SSE app not available; stdio MCP remains available.")
except ImportError:
    logger.warning("mcp package not installed — REST API remains available.")


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8893")))
