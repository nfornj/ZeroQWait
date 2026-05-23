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


class InvoiceConfirmRequest(ShopRequest):
    invoice_id: int


class CompaniesListRequest(ShopRequest):
    limit: int = 50


class CompanyCreateRequest(ShopRequest):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None


class PaymentsListRequest(ShopRequest):
    limit: int = 50


class JournalEntriesRequest(ShopRequest):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 100


class ProductsListRequest(ShopRequest):
    limit: int = 50
    product_type: Optional[str] = None


class ProductCreateRequest(ShopRequest):
    name: str
    list_price: float
    product_type: str = "service"
    description: Optional[str] = None


class ProductUpdateRequest(ShopRequest):
    product_id: int
    updates: dict


class LowStockRequest(ShopRequest):
    threshold: float = 0


class DiagnoseAccessRequest(ShopRequest):
    models: Optional[list[str]] = None


class AggregateRecordsRequest(ShopRequest):
    model: str
    domain: Optional[list] = None
    fields: Optional[list[str]] = None
    groupby: Optional[list[str]] = None
    limit: int = 80


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
        company_id=cid,
    )


@app.post("/invoices/confirm")
async def rest_invoices_confirm(req: InvoiceConfirmRequest):
    return _odoo().confirm_invoice(invoice_id=req.invoice_id)


@app.post("/payments/register")
async def rest_payments_register(req: PaymentRegisterRequest):
    cid = _company_id(req.shop_id)
    return _odoo().register_payment(
        amount=req.amount,
        partner_id=req.partner_id,
        company_id=cid,
    )


@app.post("/payments/list")
async def rest_payments_list(req: PaymentsListRequest):
    cid = _company_id(req.shop_id)
    return _odoo().get_payments(limit=req.limit, company_id=cid)


@app.post("/companies/list")
async def rest_companies_list(req: CompaniesListRequest):
    cid = _company_id(req.shop_id)
    return _odoo().get_companies(limit=req.limit, company_id=cid)


@app.post("/companies/create")
async def rest_companies_create(req: CompanyCreateRequest):
    return _odoo().create_company(
        name=req.name,
        phone=req.phone,
        email=req.email,
        street=req.street,
        city=req.city,
    )


@app.post("/accounting/journal-entries")
async def rest_journal_entries(req: JournalEntriesRequest):
    cid = _company_id(req.shop_id)
    return _odoo().get_journal_entries(
        date_from=req.date_from,
        date_to=req.date_to,
        limit=req.limit,
        company_id=cid,
    )


@app.post("/accounting/balance")
async def rest_account_balance(req: ShopRequest):
    cid = _company_id(req.shop_id)
    return _odoo().get_account_balance(company_id=cid)


@app.post("/products/list")
async def rest_products_list(req: ProductsListRequest):
    cid = _company_id(req.shop_id)
    return _odoo().get_products(limit=req.limit, product_type=req.product_type, company_id=cid)


@app.post("/products/create")
async def rest_products_create(req: ProductCreateRequest):
    cid = _company_id(req.shop_id)
    return _odoo().create_product(
        name=req.name,
        list_price=req.list_price,
        product_type=req.product_type,
        company_id=cid,
        description=req.description,
    )


@app.post("/products/update")
async def rest_products_update(req: ProductUpdateRequest):
    return _odoo().update_product(product_id=req.product_id, updates=req.updates)


@app.post("/inventory/low-stock")
async def rest_low_stock(req: LowStockRequest):
    cid = _company_id(req.shop_id)
    return _odoo().get_low_stock_items(company_id=cid, threshold=req.threshold)


@app.post("/diagnostics/access")
async def rest_diagnose_access(req: DiagnoseAccessRequest):
    cid = _company_id(req.shop_id)
    return _odoo().diagnose_access(models=req.models, company_id=cid)


@app.post("/analytics/aggregate")
async def rest_aggregate_records(req: AggregateRecordsRequest):
    cid = _company_id(req.shop_id)
    return _odoo().aggregate_records(
        model=req.model,
        domain=req.domain,
        fields=req.fields,
        groupby=req.groupby,
        company_id=cid,
        limit=req.limit,
    )


