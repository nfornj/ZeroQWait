"""HR MCP server for employee and shift operations."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4
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

from db_interface import db_interface
import models  # noqa: F401
from modules.auth.models import UserRole
from modules.auth.schemas import UserCreate
from modules.auth.service import auth_service


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hr-mcp")

app = FastAPI(title="ZeroQwait HR MCP", version="1.0.0")


class ShopRequest(BaseModel):
    shop_id: int


class ListEmployeesRequest(ShopRequest):
    include_inactive: bool = False


class AddEmployeeRequest(ShopRequest):
    name: str
    email: str
    phone: Optional[str] = None
    role: str = "employee"
    employee_code: Optional[str] = None


class RemoveEmployeeRequest(ShopRequest):
    user_id: int


class ShiftListRequest(ShopRequest):
    date: Optional[str] = None
    user_id: Optional[int] = None


class AssignShiftRequest(ShopRequest):
    user_id: int
    start_time: str
    end_time: str
    date: str


class ClockRequest(ShopRequest):
    user_id: int
    action: str


def _parse_role(raw_role: str) -> UserRole:
    normalized = raw_role.strip().lower()
    return UserRole.EMPLOYEE if normalized not in UserRole._value2member_map_ else UserRole(normalized)


@app.post("/employees/list")
async def rest_list_employees(req: ListEmployeesRequest):
    employees = db_interface.get_shop_employees(req.shop_id, is_active=None if req.include_inactive else True)
    return {"shop_id": req.shop_id, "count": len(employees), "employees": employees}


@app.post("/employees/add")
async def rest_add_employee(req: AddEmployeeRequest):
    username_seed = req.email.split("@")[0].replace(".", "_")
    username = f"{username_seed}_{uuid4().hex[:6]}"
    user = auth_service.create_user(
        UserCreate(
            email=req.email,
            username=username,
            password=uuid4().hex,
            role=_parse_role(req.role),
        )
    )
    employee = db_interface.create_shop_employee(
        {
            "shop_id": req.shop_id,
            "user_id": user.id,
            "is_active": True,
            "employee_code": req.employee_code or f"EMP-{user.id}",
        }
    )
    return {
        "shop_id": req.shop_id,
        "user": user.model_dump(mode="json"),
        "employee": employee,
        "display_name": req.name,
        "phone": req.phone,
    }


@app.post("/employees/remove")
async def rest_remove_employee(req: RemoveEmployeeRequest):
    updated = db_interface.update_shop_employee(req.shop_id, req.user_id, {"is_active": False})
    if not updated:
        return {"success": False, "error": "Employee not found"}
    return {"success": True, "shop_id": req.shop_id, "user_id": req.user_id}


@app.post("/shifts/list")
async def rest_get_shifts(req: ShiftListRequest):
    target_date = datetime.fromisoformat(req.date) if req.date else datetime.now(timezone.utc)
    start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    shifts = db_interface.get_employee_shifts(req.shop_id, start, end, req.user_id)
    return {"shop_id": req.shop_id, "count": len(shifts), "shifts": shifts}


@app.post("/shifts/assign")
async def rest_assign_shift(req: AssignShiftRequest):
    shift_date = datetime.fromisoformat(req.date)
    start_hour, start_minute = [int(part) for part in req.start_time.split(":", 1)]
    end_hour, end_minute = [int(part) for part in req.end_time.split(":", 1)]
    clock_in = shift_date.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    clock_out = shift_date.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    shift = db_interface.create_employee_shift(
        {"shop_id": req.shop_id, "user_id": req.user_id, "clock_in": clock_in, "clock_out": clock_out}
    )
    return {"success": True, "shift": shift}


@app.post("/shifts/clock")
async def rest_clock_in_out(req: ClockRequest):
    if req.action == "in":
        shift = db_interface.create_employee_shift(
            {"shop_id": req.shop_id, "user_id": req.user_id, "clock_in": datetime.now(timezone.utc)}
        )
        return {"success": True, "action": "in", "shift": shift}

    active = db_interface.get_active_shift(req.user_id)
    if not active:
        return {"success": False, "error": "No active shift found"}
    shift = db_interface.update_employee_shift(active["id"], {"clock_out": datetime.now(timezone.utc)})
    return {"success": True, "action": "out", "shift": shift}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "hr-mcp"}


try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        name="zeroqwait-hr",
        instructions="Employee and shift management tools for ZeroQwait.",
    )

    @mcp.tool(description="List employees for a shop.")
    async def list_employees(shop_id: int, include_inactive: bool = False) -> dict:
        return await rest_list_employees(ListEmployeesRequest(shop_id=shop_id, include_inactive=include_inactive))

    @mcp.tool(description="Add an employee to a shop.")
    async def add_employee(
        shop_id: int,
        name: str,
        email: str,
        phone: Optional[str] = None,
        role: str = "employee",
        employee_code: Optional[str] = None,
    ) -> dict:
        return await rest_add_employee(
            AddEmployeeRequest(
                shop_id=shop_id,
                name=name,
                email=email,
                phone=phone,
                role=role,
                employee_code=employee_code,
            )
        )

    @mcp.tool(description="Deactivate an employee in a shop.")
    async def remove_employee(shop_id: int, user_id: int) -> dict:
        return await rest_remove_employee(RemoveEmployeeRequest(shop_id=shop_id, user_id=user_id))

    @mcp.tool(description="List shifts for a shop and optional employee/date.")
    async def get_shifts(shop_id: int, date: Optional[str] = None, user_id: Optional[int] = None) -> dict:
        return await rest_get_shifts(ShiftListRequest(shop_id=shop_id, date=date, user_id=user_id))

    @mcp.tool(description="Assign a shift to an employee.")
    async def assign_shift(shop_id: int, user_id: int, start_time: str, end_time: str, date: str) -> dict:
        return await rest_assign_shift(
            AssignShiftRequest(
                shop_id=shop_id,
                user_id=user_id,
                start_time=start_time,
                end_time=end_time,
                date=date,
            )
        )

    @mcp.tool(description="Clock an employee in or out.")
    async def clock_in_out(shop_id: int, user_id: int, action: str) -> dict:
        return await rest_clock_in_out(ClockRequest(shop_id=shop_id, user_id=user_id, action=action))

    try:
        app.mount("/mcp", mcp.sse_app())
    except AttributeError:
        logger.info("FastMCP SSE app not available; stdio MCP remains available.")
except ImportError:
    logger.warning("mcp package not installed — REST API remains available.")


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8892")))