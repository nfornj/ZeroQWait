"""Booking MCP server for queue and service operations."""

from datetime import datetime, timezone
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

from db_interface import db_interface
import models  # noqa: F401
from modules.queues import schemas as queue_schemas
from modules.queues.models import Queue
from modules.queues.service import queue_service
from database import SessionLocal


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("booking-mcp")

app = FastAPI(title="ZeroQwait Booking MCP", version="1.0.0")


class ShopRequest(BaseModel):
    shop_id: int


class JoinQueueRequest(ShopRequest):
    customer_name: str
    phone: Optional[str] = None


class CallNextRequest(ShopRequest):
    employee_id: Optional[int] = None


class WaitTimeRequest(ShopRequest):
    queue_item_id: Optional[int] = None


class CloseQueueRequest(ShopRequest):
    reason: Optional[str] = None


class ServiceSearchRequest(ShopRequest):
    query: Optional[str] = None


def _active_queue(shop_id: int):
    queues = queue_service.get_active_queues(shop_id)
    return queues[0] if queues else None


def _queue_snapshot(shop_id: int) -> dict:
    queue = _active_queue(shop_id)
    if not queue:
        return {
            "shop_id": shop_id,
            "queue_id": None,
            "items": [],
            "total_in_queue": 0,
            "waiting_count": 0,
            "serving_count": 0,
            "next_customer": None,
            "live_metrics": db_interface.get_shop_live_wait_metrics(shop_id),
        }

    items = queue_service.get_queue_items(queue.id)
    active_items = [
        item for item in items if item.status in ["waiting", "being_served"]
    ]
    active_items.sort(key=lambda item: item.position)
    waiting = [item for item in active_items if item.status == "waiting"]
    serving = [item for item in active_items if item.status == "being_served"]

    return {
        "shop_id": shop_id,
        "queue_id": queue.id,
        "items": [item.model_dump(mode="json") for item in active_items],
        "total_in_queue": len(active_items),
        "waiting_count": len(waiting),
        "serving_count": len(serving),
        "next_customer": waiting[0].customer_name if waiting else None,
        "live_metrics": db_interface.get_shop_live_wait_metrics(shop_id),
    }


@app.post("/queue/list")
async def rest_list_queue(req: ShopRequest):
    return _queue_snapshot(req.shop_id)


@app.post("/queue/join")
async def rest_join_queue(req: JoinQueueRequest):
    result = db_interface.join_queue_for_shop(req.shop_id, req.customer_name, req.phone)
    if result.get("success") and req.phone:
        db_interface.upsert_shop_customer(
            req.shop_id,
            {"phone": req.phone, "name": req.customer_name},
        )
    return result


@app.post("/queue/call-next")
async def rest_call_next(req: CallNextRequest):
    queue = _active_queue(req.shop_id)
    if not queue:
        return {"error": "No active queue for this shop"}

    items = queue_service.get_queue_items(queue.id)
    for serving in [item for item in items if item.status == "being_served"]:
        queue_service.update_queue_item(
            serving.id,
            {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()},
        )

    waiting = [item for item in items if item.status == "waiting"]
    waiting.sort(key=lambda item: item.position)
    if not waiting:
        return {"error": "No customers waiting"}

    employee_id = req.employee_id
    if employee_id is None:
        employees = db_interface.get_shop_employees(req.shop_id, is_active=True)
        if employees:
            employee_id = employees[0].get("user_id")

    next_item = queue_service.update_queue_item(
        waiting[0].id,
        {
            "status": "being_served",
            "service_started_at": datetime.now(timezone.utc).isoformat(),
            "assigned_employee_id": employee_id,
        },
    )
    return next_item.model_dump(mode="json") if next_item else {"error": "Failed to update queue item"}


@app.post("/queue/wait-time")
async def rest_wait_time(req: WaitTimeRequest):
    if req.queue_item_id:
        return db_interface.get_queue_position(req.queue_item_id)
    return db_interface.get_shop_live_wait_metrics(req.shop_id)


@app.post("/queue/close")
async def rest_close_queue(req: CloseQueueRequest):
    db = SessionLocal()
    try:
        queues = db.query(Queue).filter(Queue.shop_id == req.shop_id, Queue.is_active == True).all()
        if not queues:
            return {"success": False, "error": "No active queue for this shop"}
        for queue in queues:
            queue.is_active = False
        db.commit()
        return {
            "success": True,
            "shop_id": req.shop_id,
            "closed_queues": len(queues),
            "reason": req.reason or "Owner request",
        }
    except Exception as exc:
        db.rollback()
        return {"success": False, "error": str(exc)}
    finally:
        db.close()


@app.post("/services/search")
async def rest_search_services(req: ServiceSearchRequest):
    services = db_interface.get_shop_services(req.shop_id)
    query = (req.query or "").strip().lower()
    if query:
        services = [
            service
            for service in services
            if query in str(service.get("name", "")).lower()
            or query in str(service.get("description", "")).lower()
        ]
    return {
        "shop_id": req.shop_id,
        "count": len(services),
        "services": services,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "booking-mcp"}


try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        name="zeroqwait-booking",
        instructions="Queue management and service discovery tools for ZeroQwait.",
    )

    @mcp.tool(description="List the active queue and current wait metrics for a shop.")
    async def list_queue(shop_id: int) -> dict:
        return _queue_snapshot(shop_id)

    @mcp.tool(description="Join the active queue for a shop.")
    async def join_queue(shop_id: int, customer_name: str, phone: Optional[str] = None) -> dict:
        return await rest_join_queue(JoinQueueRequest(shop_id=shop_id, customer_name=customer_name, phone=phone))

    @mcp.tool(description="Call the next waiting customer in the active queue.")
    async def call_next(shop_id: int, employee_id: Optional[int] = None) -> dict:
        return await rest_call_next(CallNextRequest(shop_id=shop_id, employee_id=employee_id))

    @mcp.tool(description="Estimate wait time for a shop or queue item.")
    async def get_wait_time(shop_id: int, queue_item_id: Optional[int] = None) -> dict:
        return await rest_wait_time(WaitTimeRequest(shop_id=shop_id, queue_item_id=queue_item_id))

    @mcp.tool(description="Close all active queues for a shop.")
    async def close_queue(shop_id: int, reason: Optional[str] = None) -> dict:
        return await rest_close_queue(CloseQueueRequest(shop_id=shop_id, reason=reason))

    @mcp.tool(description="Search active services for a shop.")
    async def search_services(shop_id: int, query: Optional[str] = None) -> dict:
        return await rest_search_services(ServiceSearchRequest(shop_id=shop_id, query=query))

    try:
        app.mount("/mcp", mcp.sse_app())
    except AttributeError:
        logger.info("FastMCP SSE app not available; stdio MCP remains available.")
except ImportError:
    logger.warning("mcp package not installed — REST API remains available.")


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8890")))
