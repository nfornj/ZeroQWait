"""Booking MCP server for queue, service, and appointment operations."""

from datetime import datetime, timezone
from contextlib import contextmanager
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
from modules.queues.models import Queue
from modules.queues.service import queue_service
from modules.appointments.service import appointment_service
from database import SessionLocal, set_tenant_for_request
from tenant_manager import resolve_shop_schema_from_metadata
from integrations.service_catalog_sync import sync_service_to_odoo
from redis_client import redis_client
from sqlalchemy import text


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


class OpenQueueRequest(ShopRequest):
    name: Optional[str] = "Main Queue"


class LockQueueJoinsRequest(ShopRequest):
    lock: bool = True  # True=stop new joins, False=re-allow
    reason: Optional[str] = None


class ServiceSearchRequest(ShopRequest):
    query: Optional[str] = None


class ServiceCreateRequest(ShopRequest):
    name: str
    cost: float
    duration_minutes: int = 30
    description: Optional[str] = None
    currency: str = "USD"


class ServiceUpdateRequest(ShopRequest):
    service_id: int
    name: Optional[str] = None
    cost: Optional[float] = None
    duration_minutes: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ServiceDeleteRequest(ShopRequest):
    service_id: int


class BookAppointmentRequest(ShopRequest):
    service_id: int
    scheduled_start: str
    customer_name: str
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    employee_id: Optional[int] = None
    notes: Optional[str] = None


class ListAppointmentsRequest(ShopRequest):
    date: Optional[str] = None
    status: Optional[str] = None
    employee_id: Optional[int] = None


class CancelAppointmentRequest(ShopRequest):
    appointment_id: int
    reason: Optional[str] = None


class AvailableSlotsRequest(ShopRequest):
    service_id: int
    date: str
    employee_id: Optional[int] = None


def _active_queue(shop_id: int):
    queues = queue_service.get_active_queues(shop_id)
    return queues[0] if queues else None


@contextmanager
def _tenant_context(shop_id: int):
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT id, tenant_schema, data_isolation_mode
                FROM platform.shops
                WHERE id = :shop_id
                """
            ),
            {"shop_id": shop_id},
        ).mappings().first()
        schema = resolve_shop_schema_from_metadata(dict(row)) if row else None
    finally:
        db.close()

    set_tenant_for_request(schema)
    try:
        yield
    finally:
        set_tenant_for_request(None)


def _parse_datetime(raw_value: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw_value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime value: {raw_value!r}")


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
        "accepting_joins": queue.accepting_joins if hasattr(queue, "accepting_joins") else True,
        "items": [item.model_dump(mode="json") for item in active_items],
        "total_in_queue": len(active_items),
        "waiting_count": len(waiting),
        "serving_count": len(serving),
        "next_customer": waiting[0].customer_name if waiting else None,
        "live_metrics": db_interface.get_shop_live_wait_metrics(shop_id),
    }


@app.post("/queue/list")
async def rest_list_queue(req: ShopRequest):
    with _tenant_context(req.shop_id):
        return _queue_snapshot(req.shop_id)


@app.post("/queue/join")
async def rest_join_queue(req: JoinQueueRequest):
    with _tenant_context(req.shop_id):
        result = db_interface.join_queue_for_shop(req.shop_id, req.customer_name, req.phone)
        if result.get("success") and req.phone:
            db_interface.upsert_shop_customer(
                req.shop_id,
                {"phone": req.phone, "name": req.customer_name},
            )
        return result


@app.post("/queue/call-next")
async def rest_call_next(req: CallNextRequest):
    with _tenant_context(req.shop_id):
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
    with _tenant_context(req.shop_id):
        if req.queue_item_id:
            return db_interface.get_queue_position(req.queue_item_id)
        return db_interface.get_shop_live_wait_metrics(req.shop_id)


@app.post("/queue/close")
async def rest_close_queue(req: CloseQueueRequest):
    with _tenant_context(req.shop_id):
        db = SessionLocal()
        try:
            queues = db.query(Queue).filter(Queue.shop_id == req.shop_id, Queue.is_active == True).all()
            if not queues:
                return {"success": False, "error": "No active queue for this shop"}
            for queue in queues:
                queue.is_active = False
                queue.accepting_joins = False
                if req.reason:
                    queue.lock_reason = req.reason
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


@app.post("/queue/open")
async def rest_open_queue(req: OpenQueueRequest):
    """Open (or re-activate) today's queue for a shop."""
    with _tenant_context(req.shop_id):
        db = SessionLocal()
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            existing = (
                db.query(Queue)
                .filter(Queue.shop_id == req.shop_id, Queue.date >= today_start)
                .order_by(Queue.date.desc())
                .first()
            )
            if existing:
                # Re-activate an existing queue instead of creating a duplicate
                existing.is_active = True
                existing.accepting_joins = True
                existing.lock_reason = None
                db.commit()
                return {
                    "success": True,
                    "shop_id": req.shop_id,
                    "queue_id": existing.id,
                    "action": "reactivated",
                }
            # No queue exists today — create a fresh one
            queue = Queue(
                shop_id=req.shop_id,
                name=req.name or "Main Queue",
                is_active=True,
                accepting_joins=True,
            )
            db.add(queue)
            db.commit()
            db.refresh(queue)
            return {
                "success": True,
                "shop_id": req.shop_id,
                "queue_id": queue.id,
                "action": "created",
            }
        except Exception as exc:
            db.rollback()
            return {"success": False, "error": str(exc)}
        finally:
            db.close()


