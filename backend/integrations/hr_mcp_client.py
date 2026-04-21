import logging
import os
from typing import Any, Dict, Optional

import httpx


logger = logging.getLogger(__name__)

HR_MCP_URL = os.getenv("HR_MCP_URL", "http://127.0.0.1:8892")


class HRMCPClient:
    """Synchronous client for the HR MCP REST surface."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 10.0):
        self.base_url = (base_url or HR_MCP_URL).rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                response = client.post(path, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("HR MCP returned %s for %s: %s", exc.response.status_code, path, exc.response.text)
            return {"error": f"HR MCP returned {exc.response.status_code} for {path}"}
        except httpx.HTTPError as exc:
            logger.error("HR MCP request failed for %s: %s", path, exc)
            return {"error": f"HR MCP request failed for {path}: {exc}"}

        try:
            data = response.json()
        except ValueError:
            logger.error("HR MCP returned invalid JSON for %s", path)
            return {"error": f"HR MCP returned invalid JSON for {path}"}

        if isinstance(data, dict):
            return data
        return {"result": data}

    def list_employees(self, shop_id: int, include_inactive: bool = False) -> Dict[str, Any]:
        return self._post("/employees/list", {"shop_id": shop_id, "include_inactive": include_inactive})

    def add_employee(
        self,
        shop_id: int,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        role: str = "employee",
        employee_code: Optional[str] = None,
        created_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._post(
            "/employees/add",
            {
                "shop_id": shop_id,
                "name": name,
                "email": email,
                "phone": phone,
                "role": role,
                "employee_code": employee_code,
                "created_by": created_by,
            },
        )

    def remove_employee(self, shop_id: int, user_id: int) -> Dict[str, Any]:
        return self._post("/employees/remove", {"shop_id": shop_id, "user_id": user_id})

    def get_shifts(self, shop_id: int, date: Optional[str] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
        return self._post("/shifts/list", {"shop_id": shop_id, "date": date, "user_id": user_id})

    def assign_shift(self, shop_id: int, user_id: int, start_time: str, end_time: str, date: str) -> Dict[str, Any]:
        return self._post(
            "/shifts/assign",
            {
                "shop_id": shop_id,
                "user_id": user_id,
                "start_time": start_time,
                "end_time": end_time,
                "date": date,
            },
        )

    def clock_in_out(self, shop_id: int, user_id: int, action: str) -> Dict[str, Any]:
        return self._post("/shifts/clock", {"shop_id": shop_id, "user_id": user_id, "action": action})