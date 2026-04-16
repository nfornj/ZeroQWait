"""Odoo ERP agent tools — plain async Python functions.

Called by the supervisor when ODOO_ENABLED=true.
Maps to OdooClient methods in backend/integrations/odoo_client.py.

Multi-tenancy: Every tool accepts ``shop_id``, resolves it to the Odoo
``company_id`` via the ``shops.odoo_company_id`` column, and passes
that to the client so all data is isolated per shop.
"""

import logging
from typing import Any, Dict, List, Optional

from integrations.odoo_client import odoo_client
from database import SessionLocal
from modules.shops.models import Shop

logger = logging.getLogger(__name__)


def _get_odoo_company_id(shop_id: int) -> Optional[int]:
    """Look up the Odoo company_id for a ZeroQwait shop.

    Returns None if the shop has no Odoo company provisioned yet.
    """
    if not shop_id:
        return None
    db = SessionLocal()
    try:
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if shop and shop.odoo_company_id:
            return shop.odoo_company_id
        return None
    finally:
        db.close()


# ── Health ────────────────────────────────────────────────────────

async def odoo_health() -> Dict[str, Any]:
    """Check Odoo connectivity and return version info."""
    return odoo_client.health_check()


# ── Company Provisioning ─────────────────────────────────────────

async def odoo_provision_shop(shop_id: int, name: str,
                              phone: Optional[str] = None,
                              email: Optional[str] = None,
                              city: Optional[str] = None) -> Dict[str, Any]:
    """Create an Odoo company for a ZeroQwait shop and persist the mapping."""
    result = odoo_client.create_company(name=name, phone=phone, email=email, city=city)
    if "error" in result:
        return result
    odoo_company_id = result["id"]
    # Persist the mapping
    db = SessionLocal()
    try:
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if shop:
            shop.odoo_company_id = odoo_company_id
            db.commit()
            logger.info("Shop %s (%s) linked to Odoo company %s", shop_id, name, odoo_company_id)
        else:
            return {"error": f"Shop {shop_id} not found in database"}
    finally:
        db.close()
    return {"odoo_company_id": odoo_company_id, "shop_id": shop_id, "name": name}


# ── CRM: Contacts ────────────────────────────────────────────────

async def odoo_get_contacts(shop_id: int = 0, limit: int = 50) -> Dict[str, Any]:
    """List CRM contacts (customers) for this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.get_contacts(limit=limit, company_id=cid)


async def odoo_search_contact(name: str, shop_id: int = 0) -> Dict[str, Any]:
    """Search contacts by name within this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.search_contact(name, company_id=cid)


async def odoo_create_contact(
    name: str,
    shop_id: int = 0,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    company_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new contact in Odoo CRM for this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.create_contact(name, email, phone, company_name, company_id=cid)


# ── CRM: Companies ───────────────────────────────────────────────

async def odoo_get_companies(shop_id: int = 0, limit: int = 50) -> Dict[str, Any]:
    """List companies / organizations for this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.get_companies(limit=limit, company_id=cid)


# ── CRM: Leads / Pipeline ────────────────────────────────────────

async def odoo_get_leads(shop_id: int = 0, limit: int = 50, stage: Optional[str] = None) -> Dict[str, Any]:
    """List CRM leads/opportunities for this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.get_leads(limit=limit, stage=stage, company_id=cid)


async def odoo_get_pipeline_summary(shop_id: int = 0) -> Dict[str, Any]:
    """Get CRM pipeline summary grouped by stage for this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.get_pipeline_summary(company_id=cid)


# ── Invoicing ─────────────────────────────────────────────────────

async def odoo_get_invoices(shop_id: int = 0, limit: int = 50, state: Optional[str] = None) -> Dict[str, Any]:
    """List customer invoices from Odoo for this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.get_invoices(limit=limit, state=state, company_id=cid)


async def odoo_create_invoice(
    partner_id: int,
    lines: List[Dict[str, Any]],
    shop_id: int = 0,
    invoice_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a customer invoice in Odoo for this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.create_invoice(partner_id, lines, invoice_date, company_id=cid)


async def odoo_confirm_invoice(invoice_id: int) -> Dict[str, Any]:
    """Post/confirm a draft invoice."""
    return odoo_client.confirm_invoice(invoice_id)


# ── Payments ──────────────────────────────────────────────────────

async def odoo_get_payments(shop_id: int = 0, limit: int = 50) -> Dict[str, Any]:
    """List customer payments from Odoo for this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.get_payments(limit=limit, company_id=cid)


async def odoo_register_payment(
    amount: float,
    partner_id: int,
    shop_id: int = 0,
    journal_id: int = 1,
    ref: Optional[str] = None,
) -> Dict[str, Any]:
    """Register and confirm a customer payment in Odoo for this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.register_payment(amount, partner_id, journal_id, ref=ref, company_id=cid)


# ── Accounting ────────────────────────────────────────────────────

async def odoo_get_journal_entries(
    shop_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """Fetch journal entries from Odoo for this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.get_journal_entries(date_from, date_to, limit, company_id=cid)


async def odoo_get_account_balance(shop_id: int = 0) -> Dict[str, Any]:
    """Get trial balance (account balances by account type) for this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.get_account_balance(company_id=cid)


async def odoo_get_revenue_summary(
    shop_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Revenue summary from posted invoices for this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.get_revenue_summary(date_from, date_to, company_id=cid)


# ── Products / Services ──────────────────────────────────────────

async def odoo_get_products(shop_id: int = 0, limit: int = 50, product_type: Optional[str] = None) -> Dict[str, Any]:
    """List products/services from Odoo for this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.get_products(limit=limit, product_type=product_type, company_id=cid)


# ── CRM: Lead Management ─────────────────────────────────────────

async def odoo_create_lead(
    name: str,
    shop_id: int = 0,
    partner_id: Optional[int] = None,
    expected_revenue: float = 0.0,
    description: Optional[str] = None,
    lead_type: str = "opportunity",
) -> Dict[str, Any]:
    """Create a CRM lead/opportunity for this shop."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.create_lead(
        name=name, partner_id=partner_id, expected_revenue=expected_revenue,
        description=description, lead_type=lead_type, company_id=cid,
    )


async def odoo_update_lead_stage(lead_id: int, stage_name: str) -> Dict[str, Any]:
    """Move a CRM lead to a different pipeline stage."""
    return odoo_client.update_lead_stage(lead_id, stage_name)


async def odoo_add_note_to_lead(lead_id: int, body: str) -> Dict[str, Any]:
    """Add a note to a CRM lead."""
    return odoo_client.add_note_to_lead(lead_id, body)


async def odoo_get_lead_stages(shop_id: int = 0) -> Dict[str, Any]:
    """List available CRM pipeline stages."""
    cid = _get_odoo_company_id(shop_id)
    return odoo_client.get_lead_stages(company_id=cid)


# ── CRM: Contact Management ──────────────────────────────────────

async def odoo_update_contact(
    contact_id: int,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    city: Optional[str] = None,
) -> Dict[str, Any]:
    """Update an existing contact's details."""
    return odoo_client.update_contact(contact_id, name=name, email=email, phone=phone, city=city)
