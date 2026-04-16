"""Odoo Finance Client — optional integration with Odoo ERP.

When ODOO_ENABLED=true, routes finance queries through Odoo's XML-RPC API.
When ODOO_ENABLED=false (default), falls back to local DailyAnalytics + Payment tables.

This is a soft integration: the platform operates fully without Odoo.
Odoo adds double-entry accounting, purchase orders, and external invoicing.
"""

import os
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ODOO_ENABLED = os.getenv("ODOO_ENABLED", "false").lower() in ("true", "1", "yes")
ODOO_URL = os.getenv("ODOO_URL", "http://odoo:8069")
ODOO_DB = os.getenv("ODOO_DB", "zeroqwait")
ODOO_USER = os.getenv("ODOO_USER", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "")


class OdooFinanceClient:
    """Thin wrapper around Odoo XML-RPC finance operations.

    All methods return plain dicts. When Odoo is disabled, each method
    returns a fallback dict pointing callers to local data instead.
    """

    def __init__(self):
        self.enabled = ODOO_ENABLED
        self._uid = None
        if self.enabled:
            try:
                self._connect()
            except Exception as e:
                logger.warning("Odoo connection failed at init, will retry on demand: %s", e)

    def _connect(self):
        """Authenticate with Odoo and cache uid."""
        import xmlrpc.client  # stdlib — no extra dependency
        common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
        self._uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        if not self._uid:
            raise ConnectionError("Odoo authentication failed")
        self._models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
        logger.info("Connected to Odoo (uid=%s)", self._uid)

    def _execute(self, model: str, method: str, *args, **kwargs):
        if not self.enabled:
            return None
        if self._uid is None:
            self._connect()
        return self._models.execute_kw(ODOO_DB, self._uid, ODOO_PASSWORD, model, method, list(args), kwargs)

    # ── Finance Queries ──────────────────────────────────────────

    def get_invoices(self, shop_id: int, limit: int = 50) -> Dict[str, Any]:
        """Fetch invoices from Odoo. Falls back to local when disabled."""
        if not self.enabled:
            return {"source": "local", "message": "Odoo disabled — use local invoice data"}
        try:
            domain = [("x_shop_id", "=", shop_id), ("move_type", "=", "out_invoice")]
            ids = self._execute("account.move", "search", domain, limit=limit)
            records = self._execute("account.move", "read", ids, fields=["name", "amount_total", "state", "invoice_date"])
            return {"source": "odoo", "invoices": records or []}
        except Exception as e:
            logger.error("Odoo get_invoices failed: %s", e)
            return {"source": "local", "error": str(e), "message": "Odoo error — falling back to local data"}

    def get_journal_entries(self, shop_id: int, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
        """Fetch journal entries (double-entry accounting) from Odoo."""
        if not self.enabled:
            return {"source": "local", "message": "Odoo disabled — use local analytics"}
        try:
            domain = [("x_shop_id", "=", shop_id)]
            if date_from:
                domain.append(("date", ">=", date_from))
            if date_to:
                domain.append(("date", "<=", date_to))
            ids = self._execute("account.move.line", "search", domain, limit=200)
            records = self._execute("account.move.line", "read", ids, fields=["name", "debit", "credit", "date", "account_id"])
            return {"source": "odoo", "entries": records or []}
        except Exception as e:
            logger.error("Odoo journal entries failed: %s", e)
            return {"source": "local", "error": str(e)}

    def get_profit_loss(self, shop_id: int, date_from: str, date_to: str) -> Dict[str, Any]:
        """Fetch P&L report stub from Odoo."""
        if not self.enabled:
            return {"source": "local", "message": "Odoo disabled — use daily_analytics for revenue reports"}
        try:
            # Odoo P&L is typically accessed via report actions, not simple API.
            # This placeholder shows the pattern; real impl uses Odoo's financial reports API.
            return {"source": "odoo", "message": "P&L report — requires Odoo report engine"}
        except Exception as e:
            return {"source": "local", "error": str(e)}

    def sync_payment_to_odoo(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Push a local payment record to Odoo as a customer payment."""
        if not self.enabled:
            return {"synced": False, "message": "Odoo disabled — payment stored locally only"}
        try:
            vals = {
                "partner_type": "customer",
                "payment_type": "inbound",
                "amount": payment_data.get("amount", 0),
                "journal_id": 1,  # Default bank journal — configure per shop
                "x_shop_id": payment_data.get("shop_id"),
            }
            new_id = self._execute("account.payment", "create", [vals])
            return {"synced": True, "odoo_payment_id": new_id}
        except Exception as e:
            logger.error("Odoo payment sync failed: %s", e)
            return {"synced": False, "error": str(e)}


# Singleton
odoo_client = OdooFinanceClient()
