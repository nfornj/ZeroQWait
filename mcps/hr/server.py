"""HR MCP server for employee and shift operations."""

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

from agents.tools import hr_tools


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hr-mcp")

app = FastAPI(title="ZeroQwait HR MCP", version="1.0.0")


class ShopRequest(BaseModel):
    shop_id: int


class ListEmployeesRequest(ShopRequest):
    include_inactive: bool = False


class AddEmployeeRequest(ShopRequest):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "employee"
    employee_code: Optional[str] = None
    created_by: Optional[int] = None


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


@app.post("/employees/list")
async def rest_list_employees(req: ListEmployeesRequest):
    result = hr_tools._local_list_employees(req.shop_id, include_inactive=req.include_inactive)
    employees = list(result.get("employees") or [])
    return {**result, "count": len(employees)}


@app.post("/employees/add")
async def rest_add_employee(req: AddEmployeeRequest):
    return hr_tools._local_add_employee(
        req.shop_id,
        req.name,
        email=req.email,
        phone=req.phone,
        role=req.role,
        employee_code=req.employee_code,
        created_by=req.created_by,
    )


@app.post("/employees/remove")
async def rest_remove_employee(req: RemoveEmployeeRequest):
    return hr_tools._local_remove_employee(req.shop_id, req.user_id)


@app.post("/shifts/list")
async def rest_get_shifts(req: ShiftListRequest):
    result = hr_tools._local_get_shifts(req.shop_id, req.date, req.user_id)
    shifts = list(result.get("shifts") or [])
    return {**result, "count": len(shifts)}


@app.post("/shifts/assign")
async def rest_assign_shift(req: AssignShiftRequest):
    return hr_tools._local_assign_shift(req.shop_id, req.user_id, req.start_time, req.end_time, req.date)


@app.post("/shifts/clock")
async def rest_clock_in_out(req: ClockRequest):
    return hr_tools._local_clock_in_out(req.shop_id, req.user_id, req.action)


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
        email: Optional[str] = None,
        phone: Optional[str] = None,
        role: str = "employee",
        employee_code: Optional[str] = None,
        created_by: Optional[int] = None,
    ) -> dict:
        return await rest_add_employee(
            AddEmployeeRequest(
                shop_id=shop_id,
                name=name,
                email=email,
                phone=phone,
                role=role,
                employee_code=employee_code,
                created_by=created_by,
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