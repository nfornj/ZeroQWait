"""Odoo ERP Client — full integration with Odoo 17 via XML-RPC.

Covers: CRM, Invoicing, Payments, Accounting, Products, and basic HR.
When ODOO_ENABLED=true, all queries route through Odoo's XML-RPC API.
When ODOO_ENABLED=false, returns disabled-status dicts so callers can
fall back to local data gracefully.
"""

import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import xmlrpc.client

logger = logging.getLogger(__name__)

ODOO_ENABLED = os.getenv("ODOO_ENABLED", "false").lower() in ("true", "1", "yes")
ODOO_URL = os.getenv("ODOO_URL", "http://odoo:8069")
ODOO_DB = os.getenv("ODOO_DB", "odoo")
ODOO_USER = os.getenv("ODOO_USER", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")

_DISABLED = {"enabled": False, "message": "Odoo integration is disabled"}


class OdooClient:
    """Full Odoo 17 XML-RPC client for ERP operations."""

    def __init__(self):
        self.enabled = ODOO_ENABLED
        self._uid: Optional[int] = None
        self._models: Optional[xmlrpc.client.ServerProxy] = None
        if self.enabled:
            try:
                self._connect()
            except Exception as e:
                logger.warning("Odoo connection failed at init — will retry on demand: %s", e)

    # ── Connection ────────────────────────────────────────────────

    def _connect(self):
        common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
        self._uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        if not self._uid:
            raise ConnectionError("Odoo authentication failed — check ODOO_DB, ODOO_USER, ODOO_PASSWORD")
        self._models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
        logger.info("Connected to Odoo (uid=%s, db=%s)", self._uid, ODOO_DB)

    def _ensure_connected(self):
        if self._uid is None or self._models is None:
            self._connect()

    def _execute(self, model: str, method: str, *args, **kwargs):
        if not self.enabled:
            return None
        self._ensure_connected()
        return self._models.execute_kw(
            ODOO_DB, self._uid, ODOO_PASSWORD,
            model, method, list(args), kwargs
        )

    def health_check(self) -> Dict[str, Any]:
        """Check Odoo connectivity and return version info."""
        if not self.enabled:
            return _DISABLED
        try:
            common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
            version = common.version()
            return {"enabled": True, "status": "ok", "version": version.get("server_version", "unknown")}
        except Exception as e:
            return {"enabled": True, "status": "error", "error": str(e)}

    # ── CRM: Contacts / Partners ──────────────────────────────────

    def get_contacts(self, limit: int = 50, customer_only: bool = True) -> Dict[str, Any]:
        """List CRM contacts (res.partner)."""
        if not self.enabled:
            return _DISABLED
        try:
            domain = [("is_company", "=", False)]
            if customer_only:
                domain.append(("customer_rank", ">", 0))
            ids = self._execute("res.partner", "search", domain, limit=limit)
            records = self._execute(
                "res.partner", "read", ids,
                fields=["name", "email", "phone", "city", "country_id", "parent_id", "customer_rank", "create_date"]
            )
            return {"contacts": records or [], "count": len(records or [])}
        except Exception as e:
            logger.error("Odoo get_contacts failed: %s", e)
            return {"error": str(e)}

    def search_contact(self, name: str) -> Dict[str, Any]:
        """Search contacts by name."""
        if not self.enabled:
            return _DISABLED
        try:
            domain = [("name", "ilike", name), ("is_company", "=", False)]
            ids = self._execute("res.partner", "search", domain, limit=20)
            records = self._execute(
                "res.partner", "read", ids,
                fields=["name", "email", "phone", "city", "parent_id", "customer_rank"]
            )
            return {"contacts": records or [], "count": len(records or [])}
        except Exception as e:
            logger.error("Odoo search_contact failed: %s", e)
            return {"error": str(e)}

    def create_contact(self, name: str, email: Optional[str] = None,
                       phone: Optional[str] = None, company_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new contact in Odoo."""
        if not self.enabled:
            return _DISABLED
        try:
            vals: Dict[str, Any] = {"name": name, "customer_rank": 1}
            if email:
                vals["email"] = email
            if phone:
                vals["phone"] = phone
            if company_name:
                # Find or create company
                company_ids = self._execute("res.partner", "search", [("name", "=", company_name), ("is_company", "=", True)], limit=1)
                if company_ids:
                    vals["parent_id"] = company_ids[0]
                else:
                    cid = self._execute("res.partner", "create", [{"name": company_name, "is_company": True}])
                    vals["parent_id"] = cid
            new_id = self._execute("res.partner", "create", [vals])
            return {"id": new_id, "name": name}
        except Exception as e:
            logger.error("Odoo create_contact failed: %s", e)
            return {"error": str(e)}

    # ── CRM: Companies ────────────────────────────────────────────

    def get_companies(self, limit: int = 50) -> Dict[str, Any]:
        """List companies / organizations."""
        if not self.enabled:
            return _DISABLED
        try:
            domain = [("is_company", "=", True)]
            ids = self._execute("res.partner", "search", domain, limit=limit)
            records = self._execute(
                "res.partner", "read", ids,
                fields=["name", "email", "phone", "city", "country_id", "website", "create_date"]
            )
            return {"companies": records or [], "count": len(records or [])}
        except Exception as e:
            logger.error("Odoo get_companies failed: %s", e)
            return {"error": str(e)}

    # ── CRM: Leads / Opportunities ────────────────────────────────

    def get_leads(self, limit: int = 50, stage: Optional[str] = None) -> Dict[str, Any]:
        """List CRM leads/opportunities (crm.lead)."""
        if not self.enabled:
            return _DISABLED
        try:
            domain: list = []
            if stage:
                domain.append(("stage_id.name", "ilike", stage))
            ids = self._execute("crm.lead", "search", domain, limit=limit)
            records = self._execute(
                "crm.lead", "read", ids,
                fields=["name", "expected_revenue", "probability", "stage_id",
                         "partner_id", "user_id", "create_date", "date_deadline", "type"]
            )
            return {"leads": records or [], "count": len(records or [])}
        except Exception as e:
            logger.error("Odoo get_leads failed: %s", e)
            return {"error": str(e)}

    def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get CRM pipeline summary grouped by stage."""
        if not self.enabled:
            return _DISABLED
        try:
            result = self._execute(
                "crm.lead", "read_group",
                [],
                fields=["stage_id", "expected_revenue"],
                groupby=["stage_id"],
            )
            stages = []
            for group in (result or []):
                stages.append({
                    "stage": group.get("stage_id", [None, "Unknown"])[1] if isinstance(group.get("stage_id"), (list, tuple)) else str(group.get("stage_id")),
                    "count": group.get("stage_id_count", 0),
                    "total_revenue": group.get("expected_revenue", 0),
                })
            return {"pipeline": stages, "total_leads": sum(s["count"] for s in stages)}
        except Exception as e:
            logger.error("Odoo pipeline summary failed: %s", e)
            return {"error": str(e)}

    # ── Invoicing ─────────────────────────────────────────────────

    def get_invoices(self, limit: int = 50, state: Optional[str] = None) -> Dict[str, Any]:
        """List customer invoices (account.move, move_type=out_invoice)."""
        if not self.enabled:
            return _DISABLED
        try:
            domain: list = [("move_type", "=", "out_invoice")]
            if state:
                domain.append(("state", "=", state))
            ids = self._execute("account.move", "search", domain, limit=limit)
            records = self._execute(
                "account.move", "read", ids,
                fields=["name", "partner_id", "amount_total", "amount_residual",
                         "state", "invoice_date", "invoice_date_due", "payment_state"]
            )
            return {"invoices": records or [], "count": len(records or [])}
        except Exception as e:
            logger.error("Odoo get_invoices failed: %s", e)
            return {"error": str(e)}

    def create_invoice(self, partner_id: int, lines: List[Dict[str, Any]],
                       invoice_date: Optional[str] = None) -> Dict[str, Any]:
        """Create a customer invoice in Odoo.

        Args:
            partner_id: Odoo partner (customer) ID.
            lines: List of dicts with keys: name, quantity, price_unit, and optional product_id, account_id.
            invoice_date: ISO date string (defaults to today).
        """
        if not self.enabled:
            return _DISABLED
        try:
            invoice_lines = []
            for line in lines:
                vals = {
                    "name": line.get("name", line.get("description", "Service")),
                    "quantity": line.get("quantity", 1),
                    "price_unit": line.get("price_unit", line.get("unit_price", 0)),
                }
                if line.get("product_id"):
                    vals["product_id"] = line["product_id"]
                if line.get("account_id"):
                    vals["account_id"] = line["account_id"]
                invoice_lines.append((0, 0, vals))

            invoice_vals: Dict[str, Any] = {
                "move_type": "out_invoice",
                "partner_id": partner_id,
                "invoice_line_ids": invoice_lines,
            }
            if invoice_date:
                invoice_vals["invoice_date"] = invoice_date

            new_id = self._execute("account.move", "create", [invoice_vals])
            return {"id": new_id, "status": "draft"}
        except Exception as e:
            logger.error("Odoo create_invoice failed: %s", e)
            return {"error": str(e)}

    def confirm_invoice(self, invoice_id: int) -> Dict[str, Any]:
        """Post/confirm a draft invoice."""
        if not self.enabled:
            return _DISABLED
        try:
            self._execute("account.move", "action_post", [invoice_id])
            return {"id": invoice_id, "status": "posted"}
        except Exception as e:
            logger.error("Odoo confirm_invoice failed: %s", e)
            return {"error": str(e)}

    # ── Payments ──────────────────────────────────────────────────

    def get_payments(self, limit: int = 50) -> Dict[str, Any]:
        """List customer payments."""
        if not self.enabled:
            return _DISABLED
        try:
            domain = [("partner_type", "=", "customer")]
            ids = self._execute("account.payment", "search", domain, limit=limit)
            records = self._execute(
                "account.payment", "read", ids,
                fields=["name", "amount", "payment_type", "partner_id",
                         "journal_id", "state", "date", "ref"]
            )
            return {"payments": records or [], "count": len(records or [])}
        except Exception as e:
            logger.error("Odoo get_payments failed: %s", e)
            return {"error": str(e)}

    def register_payment(self, amount: float, partner_id: int,
                         journal_id: int = 1, payment_method: str = "manual",
                         ref: Optional[str] = None) -> Dict[str, Any]:
        """Register a customer payment in Odoo."""
        if not self.enabled:
            return _DISABLED
        try:
            vals: Dict[str, Any] = {
                "payment_type": "inbound",
                "partner_type": "customer",
                "amount": amount,
                "partner_id": partner_id,
                "journal_id": journal_id,
            }
            if ref:
                vals["ref"] = ref
            new_id = self._execute("account.payment", "create", [vals])
            # Confirm the payment
            self._execute("account.payment", "action_post", [new_id])
            return {"id": new_id, "status": "posted", "amount": amount}
        except Exception as e:
            logger.error("Odoo register_payment failed: %s", e)
            return {"error": str(e)}

    # ── Accounting / Journal Entries ──────────────────────────────

    def get_journal_entries(self, date_from: Optional[str] = None,
                           date_to: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """Fetch journal entries (account.move.line)."""
        if not self.enabled:
            return _DISABLED
        try:
            domain: list = []
            if date_from:
                domain.append(("date", ">=", date_from))
            if date_to:
                domain.append(("date", "<=", date_to))
            ids = self._execute("account.move.line", "search", domain, limit=limit)
            records = self._execute(
                "account.move.line", "read", ids,
                fields=["name", "debit", "credit", "date", "account_id", "move_id", "partner_id"]
            )
            return {"entries": records or [], "count": len(records or [])}
        except Exception as e:
            logger.error("Odoo journal entries failed: %s", e)
            return {"error": str(e)}

    def get_account_balance(self) -> Dict[str, Any]:
        """Get account balances grouped by account type (trial balance)."""
        if not self.enabled:
            return _DISABLED
        try:
            result = self._execute(
                "account.move.line", "read_group",
                [],
                fields=["account_id", "debit", "credit"],
                groupby=["account_id"],
            )
            accounts = []
            for group in (result or []):
                acct = group.get("account_id")
                accounts.append({
                    "account": acct[1] if isinstance(acct, (list, tuple)) else str(acct),
                    "debit": group.get("debit", 0),
                    "credit": group.get("credit", 0),
                    "balance": group.get("debit", 0) - group.get("credit", 0),
                })
            return {"accounts": accounts}
        except Exception as e:
            logger.error("Odoo account balance failed: %s", e)
            return {"error": str(e)}

    # ── Products / Services ───────────────────────────────────────

    def get_products(self, limit: int = 50, product_type: Optional[str] = None) -> Dict[str, Any]:
        """List products/services (product.product)."""
        if not self.enabled:
            return _DISABLED
        try:
            domain: list = []
            if product_type:
                domain.append(("type", "=", product_type))
            ids = self._execute("product.product", "search", domain, limit=limit)
            records = self._execute(
                "product.product", "read", ids,
                fields=["name", "list_price", "type", "categ_id", "qty_available", "default_code"]
            )
            return {"products": records or [], "count": len(records or [])}
        except Exception as e:
            logger.error("Odoo get_products failed: %s", e)
            return {"error": str(e)}

    # ── Revenue Summary (aggregated from invoices) ────────────────

    def get_revenue_summary(self, date_from: Optional[str] = None,
                            date_to: Optional[str] = None) -> Dict[str, Any]:
        """Revenue summary from posted invoices in a date range."""
        if not self.enabled:
            return _DISABLED
        try:
            domain: list = [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
            if date_from:
                domain.append(("invoice_date", ">=", date_from))
            if date_to:
                domain.append(("invoice_date", "<=", date_to))
            result = self._execute(
                "account.move", "read_group",
                domain,
                fields=["amount_total", "invoice_date"],
                groupby=["invoice_date:day"],
            )
            daily = []
            total = 0.0
            for group in (result or []):
                amount = group.get("amount_total", 0)
                total += amount
                daily.append({
                    "date": group.get("invoice_date:day", "unknown"),
                    "revenue": amount,
                    "count": group.get("__count", 0),
                })
            return {"daily": daily, "total_revenue": total, "period": {"from": date_from, "to": date_to}}
        except Exception as e:
            logger.error("Odoo revenue summary failed: %s", e)
            return {"error": str(e)}


# Singleton
odoo_client = OdooClient()
