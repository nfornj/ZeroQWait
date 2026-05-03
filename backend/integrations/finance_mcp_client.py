import logging
import os
from typing import Any, Dict, Optional

import httpx


logger = logging.getLogger(__name__)

FINANCE_MCP_URL = os.getenv("FINANCE_MCP_URL", "http://127.0.0.1:8891")


class FinanceMCPClient:
    """Synchronous client for the finance MCP REST surface."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 10.0):
        self.base_url = (base_url or FINANCE_MCP_URL).rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                response = client.post(path, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Finance MCP returned %s for %s: %s", exc.response.status_code, path, exc.response.text)
            return {"error": f"Finance MCP returned {exc.response.status_code} for {path}"}
        except httpx.HTTPError as exc:
            logger.error("Finance MCP request failed for %s: %s", path, exc)
            return {"error": f"Finance MCP request failed for {path}: {exc}"}

        try:
            data = response.json()
        except ValueError:
            logger.error("Finance MCP returned invalid JSON for %s", path)
            return {"error": f"Finance MCP returned invalid JSON for {path}"}

        if isinstance(data, dict):
            return data
        return {"result": data}

    def daily_revenue(self, shop_id: int, date: Optional[str] = None) -> Dict[str, Any]:
        return self._post("/revenue/daily", {"shop_id": shop_id, "date": date})

    def weekly_summary(self, shop_id: int, week_start: Optional[str] = None) -> Dict[str, Any]:
        return self._post("/revenue/weekly", {"shop_id": shop_id, "week_start": week_start})

    def trend_summary(self, shop_id: int, query: str) -> Dict[str, Any]:
        return self._post("/revenue/trend", {"shop_id": shop_id, "query": query})

    def top_services(self, shop_id: int, limit: int = 5) -> Dict[str, Any]:
        return self._post("/services/top", {"shop_id": shop_id, "limit": limit})

    def customer_metrics(self, shop_id: int, query: Optional[str] = None) -> Dict[str, Any]:
        return self._post("/customers/metrics", {"shop_id": shop_id, "query": query})

    def export_report(self, shop_id: int, format: str = "csv") -> Dict[str, Any]:
        return self._post("/reports/export", {"shop_id": shop_id, "format": format})

    def create_invoice(
        self,
        shop_id: int,
        service_name: str,
        unit_price: float,
        quantity: int = 1,
        customer_id: Optional[int] = None,
        tax_rate: float = 0.0,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._post(
            "/invoices/create",
            {
                "shop_id": shop_id,
                "service_name": service_name,
                "unit_price": unit_price,
                "quantity": quantity,
                "customer_id": customer_id,
                "tax_rate": tax_rate,
                "notes": notes,
            },
        )

    def record_payment(
        self,
        shop_id: int,
        amount: float,
        method: str = "cash",
        invoice_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._post(
            "/payments/record",
            {
                "shop_id": shop_id,
                "amount": amount,
                "method": method,
                "invoice_id": invoice_id,
                "notes": notes,
            },
        )

    def process_refund(
        self,
        shop_id: int,
        payment_id: int,
        refund_amount: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._post(
            "/payments/refund",
            {
                "shop_id": shop_id,
                "payment_id": payment_id,
                "refund_amount": refund_amount,
                "reason": reason,
            },
        )

    def list_invoices(self, shop_id: int, status: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        return self._post("/invoices/list", {"shop_id": shop_id, "status": status, "limit": limit})

    def get_pos_summary(self, shop_id: int, date: Optional[str] = None) -> Dict[str, Any]:
        return self._post("/pos/summary", {"shop_id": shop_id, "date": date})

    def answer_finance_question(
        self,
        shop_id: int,
        question: str,
        operation: Optional[str] = None,
        mode: str = "enabled",
    ) -> Dict[str, Any]:
        return self._post(
            "/query/answer",
            {
                "shop_id": shop_id,
                "question": question,
                "operation": operation,
                "mode": mode,
            },
        )

    def get_inactive_clients(self, shop_id: int, days_threshold: int = 45) -> Dict[str, Any]:
        return self._post("/clients/inactive", {"shop_id": shop_id, "days_threshold": days_threshold})

    def get_top_clients(self, shop_id: int, limit: int = 10) -> Dict[str, Any]:
        return self._post("/clients/top", {"shop_id": shop_id, "limit": limit})

    def get_visit_frequency_summary(self, shop_id: int) -> Dict[str, Any]:
        return self._post("/clients/visit-frequency", {"shop_id": shop_id})

    def get_client_profile(self, shop_id: int, client_id: int) -> Dict[str, Any]:
        return self._post("/clients/profile", {"shop_id": shop_id, "client_id": client_id})

    def search_clients(self, shop_id: int, name: str) -> Dict[str, Any]:
        return self._post("/clients/search", {"shop_id": shop_id, "name": name})
