"""Odoo ERP Client — full integration with Odoo 17 via XML-RPC.

Covers: CRM, Invoicing, Payments, Accounting, Products, and basic HR.
When ODOO_ENABLED=true, all queries route through Odoo's XML-RPC API.
When ODOO_ENABLED=false, returns disabled-status dicts so callers can
fall back to local data gracefully.

Multi-tenancy: Every shop maps to a unique ``res.company`` in Odoo.
All record creation and searches accept an optional ``company_id``
parameter so that data is strictly isolated per shop.
"""

import os
import logging
from typing import Any, Dict, List, Optional
import xmlrpc.client

logger = logging.getLogger(__name__)

ODOO_ENABLED = os.getenv("ODOO_ENABLED", "false").lower() in ("1", "true", "yes")
ODOO_URL = os.getenv("ODOO_URL", "http://odoo:8069")
ODOO_DB = os.getenv("ODOO_DB", "odoo")
ODOO_USER = os.getenv("ODOO_USER", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")

_DISABLED = {"enabled": False, "message": "Odoo integration is disabled"}


def _add_company_filter(domain: list, company_id: Optional[int]) -> list:
    """Append company_id filter to an Odoo domain if provided."""
    if company_id is not None:
        return domain + [("company_id", "=", company_id)]
    return domain


_M2O_FIELDS = {"country_id", "parent_id", "partner_id", "stage_id",
               "user_id", "journal_id", "account_id", "categ_id",
               "move_id", "company_id", "uom_id", "uom_po_id"}


def _resolve_m2o(records: list) -> list:
    """Convert Many2one [id, name] tuples to readable 'name' strings."""
    if not records:
        return records
    out = []
    for rec in records:
        cleaned = {}
        for key, val in rec.items():
            if key in _M2O_FIELDS and isinstance(val, (list, tuple)) and len(val) == 2:
                cleaned[key] = val[1]  # keep display name
            else:
                cleaned[key] = val
        out.append(cleaned)
    return out


class OdooClient:
    """Full Odoo 17 XML-RPC client for ERP operations with multi-company isolation."""

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
        self._models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)
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

    # ── Company Management (Multi-Tenancy) ────────────────────────

    def create_company(self, name: str, phone: Optional[str] = None,
                       email: Optional[str] = None,
                       street: Optional[str] = None,
                       city: Optional[str] = None) -> Dict[str, Any]:
        """Create a new res.company in Odoo for tenant isolation.

        Each ZeroQwait shop gets its own Odoo company so that CRM contacts,
        invoices, payments, and accounting entries are fully isolated.
        If a company with the same name already exists, returns the existing one.
        """
        if not self.enabled:
            return _DISABLED
        try:
            # Check if company already exists (handles duplicate shop names)
            existing = self._execute("res.company", "search", [("name", "=", name)], limit=1)
            if existing:
                logger.info("Odoo company '%s' already exists (id=%s), reusing", name, existing[0])
                return {"id": existing[0], "name": name, "reused": True}
            vals: Dict[str, Any] = {"name": name}
            if phone:
                vals["phone"] = phone
            if email:
                vals["email"] = email
            if street:
                vals["street"] = street
            if city:
                vals["city"] = city
            new_id = self._execute("res.company", "create", vals)
            logger.info("Created Odoo company id=%s for shop '%s'", new_id, name)
            return {"id": new_id, "name": name}
        except Exception as e:
            logger.error("Odoo create_company failed: %s", e)
            return {"error": str(e)}

    def get_odoo_company(self, company_id: int) -> Dict[str, Any]:
        """Get an Odoo company by ID."""
        if not self.enabled:
            return _DISABLED
        try:
            records = self._execute(
                "res.company", "read", [company_id],
                fields=["name", "phone", "email", "street", "city"],
            )
            if records:
                return {"company": records[0]}
            return {"error": f"Company {company_id} not found"}
        except Exception as e:
            logger.error("Odoo get_odoo_company failed: %s", e)
            return {"error": str(e)}

    # ── CRM: Contacts / Partners ──────────────────────────────────

    def get_contacts(self, limit: int = 50, customer_only: bool = True,
                     company_id: Optional[int] = None) -> Dict[str, Any]:
        """List CRM contacts (res.partner) scoped to company_id."""
        if not self.enabled:
            return _DISABLED
        try:
            domain = [("is_company", "=", False)]
            if customer_only:
                domain.append(("customer_rank", ">", 0))
            domain = _add_company_filter(domain, company_id)
            ids = self._execute("res.partner", "search", domain, limit=limit)
            records = self._execute(
                "res.partner", "read", ids,
                fields=["name", "email", "phone", "city", "country_id", "parent_id", "customer_rank", "create_date"]
            )
            records = _resolve_m2o(records or [])
            return {"contacts": records, "count": len(records)}
        except Exception as e:
            logger.error("Odoo get_contacts failed: %s", e)
            return {"error": str(e)}

    def search_contact(self, name: str,
                       company_id: Optional[int] = None) -> Dict[str, Any]:
        """Search contacts by name, scoped to company_id."""
        if not self.enabled:
            return _DISABLED
        try:
            domain = [("name", "ilike", name), ("is_company", "=", False)]
            domain = _add_company_filter(domain, company_id)
            ids = self._execute("res.partner", "search", domain, limit=20)
            records = self._execute(
                "res.partner", "read", ids,
                fields=["name", "email", "phone", "city", "parent_id", "customer_rank"]
            )
            records = _resolve_m2o(records or [])
            return {"contacts": records, "count": len(records)}
        except Exception as e:
            logger.error("Odoo search_contact failed: %s", e)
            return {"error": str(e)}

    def create_contact(self, name: str, email: Optional[str] = None,
                       phone: Optional[str] = None, company_name: Optional[str] = None,
                       company_id: Optional[int] = None) -> Dict[str, Any]:
        """Create a new contact in Odoo, assigned to company_id."""
        if not self.enabled:
            return _DISABLED
        try:
            vals: Dict[str, Any] = {"name": name, "customer_rank": 1}
            if company_id is not None:
                vals["company_id"] = company_id
            if email:
                vals["email"] = email
            if phone:
                vals["phone"] = phone
            if company_name:
                # Find or create partner-company (CRM organization) within the same Odoo company
                org_domain = [("name", "=", company_name), ("is_company", "=", True)]
                org_domain = _add_company_filter(org_domain, company_id)
                org_ids = self._execute("res.partner", "search", org_domain, limit=1)
                if org_ids:
                    vals["parent_id"] = org_ids[0]
                else:
                    org_vals: Dict[str, Any] = {"name": company_name, "is_company": True}
                    if company_id is not None:
                        org_vals["company_id"] = company_id
                    cid = self._execute("res.partner", "create", org_vals)
                    vals["parent_id"] = cid
            new_id = self._execute("res.partner", "create", vals)
            return {"id": new_id, "name": name}
        except Exception as e:
            logger.error("Odoo create_contact failed: %s", e)
            return {"error": str(e)}

    # ── CRM: Companies (Partner Organizations) ────────────────────

    def get_companies(self, limit: int = 50,
                      company_id: Optional[int] = None) -> Dict[str, Any]:
        """List partner-companies / organizations scoped to company_id."""
        if not self.enabled:
            return _DISABLED
        try:
            domain = [("is_company", "=", True)]
            domain = _add_company_filter(domain, company_id)
            ids = self._execute("res.partner", "search", domain, limit=limit)
            records = self._execute(
                "res.partner", "read", ids,
                fields=["name", "email", "phone", "city", "country_id", "website", "create_date"]
            )
            records = _resolve_m2o(records or [])
            return {"companies": records, "count": len(records)}
        except Exception as e:
            logger.error("Odoo get_companies failed: %s", e)
            return {"error": str(e)}

    # ── CRM: Leads / Opportunities ────────────────────────────────

    def get_leads(self, limit: int = 50, stage: Optional[str] = None,
                  company_id: Optional[int] = None) -> Dict[str, Any]:
        """List CRM leads/opportunities scoped to company_id."""
        if not self.enabled:
            return _DISABLED
        try:
            domain: list = []
            if stage:
                domain.append(("stage_id.name", "ilike", stage))
            domain = _add_company_filter(domain, company_id)
            ids = self._execute("crm.lead", "search", domain, limit=limit)
            records = self._execute(
                "crm.lead", "read", ids,
                fields=["name", "expected_revenue", "probability", "stage_id",
                         "partner_id", "user_id", "create_date", "date_deadline", "type"]
            )
            records = _resolve_m2o(records or [])
            return {"leads": records, "count": len(records)}
        except Exception as e:
            logger.error("Odoo get_leads failed: %s", e)
            return {"error": str(e)}

    def get_pipeline_summary(self, company_id: Optional[int] = None) -> Dict[str, Any]:
        """Get CRM pipeline summary grouped by stage, scoped to company_id."""
        if not self.enabled:
            return _DISABLED
        try:
            domain: list = _add_company_filter([], company_id)
            result = self._execute(
                "crm.lead", "read_group",
                domain,
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

    def get_invoices(self, limit: int = 50, state: Optional[str] = None,
                     company_id: Optional[int] = None) -> Dict[str, Any]:
        """List customer invoices scoped to company_id."""
        if not self.enabled:
            return _DISABLED
        try:
            domain: list = [("move_type", "=", "out_invoice")]
            if state:
                domain.append(("state", "=", state))
            domain = _add_company_filter(domain, company_id)
            ids = self._execute("account.move", "search", domain, limit=limit)
            records = self._execute(
                "account.move", "read", ids,
                fields=["name", "partner_id", "amount_total", "amount_residual",
                         "state", "invoice_date", "invoice_date_due", "payment_state"]
            )
            records = _resolve_m2o(records or [])
            return {"invoices": records, "count": len(records)}
        except Exception as e:
            logger.error("Odoo get_invoices failed: %s", e)
            return {"error": str(e)}

    def create_invoice(self, partner_id: int, lines: List[Dict[str, Any]],
                       invoice_date: Optional[str] = None,
                       company_id: Optional[int] = None) -> Dict[str, Any]:
        """Create a customer invoice assigned to company_id."""
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
            if company_id is not None:
                invoice_vals["company_id"] = company_id
            if invoice_date:
                invoice_vals["invoice_date"] = invoice_date

            new_id = self._execute("account.move", "create", invoice_vals)
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

    def get_payments(self, limit: int = 50,
                     company_id: Optional[int] = None) -> Dict[str, Any]:
        """List customer payments scoped to company_id."""
        if not self.enabled:
            return _DISABLED
        try:
            domain = [("partner_type", "=", "customer")]
            domain = _add_company_filter(domain, company_id)
            ids = self._execute("account.payment", "search", domain, limit=limit)
            records = self._execute(
                "account.payment", "read", ids,
                fields=["name", "amount", "payment_type", "partner_id",
                         "journal_id", "state", "date", "ref"]
            )
            records = _resolve_m2o(records or [])
            return {"payments": records, "count": len(records)}
        except Exception as e:
            logger.error("Odoo get_payments failed: %s", e)
            return {"error": str(e)}

    def register_payment(self, amount: float, partner_id: int,
                         journal_id: int = 0, payment_method: str = "manual",
                         ref: Optional[str] = None,
                         company_id: Optional[int] = None) -> Dict[str, Any]:
        """Register a customer payment assigned to company_id."""
        if not self.enabled:
            return _DISABLED
        try:
            # Auto-resolve journal for the target company if none specified
            if not journal_id and company_id is not None:
                domain = [("type", "=", "bank"), ("company_id", "=", company_id)]
                j_ids = self._execute("account.journal", "search", domain, limit=1)
                if not j_ids:
                    # Fall back to any cash/bank journal for this company
                    domain = [("type", "in", ["bank", "cash"]), ("company_id", "=", company_id)]
                    j_ids = self._execute("account.journal", "search", domain, limit=1)
                if j_ids:
                    journal_id = j_ids[0]
                else:
                    return {"error": f"No bank/cash journal found for company_id={company_id}"}
            elif not journal_id:
                journal_id = 1  # Default fallback when no company specified

            vals: Dict[str, Any] = {
                "payment_type": "inbound",
                "partner_type": "customer",
                "amount": amount,
                "partner_id": partner_id,
                "journal_id": journal_id,
            }
            if company_id is not None:
                vals["company_id"] = company_id
            if ref:
                vals["ref"] = ref
            new_id = self._execute("account.payment", "create", vals)
            # Try to confirm the payment; skip if chart of accounts is incomplete
            try:
                self._execute("account.payment", "action_post", [new_id])
                return {"id": new_id, "status": "posted", "amount": amount}
            except Exception as post_err:
                logger.warning("Odoo payment created but confirm failed (chart of accounts incomplete?): %s", post_err)
                return {"id": new_id, "status": "draft", "amount": amount}
        except Exception as e:
            logger.error("Odoo register_payment failed: %s", e)
            return {"error": str(e)}

    # ── Accounting / Journal Entries ──────────────────────────────

    def get_journal_entries(self, date_from: Optional[str] = None,
                           date_to: Optional[str] = None, limit: int = 100,
                           company_id: Optional[int] = None) -> Dict[str, Any]:
        """Fetch journal entries scoped to company_id."""
        if not self.enabled:
            return _DISABLED
        try:
            domain: list = []
            if date_from:
                domain.append(("date", ">=", date_from))
            if date_to:
                domain.append(("date", "<=", date_to))
            domain = _add_company_filter(domain, company_id)
            ids = self._execute("account.move.line", "search", domain, limit=limit)
            records = self._execute(
                "account.move.line", "read", ids,
                fields=["name", "debit", "credit", "date", "account_id", "move_id", "partner_id"]
            )
            records = _resolve_m2o(records or [])
            return {"entries": records, "count": len(records)}
        except Exception as e:
            logger.error("Odoo journal entries failed: %s", e)
            return {"error": str(e)}

    def get_account_balance(self, company_id: Optional[int] = None) -> Dict[str, Any]:
        """Get account balances grouped by account type, scoped to company_id."""
        if not self.enabled:
            return _DISABLED
        try:
            domain: list = _add_company_filter([], company_id)
            result = self._execute(
                "account.move.line", "read_group",
                domain,
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

    def get_products(self, limit: int = 50, product_type: Optional[str] = None,
                     company_id: Optional[int] = None) -> Dict[str, Any]:
        """List products/services scoped to company_id (or shared if company_id is None)."""
        if not self.enabled:
            return _DISABLED
        try:
            domain: list = []
            if product_type:
                domain.append(("type", "=", product_type))
            domain = _add_company_filter(domain, company_id)
            ids = self._execute("product.product", "search", domain, limit=limit)
            records = self._execute(
                "product.product", "read", ids,
                fields=["name", "list_price", "type", "categ_id", "qty_available", "default_code"]
            )
            records = _resolve_m2o(records or [])
            return {"products": records, "count": len(records)}
        except Exception as e:
            logger.error("Odoo get_products failed: %s", e)
            return {"error": str(e)}

    def create_product(self, name: str, list_price: float,
                       product_type: str = "service",
                       company_id: Optional[int] = None,
                       description: Optional[str] = None) -> Dict[str, Any]:
        """Create a product/service in Odoo, scoped to company_id."""
        if not self.enabled:
            return _DISABLED
        try:
            vals: Dict[str, Any] = {
                "name": name,
                "list_price": list_price,
                "type": product_type,
                "sale_ok": True,
            }
            if company_id is not None:
                vals["company_id"] = company_id
            if description:
                vals["description_sale"] = description
            product_id = self._execute("product.product", "create", vals)
            return {"product_id": product_id, "name": name, "list_price": list_price}
        except Exception as e:
            logger.error("Odoo create_product failed: %s", e)
            return {"error": str(e)}

    def update_product(self, product_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a product/service in Odoo."""
        if not self.enabled:
            return _DISABLED
        try:
            self._execute("product.product", "write", [product_id], updates)
            return {"product_id": product_id, "updated": True}
        except Exception as e:
            logger.error("Odoo update_product failed: %s", e)
            return {"error": str(e)}

    # ── Stock / Inventory ─────────────────────────────────────────

    def get_low_stock_items(self, company_id: Optional[int] = None, threshold: float = 0) -> Dict[str, Any]:
        """Return storable products whose on-hand quantity is at or below *threshold*."""
        if not self.enabled:
            return _DISABLED
        try:
            domain: list = [("type", "=", "product"), ("qty_on_hand", "<=", threshold)]
            domain = _add_company_filter(domain, company_id)
            items = self._execute(
                "product.product", "search_read", domain,
                ["id", "name", "qty_on_hand", "uom_id", "default_code", "barcode"],
                limit=200,
            )
            return {"items": _resolve_m2o(items), "count": len(items)}
        except Exception as e:
            logger.error("Odoo get_low_stock_items failed: %s", e)
            return {"error": str(e)}

    def receive_stock(self, product_id: int, qty: float,
                      company_id: Optional[int] = None, notes: str = "") -> Dict[str, Any]:
        """Increase on-hand stock for *product_id* by *qty* (creates/updates stock.quant)."""
        if not self.enabled:
            return _DISABLED
        try:
            domain = _add_company_filter([("product_id", "=", product_id)], company_id)
            quants = self._execute("stock.quant", "search_read", domain, ["id", "quantity"], limit=1)
            if quants:
                quant_id = quants[0]["id"]
                new_qty = quants[0]["quantity"] + qty
                self._models.execute_kw(
                    self._db, self._uid, self._password,
                    "stock.quant", "write", [[quant_id], {"quantity": new_qty}],
                )
            else:
                vals: Dict[str, Any] = {"product_id": product_id, "quantity": qty, "location_id": 8}
                if company_id:
                    vals["company_id"] = company_id
                quant_id = self._models.execute_kw(
                    self._db, self._uid, self._password,
                    "stock.quant", "create", [vals],
                )
            return {"quant_id": quant_id, "qty_added": qty, "notes": notes}
        except Exception as e:
            logger.error("Odoo receive_stock failed: %s", e)
            return {"error": str(e)}

    def adjust_stock(self, product_id: int, qty_delta: float,
                     reason: str = "", company_id: Optional[int] = None) -> Dict[str, Any]:
        """Apply a signed *qty_delta* adjustment to *product_id*'s on-hand stock."""
        if not self.enabled:
            return _DISABLED
        try:
            domain = _add_company_filter([("product_id", "=", product_id)], company_id)
            quants = self._execute("stock.quant", "search_read", domain, ["id", "quantity"], limit=1)
            quant_id: Optional[int] = None
            if quants:
                quant_id = quants[0]["id"]
                new_qty = quants[0]["quantity"] + qty_delta
                self._models.execute_kw(
                    self._db, self._uid, self._password,
                    "stock.quant", "write", [[quant_id], {"quantity": new_qty}],
                )
            return {"quant_id": quant_id, "qty_delta": qty_delta, "reason": reason}
        except Exception as e:
            logger.error("Odoo adjust_stock failed: %s", e)
            return {"error": str(e)}

    def get_product_by_barcode(self, barcode: str, company_id: Optional[int] = None) -> Dict[str, Any]:
        """Look up a product by its barcode field."""
        if not self.enabled:
            return _DISABLED
        try:
            domain: list = [("barcode", "=", barcode)]
            domain = _add_company_filter(domain, company_id)
            items = self._execute(
                "product.product", "search_read", domain,
                ["id", "name", "qty_on_hand", "list_price", "default_code", "barcode"],
                limit=1,
            )
            if not items:
                return {"error": "not_found", "barcode": barcode}
            return {"product": _resolve_m2o(items[0], [])}
        except Exception as e:
            logger.error("Odoo get_product_by_barcode failed: %s", e)
            return {"error": str(e)}

    # ── Revenue Summary (aggregated from invoices) ────────────────

    def get_revenue_summary(self, date_from: Optional[str] = None,
                            date_to: Optional[str] = None,
                            company_id: Optional[int] = None) -> Dict[str, Any]:
        """Revenue summary from posted invoices, scoped to company_id."""
        if not self.enabled:
            return _DISABLED
        try:
            domain: list = [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
            if date_from:
                domain.append(("invoice_date", ">=", date_from))
            if date_to:
                domain.append(("invoice_date", "<=", date_to))
            domain = _add_company_filter(domain, company_id)
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

    # ── CRM: Lead/Opportunity Management ──────────────────────────

    def create_lead(self, name: str, partner_id: Optional[int] = None,
                    expected_revenue: float = 0.0,
                    description: Optional[str] = None,
                    lead_type: str = "opportunity",
                    company_id: Optional[int] = None) -> Dict[str, Any]:
        """Create a CRM lead or opportunity assigned to company_id."""
        if not self.enabled:
            return _DISABLED
        try:
            vals: Dict[str, Any] = {
                "name": name,
                "type": lead_type,
                "expected_revenue": expected_revenue,
            }
            if partner_id:
                vals["partner_id"] = partner_id
            if description:
                vals["description"] = description
            if company_id is not None:
                vals["company_id"] = company_id
            new_id = self._execute("crm.lead", "create", vals)
            return {"id": new_id, "name": name, "type": lead_type}
        except Exception as e:
            logger.error("Odoo create_lead failed: %s", e)
            return {"error": str(e)}

    def update_lead_stage(self, lead_id: int,
                          stage_name: str) -> Dict[str, Any]:
        """Move a CRM lead to a different stage by stage name."""
        if not self.enabled:
            return _DISABLED
        try:
            stage_ids = self._execute(
                "crm.stage", "search",
                [("name", "ilike", stage_name)], limit=1,
            )
            if not stage_ids:
                return {"error": f"Stage '{stage_name}' not found"}
            self._execute("crm.lead", "write", [lead_id], {"stage_id": stage_ids[0]})
            return {"id": lead_id, "new_stage": stage_name, "stage_id": stage_ids[0]}
        except Exception as e:
            logger.error("Odoo update_lead_stage failed: %s", e)
            return {"error": str(e)}

    def update_contact(self, contact_id: int,
                       name: Optional[str] = None,
                       email: Optional[str] = None,
                       phone: Optional[str] = None,
                       city: Optional[str] = None) -> Dict[str, Any]:
        """Update an existing contact's fields."""
        if not self.enabled:
            return _DISABLED
        try:
            vals: Dict[str, Any] = {}
            if name:
                vals["name"] = name
            if email:
                vals["email"] = email
            if phone:
                vals["phone"] = phone
            if city:
                vals["city"] = city
            if not vals:
                return {"error": "No fields to update"}
            self._execute("res.partner", "write", [contact_id], vals)
            return {"id": contact_id, "updated_fields": list(vals.keys())}
        except Exception as e:
            logger.error("Odoo update_contact failed: %s", e)
            return {"error": str(e)}

    def add_note_to_lead(self, lead_id: int, body: str) -> Dict[str, Any]:
        """Add a log note to a CRM lead via message_post."""
        if not self.enabled:
            return _DISABLED
        try:
            msg_id = self._execute(
                "crm.lead", "message_post",
                [lead_id],
                body=body,
                message_type="comment",
            )
            return {"message_id": msg_id, "lead_id": lead_id}
        except Exception as e:
            logger.error("Odoo add_note_to_lead failed: %s", e)
            return {"error": str(e)}

    def get_lead_stages(self, company_id: Optional[int] = None) -> Dict[str, Any]:
        """List available CRM pipeline stages."""
        if not self.enabled:
            return _DISABLED
        try:
            ids = self._execute("crm.stage", "search", [], limit=50)
            records = self._execute(
                "crm.stage", "read", ids,
                fields=["name", "sequence", "is_won"]
            )
            return {"stages": records or []}
        except Exception as e:
            logger.error("Odoo get_lead_stages failed: %s", e)
            return {"error": str(e)}


# Singleton
odoo_client = OdooClient()
