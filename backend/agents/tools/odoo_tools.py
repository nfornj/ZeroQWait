"""Odoo ERP agent tools — plain async Python functions.

Called by the supervisor when ODOO_ENABLED=true.
Maps to OdooClient methods in backend/integrations/odoo_client.py.
"""

from typing import Any, Dict, List, Optional

from integrations.odoo_client import odoo_client


# ── Health ────────────────────────────────────────────────────────

async def odoo_health() -> Dict[str, Any]:
    """Check Odoo connectivity and return version info."""
    return odoo_client.health_check()


# ── CRM: Contacts ────────────────────────────────────────────────

async def odoo_get_contacts(limit: int = 50) -> Dict[str, Any]:
    """List CRM contacts (customers)."""
    return odoo_client.get_contacts(limit=limit)


async def odoo_search_contact(name: str) -> Dict[str, Any]:
    """Search contacts by name."""
    return odoo_client.search_contact(name)


async def odoo_create_contact(
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    company_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new contact in Odoo CRM."""
    return odoo_client.create_contact(name, email, phone, company_name)


# ── CRM: Companies ───────────────────────────────────────────────

async def odoo_get_companies(limit: int = 50) -> Dict[str, Any]:
    """List companies / organizations."""
    return odoo_client.get_companies(limit=limit)


# ── CRM: Leads / Pipeline ────────────────────────────────────────

async def odoo_get_leads(limit: int = 50, stage: Optional[str] = None) -> Dict[str, Any]:
    """List CRM leads/opportunities."""
    return odoo_client.get_leads(limit=limit, stage=stage)


async def odoo_get_pipeline_summary() -> Dict[str, Any]:
    """Get CRM pipeline summary grouped by stage."""
    return odoo_client.get_pipeline_summary()


# ── Invoicing ─────────────────────────────────────────────────────

async def odoo_get_invoices(limit: int = 50, state: Optional[str] = None) -> Dict[str, Any]:
    """List customer invoices from Odoo."""
    return odoo_client.get_invoices(limit=limit, state=state)


async def odoo_create_invoice(
    partner_id: int,
    lines: List[Dict[str, Any]],
    invoice_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a customer invoice in Odoo.

    Args:
        partner_id: Odoo partner (customer) ID.
        lines: List of dicts with keys: name, quantity, price_unit.
        invoice_date: ISO date string (defaults to today).
    """
    return odoo_client.create_invoice(partner_id, lines, invoice_date)


async def odoo_confirm_invoice(invoice_id: int) -> Dict[str, Any]:
    """Post/confirm a draft invoice."""
    return odoo_client.confirm_invoice(invoice_id)


# ── Payments ──────────────────────────────────────────────────────

async def odoo_get_payments(limit: int = 50) -> Dict[str, Any]:
    """List customer payments from Odoo."""
    return odoo_client.get_payments(limit=limit)


async def odoo_register_payment(
    amount: float,
    partner_id: int,
    journal_id: int = 1,
    ref: Optional[str] = None,
) -> Dict[str, Any]:
    """Register and confirm a customer payment in Odoo."""
    return odoo_client.register_payment(amount, partner_id, journal_id, ref=ref)


# ── Accounting ────────────────────────────────────────────────────

async def odoo_get_journal_entries(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """Fetch journal entries from Odoo."""
    return odoo_client.get_journal_entries(date_from, date_to, limit)


async def odoo_get_account_balance() -> Dict[str, Any]:
    """Get trial balance (account balances by account type)."""
    return odoo_client.get_account_balance()


async def odoo_get_revenue_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Revenue summary from posted invoices in a date range."""
    return odoo_client.get_revenue_summary(date_from, date_to)


# ── Products / Services ──────────────────────────────────────────

async def odoo_get_products(limit: int = 50, product_type: Optional[str] = None) -> Dict[str, Any]:
    """List products/services from Odoo."""
    return odoo_client.get_products(limit=limit, product_type=product_type)
