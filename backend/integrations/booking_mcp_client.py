import logging
import os
from typing import Any, Dict, Optional

import httpx


logger = logging.getLogger(__name__)

BOOKING_MCP_URL = os.getenv("BOOKING_MCP_URL", "http://127.0.0.1:8890")


class BookingMCPClient:
    """Synchronous client for the booking MCP REST surface."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 10.0):
        self.base_url = (base_url or BOOKING_MCP_URL).rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                response = client.post(path, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Booking MCP returned %s for %s: %s", exc.response.status_code, path, exc.response.text)
            return {"error": f"Booking MCP returned {exc.response.status_code} for {path}"}
        except httpx.HTTPError as exc:
            logger.error("Booking MCP request failed for %s: %s", path, exc)
            return {"error": f"Booking MCP request failed for {path}: {exc}"}

        try:
            data = response.json()
        except ValueError:
            logger.error("Booking MCP returned invalid JSON for %s", path)
            return {"error": f"Booking MCP returned invalid JSON for {path}"}

        if isinstance(data, dict):
            return data
        return {"result": data}

    def list_queue(self, shop_id: int) -> Dict[str, Any]:
        return self._post("/queue/list", {"shop_id": shop_id})

    def join_queue(self, shop_id: int, customer_name: str, phone: Optional[str] = None) -> Dict[str, Any]:
        return self._post(
            "/queue/join",
            {"shop_id": shop_id, "customer_name": customer_name, "phone": phone},
        )

    def call_next(self, shop_id: int, employee_id: Optional[int] = None) -> Dict[str, Any]:
        return self._post("/queue/call-next", {"shop_id": shop_id, "employee_id": employee_id})

    def get_wait_time(self, shop_id: int, queue_item_id: Optional[int] = None) -> Dict[str, Any]:
        return self._post(
            "/queue/wait-time",
            {"shop_id": shop_id, "queue_item_id": queue_item_id},
        )

    def close_queue(self, shop_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
        return self._post("/queue/close", {"shop_id": shop_id, "reason": reason})

    def search_services(self, shop_id: int, query: Optional[str] = None) -> Dict[str, Any]:
        return self._post("/services/search", {"shop_id": shop_id, "query": query})

    def create_service(
        self,
        shop_id: int,
        name: str,
        cost: float,
        duration_minutes: int = 30,
        description: Optional[str] = None,
        currency: str = "USD",
    ) -> Dict[str, Any]:
        return self._post(
            "/services/create",
            {
                "shop_id": shop_id,
                "name": name,
                "cost": cost,
                "duration_minutes": duration_minutes,
                "description": description,
                "currency": currency,
            },
        )

    def update_service(
        self,
        shop_id: int,
        service_id: int,
        *,
        name: Optional[str] = None,
        cost: Optional[float] = None,
        duration_minutes: Optional[int] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        return self._post(
            "/services/update",
            {
                "shop_id": shop_id,
                "service_id": service_id,
                "name": name,
                "cost": cost,
                "duration_minutes": duration_minutes,
                "description": description,
                "is_active": is_active,
            },
        )

    def delete_service(self, shop_id: int, service_id: int) -> Dict[str, Any]:
        return self._post("/services/delete", {"shop_id": shop_id, "service_id": service_id})

    def book_appointment(
        self,
        shop_id: int,
        service_id: int,
        scheduled_start: str,
        customer_name: str,
        customer_phone: Optional[str] = None,
        customer_email: Optional[str] = None,
        employee_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._post(
            "/appointments/book",
            {
                "shop_id": shop_id,
                "service_id": service_id,
                "scheduled_start": scheduled_start,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "customer_email": customer_email,
                "employee_id": employee_id,
                "notes": notes,
            },
        )

    def list_appointments(
        self,
        shop_id: int,
        date: Optional[str] = None,
        status: Optional[str] = None,
        employee_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._post(
            "/appointments/list",
            {
                "shop_id": shop_id,
                "date": date,
                "status": status,
                "employee_id": employee_id,
            },
        )

    def cancel_appointment(self, shop_id: int, appointment_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
        return self._post(
            "/appointments/cancel",
            {"shop_id": shop_id, "appointment_id": appointment_id, "reason": reason},
        )

    def get_available_slots(
        self,
        shop_id: int,
        service_id: int,
        date: str,
        employee_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._post(
            "/appointments/available-slots",
            {
                "shop_id": shop_id,
                "service_id": service_id,
                "date": date,
                "employee_id": employee_id,
            },
        )