@app.post("/queue/lock-joins")
async def rest_lock_queue_joins(req: LockQueueJoinsRequest):
    """Lock or unlock new customer joins without closing the queue (existing customers still served)."""
    with _tenant_context(req.shop_id):
        db = SessionLocal()
        try:
            queues = db.query(Queue).filter(Queue.shop_id == req.shop_id, Queue.is_active == True).all()
            if not queues:
                return {"success": False, "error": "No active queue for this shop"}
            for queue in queues:
                queue.accepting_joins = not req.lock
                queue.lock_reason = req.reason if req.lock else None
            db.commit()
            return {
                "success": True,
                "shop_id": req.shop_id,
                "accepting_joins": not req.lock,
                "reason": req.reason,
            }
        except Exception as exc:
            db.rollback()
            return {"success": False, "error": str(exc)}
        finally:
            db.close()


@app.post("/services/search")
async def rest_search_services(req: ServiceSearchRequest):
    with _tenant_context(req.shop_id):
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


@app.post("/services/create")
async def rest_create_service(req: ServiceCreateRequest):
    with _tenant_context(req.shop_id):
        service_data = {
            "shop_id": req.shop_id,
            "name": req.name,
            "cost": req.cost,
            "duration_minutes": req.duration_minutes,
            "description": req.description or "",
            "is_active": True,
            "currency": req.currency,
        }
        new_service = db_interface.create_shop_service(service_data)
        if not new_service:
            return {"error": "Failed to create service"}
        redis_client.tenant_delete(req.shop_id, "services")
        sync_service_to_odoo(req.shop_id, new_service, action="create")
        return {
            "message": f"Service '{req.name}' created at ${req.cost:.2f}",
            "service": new_service,
            "shop_id": req.shop_id,
        }


@app.post("/services/update")
async def rest_update_service(req: ServiceUpdateRequest):
    with _tenant_context(req.shop_id):
        updates = {
            key: value
            for key, value in {
                "name": req.name,
                "cost": req.cost,
                "duration_minutes": req.duration_minutes,
                "description": req.description,
                "is_active": req.is_active,
            }.items()
            if value is not None
        }
        if not updates:
            return {"error": "No updates provided"}

        updated = db_interface.update_shop_service(req.shop_id, req.service_id, updates)
        if not updated:
            return {"error": f"Service {req.service_id} not found"}
        redis_client.tenant_delete(req.shop_id, "services")
        sync_service_to_odoo(req.shop_id, updated, action="update")
        return {
            "message": f"Service '{updated.get('name', '')}' updated",
            "service": updated,
            "shop_id": req.shop_id,
        }


@app.post("/services/delete")
async def rest_delete_service(req: ServiceDeleteRequest):
    with _tenant_context(req.shop_id):
        updated = db_interface.update_shop_service(req.shop_id, req.service_id, {"is_active": False})
        if not updated:
            return {"error": f"Service {req.service_id} not found"}
        redis_client.tenant_delete(req.shop_id, "services")
        return {
            "message": f"Service '{updated.get('name', '')}' has been deactivated",
            "shop_id": req.shop_id,
        }


@app.post("/appointments/book")
async def rest_book_appointment(req: BookAppointmentRequest):
    try:
        parsed_start = _parse_datetime(req.scheduled_start)
    except ValueError as exc:
        return {"error": str(exc)}

    with _tenant_context(req.shop_id):
        return appointment_service.book_appointment(
            shop_id=req.shop_id,
            service_id=req.service_id,
            scheduled_start=parsed_start,
            customer_name=req.customer_name,
            customer_phone=req.customer_phone,
            customer_email=req.customer_email,
            employee_id=req.employee_id,
            notes=req.notes,
        )