@app.get("/leads/stages")
async def rest_lead_stages():
    return _odoo().get_lead_stages()


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

    @mcp.tool(description="Create a new customer invoice in Odoo for a shop.")
    async def create_invoice(shop_id: int, partner_id: int, lines: list) -> dict:
        return await rest_invoices_create(
            InvoiceCreateRequest(shop_id=shop_id, partner_id=partner_id, lines=lines)
        )

    @mcp.tool(description="Confirm (post) a draft invoice in Odoo. invoice_id is returned by create_invoice.")
    async def confirm_invoice(shop_id: int, invoice_id: int) -> dict:
        return await rest_invoices_confirm(
            InvoiceConfirmRequest(shop_id=shop_id, invoice_id=invoice_id)
        )

    @mcp.tool(description="Register a customer payment in Odoo for a shop.")
    async def register_payment(
        shop_id: int,
        amount: float,
        partner_id: int,
    ) -> dict:
        return await rest_payments_register(
            PaymentRegisterRequest(shop_id=shop_id, amount=amount, partner_id=partner_id)
        )

    @mcp.tool(description="List partner-companies/organizations in Odoo for a shop.")
    async def list_companies(shop_id: int, limit: int = 50) -> dict:
        return await rest_companies_list(CompaniesListRequest(shop_id=shop_id, limit=limit))

    @mcp.tool(description="Create a new Odoo company (for tenant isolation) associated with a shop.")
    async def create_company(
        shop_id: int,
        name: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        street: Optional[str] = None,
        city: Optional[str] = None,
    ) -> dict:
        return await rest_companies_create(
            CompanyCreateRequest(shop_id=shop_id, name=name, phone=phone, email=email, street=street, city=city)
        )

    @mcp.tool(description="List customer payments recorded in Odoo for a shop.")
    async def list_payments(shop_id: int, limit: int = 50) -> dict:
        return await rest_payments_list(PaymentsListRequest(shop_id=shop_id, limit=limit))

    @mcp.tool(description="Get accounting journal entries from Odoo for a shop, optionally filtered by date range.")
    async def get_journal_entries(
        shop_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
    ) -> dict:
        return await rest_journal_entries(
            JournalEntriesRequest(shop_id=shop_id, date_from=date_from, date_to=date_to, limit=limit)
        )

    @mcp.tool(description="Get account balances (debit/credit grouped by account) from Odoo for a shop.")
    async def get_account_balance(shop_id: int) -> dict:
        return await rest_account_balance(ShopRequest(shop_id=shop_id))

    @mcp.tool(description="List products and services in Odoo for a shop. product_type: 'service', 'consu', or 'product'.")
    async def list_products(
        shop_id: int,
        limit: int = 50,
        product_type: Optional[str] = None,
    ) -> dict:
        return await rest_products_list(
            ProductsListRequest(shop_id=shop_id, limit=limit, product_type=product_type)
        )

    @mcp.tool(description="Create a product or service in Odoo for a shop.")
    async def create_product(
        shop_id: int,
        name: str,
        list_price: float,
        product_type: str = "service",
        description: Optional[str] = None,
    ) -> dict:
        return await rest_products_create(
            ProductCreateRequest(
                shop_id=shop_id, name=name, list_price=list_price,
                product_type=product_type, description=description,
            )
        )

    @mcp.tool(description="Update fields on an existing Odoo product. Pass updates as a dict of field->value.")
    async def update_product(shop_id: int, product_id: int, updates: dict) -> dict:
        return await rest_products_update(
            ProductUpdateRequest(shop_id=shop_id, product_id=product_id, updates=updates)
        )

    @mcp.tool(description="Get low-stock items from Odoo inventory for a shop. threshold defaults to 0 (out-of-stock).")
    async def get_low_stock_items(shop_id: int, threshold: float = 0) -> dict:
        return await rest_low_stock(LowStockRequest(shop_id=shop_id, threshold=threshold))

    @mcp.tool(description="Diagnose read access to allowlisted Odoo models for a shop without changing data.")
    async def diagnose_access(shop_id: int, models: Optional[list[str]] = None) -> dict:
        return await rest_diagnose_access(DiagnoseAccessRequest(shop_id=shop_id, models=models))

    @mcp.tool(description="Aggregate allowlisted Odoo records with read_group for read-only diagnostics and analytics.")
    async def aggregate_records(
        shop_id: int,
        model: str,
        domain: Optional[list] = None,
        fields: Optional[list[str]] = None,
        groupby: Optional[list[str]] = None,
        limit: int = 80,
    ) -> dict:
        return await rest_aggregate_records(
            AggregateRecordsRequest(
                shop_id=shop_id,
                model=model,
                domain=domain,
                fields=fields,
                groupby=groupby,
                limit=limit,
            )
        )

    @mcp.tool(description="List available CRM pipeline stages in Odoo.")
    async def get_lead_stages(shop_id: int) -> dict:
        return await rest_lead_stages()

    try:
        app.mount("/mcp", mcp.sse_app())
    except AttributeError:
        logger.info("FastMCP SSE app not available; stdio MCP remains available.")
except ImportError:
    logger.warning("mcp package not installed — REST API remains available.")


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8893")))