@app.post("/appointments/list")
async def rest_list_appointments(req: ListAppointmentsRequest):
    with _tenant_context(req.shop_id):
        if req.date:
            try:
                parsed_date = _parse_datetime(req.date)
            except ValueError as exc:
                return {"error": str(exc)}
            appointments = appointment_service.list_appointments(
                shop_id=req.shop_id,
                date=parsed_date,
                status=req.status,
                employee_id=req.employee_id,
            )
        else:
            appointments = appointment_service.get_todays_appointments(req.shop_id)
        return {"appointments": appointments, "shop_id": req.shop_id, "count": len(appointments)}


@app.post("/appointments/cancel")
async def rest_cancel_appointment(req: CancelAppointmentRequest):
    with _tenant_context(req.shop_id):
        result = appointment_service.update_status(
            shop_id=req.shop_id,
            appointment_id=req.appointment_id,
            new_status="cancelled",
            reason=req.reason,
        )
        return result if result else {"error": "Appointment not found"}


@app.post("/appointments/available-slots")
async def rest_get_available_slots(req: AvailableSlotsRequest):
    try:
        parsed_date = _parse_datetime(req.date)
    except ValueError as exc:
        return {"error": str(exc)}
    with _tenant_context(req.shop_id):
        slots = appointment_service.get_available_slots(
            shop_id=req.shop_id,
            service_id=req.service_id,
            date=parsed_date,
            employee_id=req.employee_id,
        )
        return {"available_slots": slots, "shop_id": req.shop_id, "date": req.date}


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
        return await rest_list_queue(ShopRequest(shop_id=shop_id))

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

    @mcp.tool(description="Create a new service for a shop.")
    async def create_service(
        shop_id: int,
        name: str,
        cost: float,
        duration_minutes: int = 30,
        description: Optional[str] = None,
        currency: str = "USD",
    ) -> dict:
        return await rest_create_service(
            ServiceCreateRequest(
                shop_id=shop_id,
                name=name,
                cost=cost,
                duration_minutes=duration_minutes,
                description=description,
                currency=currency,
            )
        )

    @mcp.tool(description="Update an existing service for a shop.")
    async def update_service(
        shop_id: int,
        service_id: int,
        name: Optional[str] = None,
        cost: Optional[float] = None,
        duration_minutes: Optional[int] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> dict:
        return await rest_update_service(
            ServiceUpdateRequest(
                shop_id=shop_id,
                service_id=service_id,
                name=name,
                cost=cost,
                duration_minutes=duration_minutes,
                description=description,
                is_active=is_active,
            )
        )

    @mcp.tool(description="Deactivate a service for a shop.")
    async def delete_service(shop_id: int, service_id: int) -> dict:
        return await rest_delete_service(ServiceDeleteRequest(shop_id=shop_id, service_id=service_id))

    @mcp.tool(description="Book an appointment for a customer.")
    async def book_appointment(
        shop_id: int,
        service_id: int,
        scheduled_start: str,
        customer_name: str,
        customer_phone: Optional[str] = None,
        customer_email: Optional[str] = None,
        employee_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> dict:
        return await rest_book_appointment(
            BookAppointmentRequest(
                shop_id=shop_id,
                service_id=service_id,
                scheduled_start=scheduled_start,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_email=customer_email,
                employee_id=employee_id,
                notes=notes,
            )
        )

    @mcp.tool(description="List appointments for a shop.")
    async def list_appointments(
        shop_id: int,
        date: Optional[str] = None,
        status: Optional[str] = None,
        employee_id: Optional[int] = None,
    ) -> dict:
        return await rest_list_appointments(
            ListAppointmentsRequest(
                shop_id=shop_id,
                date=date,
                status=status,
                employee_id=employee_id,
            )
        )

    @mcp.tool(description="Cancel an appointment for a shop.")
    async def cancel_appointment(shop_id: int, appointment_id: int, reason: Optional[str] = None) -> dict:
        return await rest_cancel_appointment(
            CancelAppointmentRequest(shop_id=shop_id, appointment_id=appointment_id, reason=reason)
        )

    @mcp.tool(description="Get available appointment slots for a shop and service.")
    async def get_available_slots(
        shop_id: int,
        service_id: int,
        date: str,
        employee_id: Optional[int] = None,
    ) -> dict:
        return await rest_get_available_slots(
            AvailableSlotsRequest(
                shop_id=shop_id,
                service_id=service_id,
                date=date,
                employee_id=employee_id,
            )
        )

    try:
        app.mount("/mcp", mcp.sse_app())
    except AttributeError:
        logger.info("FastMCP SSE app not available; stdio MCP remains available.")
except ImportError:
    logger.warning("mcp package not installed — REST API remains available.")


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8890")))
