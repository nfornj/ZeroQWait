from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import List, Optional, Dict
from modules.queues import schemas
from modules.queues.service import queue_service
from modules.shops.service import shop_service
from modules.auth.service import auth_service
from db_interface import db_interface
from websocket_manager import manager
from shared.auth_utils import get_current_user, get_current_user_optional
from permissions import check_shop_access
from redis_client import redis_client
from database import SessionLocal
from audit_logger import audit
from datetime import datetime, timedelta
import random

router = APIRouter()

# Helper function to anonymize customer names for privacy
def anonymize_customer_name(name: str) -> str:
    if not name or not name.strip():
        return "Customer"
    
    parts = name.strip().split()
    if len(parts) == 1:
        return parts[0][:3] + "..." if len(parts[0]) > 3 else parts[0]
    else:
        return f"{parts[0]} {parts[-1][0]}."

# Helper function to populate employee details for queue items
def populate_employee_details(items: List[schemas.QueueItem]) -> List[schemas.QueueItem]:
    if not items:
        return items
    
    # Get unique employee IDs
    employee_ids = list(set([item.assigned_employee_id for item in items if item.assigned_employee_id]))
    
    if not employee_ids:
        return items
    
    try:
        employees_dict = {}
        for emp_id in employee_ids:
            user = auth_service.get_user_by_id(emp_id)
            if user:
                employees_dict[emp_id] = {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    # "profile_photo_url": user.profile_photo_url # schemas.User might not have this? Check schema.
                    # schemas.User inherits UserBase which has email, username. Custom fields?
                    # Models have it. Schema should have it? 
                    # schemas.User inherits UserBase. UserBase doesn't have photo.
                    # We might need to update Schema or fetch Dict.
                    # For now, omit or update schemas.User later.
                }
            
        for item in items:
            if item.assigned_employee_id:
                item.assigned_employee = employees_dict.get(item.assigned_employee_id)
    except Exception:
        pass
    
    return items

QUEUE_STATUS_WAITING = "waiting"
QUEUE_STATUS_BEING_SERVED = "being_served"
QUEUE_STATUS_COMPLETED = "completed"
QUEUE_STATUS_CANCELLED = "cancelled"
CHECKED_OUT_MARKER_PREFIX = "CHECKED_OUT_AT:"


def _append_checked_out_marker(notes: Optional[str], timestamp_iso: str) -> str:
    existing = (notes or "").splitlines()
    cleaned = [line for line in existing if not line.startswith(CHECKED_OUT_MARKER_PREFIX)]
    cleaned.append(f"{CHECKED_OUT_MARKER_PREFIX}{timestamp_iso}")
    return "\n".join([line for line in cleaned if line.strip()])


def _is_checked_out(notes: Optional[str]) -> bool:
    if not notes:
        return False
    return any(line.startswith(CHECKED_OUT_MARKER_PREFIX) for line in notes.splitlines())


def get_least_busy_employee(shop_id: int) -> Optional[int]:
    """Find the clocked-in employee with the fewest active queue items."""
    active_shifts = db_interface.get_shop_active_shifts(shop_id)
    if not active_shifts:
        return None

    clocked_in_ids = [s["user_id"] for s in active_shifts]

    queues = queue_service.get_active_queues(shop_id)
    if not queues:
        return clocked_in_ids[0]

    load = {uid: 0 for uid in clocked_in_ids}
    for queue in queues:
        items = queue_service.get_queue_items(queue.id)
        for item in items:
            if item.status in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]:
                if item.assigned_employee_id in load:
                    load[item.assigned_employee_id] += 1

    return min(load, key=load.get)


def _build_shop_live_snapshot(shop_id: int) -> Dict:
    """Build a single payload consumed by kiosk/public real-time panels."""
    queues = queue_service.get_active_queues(shop_id)
    queue_items: List[Dict] = []
    completed_items: List[Dict] = []
    if queues:
        queue = queues[0]
        items = queue_service.get_queue_items(queue.id)
        active_items = [item for item in items if item.status in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]]
        active_items.sort(key=lambda x: x.position)
        for idx, item in enumerate(active_items, start=1):
            queue_items.append({
                "id": item.id,
                "position": idx,
                "status": item.status,
                "checked_in_at": getattr(item, "checked_in_at", None),
            })

        # Include recently completed items (last 10 min) for checkout notifications
        ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
        for item in items:
            if (
                item.status == QUEUE_STATUS_COMPLETED
                and item.completed_at
                and item.completed_at >= ten_minutes_ago
                and not _is_checked_out(item.notes)
            ):
                completed_items.append({
                    "id": item.id,
                    "customer_name": item.customer_name,
                    "service_cost": item.service_cost or 0,
                    "service_name": item.service.name if item.service else None,
                    "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                })

    metrics = db_interface.get_shop_live_wait_metrics(shop_id)
    return {
        "type": "shop_live_snapshot",
        "shop_id": shop_id,
        "queue_items": queue_items,
        "completed_items": completed_items,
        "live_metrics": metrics,
        "generated_at": datetime.utcnow().isoformat(),
    }


async def _broadcast_shop_live_snapshot(shop_id: int) -> None:
    """Push current queue + metrics to all websocket clients for this shop."""
    await manager.broadcast(str(shop_id), _build_shop_live_snapshot(shop_id))


@router.get("/shop/{shop_id}/recently-completed")
def get_recently_completed(shop_id: int):
    """Return queue items completed in the last 10 minutes for customer checkout."""
    queues = queue_service.get_active_queues(shop_id)
    if not queues:
        return []
    items = queue_service.get_queue_items(queues[0].id)
    ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
    result = []
    for item in items:
        if (
            item.status == QUEUE_STATUS_COMPLETED
            and item.completed_at
            and item.completed_at >= ten_minutes_ago
            and not _is_checked_out(item.notes)
        ):
            result.append({
                "id": item.id,
                "customer_name": item.customer_name,
                "service_cost": item.service_cost or 0,
                "service_name": item.service.name if item.service else None,
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            })
    return result


@router.get("/shop/{shop_id}/all", response_model=List[schemas.Queue])
def get_all_queues(
    shop_id: int,
    current_user: dict = Depends(get_current_user)
):
    check_shop_access(shop_id, current_user, require_owner=True)
    try:
        queues = queue_service.get_all_queues(shop_id)
        for queue in queues:
            items = queue_service.get_queue_items(queue.id)
            items = populate_employee_details(items)
            queue.queue_items = items
        return queues
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch queues: {str(e)}")


@router.post("/shop/{shop_id}", response_model=schemas.Queue, status_code=status.HTTP_201_CREATED)
def create_queue(
    shop_id: int,
    queue_create: schemas.QueueCreate,
    current_user: dict = Depends(get_current_user)
):
    check_shop_access(shop_id, current_user, require_owner=True)
    try:
        queue = queue_service.create_queue(queue_create, shop_id)
        return queue
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create queue: {str(e)}")

@router.get("/shop/{shop_id}/active", response_model=schemas.Queue)
def get_active_queue(
    shop_id: int,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    try:
        # Check if user has access to this shop (owner or employee)
        has_shop_access = False
        if current_user:
            try:
                check_shop_access(shop_id, current_user, require_owner=False)
                has_shop_access = True
            except HTTPException:
                has_shop_access = False
        
        queues = queue_service.get_active_queues(shop_id)
        if not queues:
             q_create = schemas.QueueCreate(name="Main Queue", is_active=True)
             queue = queue_service.create_queue(q_create, shop_id)
        else:
             queue = queues[0]
             
        items = queue_service.get_queue_items(queue.id)
        
        # Renumber positions dynamically for active customers only
        active_items = [item for item in items if item.status in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]]
        for idx, item in enumerate(active_items, start=1):
            item.position = idx
        
        items = populate_employee_details(items)
        
        if not has_shop_access:
            for item in items:
                if item.customer_name:
                    item.customer_name = anonymize_customer_name(item.customer_name)
                item.customer_phone = None
                item.customer_email = None
                item.notes = None
        
        queue.queue_items = items
        return queue
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch queue: {str(e)}")

@router.post("/shop/{shop_id}/join", response_model=schemas.QueueItem)
async def join_queue(
    shop_id: int,
    queue_item: schemas.QueueItemCreate,
    request: Request,
):
    client_ip = request.client.host if request.client else "unknown"
    # Rate-limit: max 10 join attempts per IP per minute to prevent queue flooding
    if not redis_client.check_rate_limit(client_ip, limit=10, window=60):
        await audit(
            action="QUEUE",
            detail="queue_join_rate_limited",
            shop_id=shop_id,
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait before joining again.",
        )
    try:
        shop = shop_service.get_shop(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
            
        queues = queue_service.get_active_queues(shop_id)
        if not queues:
            q_create = schemas.QueueCreate(name="Main Queue", is_active=True)
            queue = queue_service.create_queue(q_create, shop_id)
        else:
            queue = queues[0]
            
        # Tier checks omitted for brevity (should implement)
        
        new_item = queue_service.create_queue_item(queue_item, queue.id)
        if new_item:
            # Auto-assign to least busy clocked-in employee
            employee_id = get_least_busy_employee(shop_id)
            if employee_id:
                queue_service.update_queue_item(new_item.id, {"assigned_employee_id": employee_id})
                new_item.assigned_employee_id = employee_id
            # Invalidate queue cache for this shop
            redis_client.invalidate_queue_cache(shop_id)
            # Dynamic position
            all_items = queue_service.get_queue_items(queue.id)
            active_items = [i for i in all_items if i.status in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]]
            new_item.position = len(active_items)
            await _broadcast_shop_live_snapshot(shop_id)
            await audit(
                action="QUEUE",
                detail="queue_join",
                shop_id=shop_id,
                ip_address=client_ip,
                metadata={"customer_name": queue_item.customer_name, "queue_item_id": new_item.id},
            )
            return new_item
        raise HTTPException(status_code=500, detail="Failed to join queue")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to join queue: {str(e)}")

@router.patch("/items/{item_id}/status")
async def update_queue_item_status(
    item_id: int,
    new_status: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        item = queue_service.get_queue_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Queue item not found")
            
        queue = queue_service.get_queue(item.queue_id)
        if not queue:
            raise HTTPException(status_code=404, detail="Queue not found")
            
        check_shop_access(queue.shop_id, current_user, require_owner=False)
        
        update_data = {"status": new_status}
        if new_status == QUEUE_STATUS_BEING_SERVED:
            update_data["service_started_at"] = datetime.utcnow().isoformat()
        elif new_status in [QUEUE_STATUS_COMPLETED, QUEUE_STATUS_CANCELLED]:
            update_data["completed_at"] = datetime.utcnow().isoformat()
            
        updated = queue_service.update_queue_item(item_id, update_data)
        # Invalidate queue cache for this shop
        redis_client.invalidate_queue_cache(queue.shop_id)
        await _broadcast_shop_live_snapshot(queue.shop_id)
        return updated
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/items/{item_id}/checkout")
async def mark_queue_item_checked_out(
    item_id: int,
):
    """Mark a queue item as checked out after successful payment."""
    try:
        item = queue_service.get_queue_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Queue item not found")

        queue = queue_service.get_queue(item.queue_id)
        if not queue:
            raise HTTPException(status_code=404, detail="Queue not found")

        now_iso = datetime.utcnow().isoformat()
        update_data = {
            "notes": _append_checked_out_marker(item.notes, now_iso),
        }

        # Ensure paid customers are not left in active queue states.
        if item.status in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]:
            update_data["status"] = QUEUE_STATUS_COMPLETED
            update_data["completed_at"] = now_iso
        elif item.status == QUEUE_STATUS_COMPLETED and not item.completed_at:
            update_data["completed_at"] = now_iso

        updated = queue_service.update_queue_item(item_id, update_data)
        redis_client.invalidate_queue_cache(queue.shop_id)
        await _broadcast_shop_live_snapshot(queue.shop_id)

        return {
            "ok": True,
            "queue_item_id": item_id,
            "status": updated.status if updated else item.status,
            "checked_out": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark checked out: {str(e)}")

@router.post("/{queue_id}/call-next", response_model=schemas.QueueItem)
async def call_next_customer(
    queue_id: int,
    employee_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    try:
        queue = queue_service.get_queue(queue_id)
        if not queue:
            raise HTTPException(status_code=404, detail="Queue not found")
            
        check_shop_access(queue.shop_id, current_user, require_owner=False)
        
        assigned_employee_id = employee_id
        if assigned_employee_id is None:
            # Random assignment logic omitted, default to current user
            assigned_employee_id = current_user.id
            
        items = queue_service.get_queue_items(queue_id)
        
        # Complete serving
        currently_serving = [i for i in items if i.status == QUEUE_STATUS_BEING_SERVED]
        for serving in currently_serving:
            queue_service.update_queue_item(serving.id, {
                "status": QUEUE_STATUS_COMPLETED,
                "completed_at": datetime.utcnow().isoformat()
            })
            
        # Find next
        waiting = [i for i in items if i.status == QUEUE_STATUS_WAITING]
        waiting.sort(key=lambda x: x.position)
        
        if not waiting:
             raise HTTPException(status_code=404, detail="No customers waiting")
             
        next_item = waiting[0]
        update_data = {
            "status": QUEUE_STATUS_BEING_SERVED,
            "service_started_at": datetime.utcnow().isoformat(),
            "assigned_employee_id": assigned_employee_id
        }
        
        result = queue_service.update_queue_item(next_item.id, update_data)
        # Invalidate queue cache for this shop
        redis_client.invalidate_queue_cache(queue.shop_id)
        await _broadcast_shop_live_snapshot(queue.shop_id)
        
        if result and result.assigned_employee_id:
             user = auth_service.get_user_by_id(result.assigned_employee_id)
             if user:
                 # Populate logic
                 result.assigned_employee = {"id": user.id, "username": user.username}
                 
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Additional endpoints (remove, leave, estimate) follow similar pattern
# Omitting for brevity unless specifically requested to ensure file size limits


@router.get("/items/{item_id}/estimate")
def get_wait_estimate(item_id: int):
    """Get a customer's current position, people ahead and estimated wait."""
    try:
        result = db_interface.get_queue_position(item_id)
        if result.get("error"):
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get wait estimate: {str(e)}")


@router.get("/shop/{shop_id}/live-metrics")
def get_shop_live_metrics(shop_id: int):
    """AI-enhanced real-time wait metrics for kiosk/landing experiences."""
    try:
        result = db_interface.get_shop_live_wait_metrics(shop_id)
        if result.get("error"):
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get live metrics: {str(e)}")


# ──────────────────────────────────────
# Queue detail & smart management
# ──────────────────────────────────────

@router.get("/shop/{shop_id}/active-employees")
def get_active_employees(
    shop_id: int,
    current_user: dict = Depends(get_current_user)
):
    """List clocked-in employees with their current queue load."""
    check_shop_access(shop_id, current_user, require_owner=False)
    try:
        active_shifts = db_interface.get_shop_active_shifts(shop_id)
        if not active_shifts:
            return []

        # Count load per employee
        load_map: Dict[int, int] = {}
        queues = queue_service.get_active_queues(shop_id)
        for queue in queues:
            items = queue_service.get_queue_items(queue.id)
            for item in items:
                if item.status in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]:
                    eid = item.assigned_employee_id
                    if eid:
                        load_map[eid] = load_map.get(eid, 0) + 1

        result = []
        for shift in active_shifts:
            uid = shift["user_id"]
            user = auth_service.get_user_by_id(uid)
            if user:
                result.append({
                    "user_id": uid,
                    "username": user.username,
                    "email": user.email,
                    "active_items": load_map.get(uid, 0),
                    "clock_in": shift.get("clock_in"),
                })
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active employees: {str(e)}")


@router.get("/{queue_id}/items", response_model=List[schemas.QueueItem])
def get_queue_items_detail(
    queue_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get all items in a queue with employee details (owner/employee drill-down)."""
    try:
        queue = queue_service.get_queue(queue_id)
        if not queue:
            raise HTTPException(status_code=404, detail="Queue not found")
        check_shop_access(queue.shop_id, current_user, require_owner=False)

        items = queue_service.get_queue_items(queue_id)
        # Renumber active positions
        active_items = [i for i in items if i.status in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]]
        active_items.sort(key=lambda x: x.position)
        for idx, item in enumerate(active_items, start=1):
            item.position = idx

        items = populate_employee_details(items)
        return items
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get queue items: {str(e)}")


@router.patch("/items/{item_id}/reassign", response_model=schemas.QueueItem)
async def reassign_queue_item(
    item_id: int,
    body: schemas.ReassignRequest,
    current_user: dict = Depends(get_current_user)
):
    """Reassign a queue item to a different employee."""
    try:
        item = queue_service.get_queue_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Queue item not found")

        queue = queue_service.get_queue(item.queue_id)
        if not queue:
            raise HTTPException(status_code=404, detail="Queue not found")
        check_shop_access(queue.shop_id, current_user, require_owner=False)

        if item.status not in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]:
            raise HTTPException(status_code=400, detail="Can only reassign waiting or being-served customers")

        updated = queue_service.update_queue_item(item_id, {"assigned_employee_id": body.employee_id})
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to reassign")

        redis_client.invalidate_queue_cache(queue.shop_id)
        await _broadcast_shop_live_snapshot(queue.shop_id)

        # Populate employee details on result
        user = auth_service.get_user_by_id(body.employee_id)
        if user:
            updated.assigned_employee = {"id": user.id, "username": user.username, "email": user.email}
        return updated
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reassign: {str(e)}")


@router.post("/items/{item_id}/serve", response_model=schemas.QueueItem)
async def serve_queue_item(
    item_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Serve a specific customer (out of order)."""
    try:
        item = queue_service.get_queue_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Queue item not found")

        queue = queue_service.get_queue(item.queue_id)
        if not queue:
            raise HTTPException(status_code=404, detail="Queue not found")
        check_shop_access(queue.shop_id, current_user, require_owner=False)

        if item.status != QUEUE_STATUS_WAITING:
            raise HTTPException(status_code=400, detail="Only waiting customers can be served")

        update_data = {
            "status": QUEUE_STATUS_BEING_SERVED,
            "service_started_at": datetime.utcnow().isoformat(),
        }
        if not item.assigned_employee_id:
            update_data["assigned_employee_id"] = current_user["id"]

        updated = queue_service.update_queue_item(item_id, update_data)
        redis_client.invalidate_queue_cache(queue.shop_id)
        await _broadcast_shop_live_snapshot(queue.shop_id)
        return updated
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to serve customer: {str(e)}")


@router.delete("/items/{item_id}/leave")
async def leave_queue(item_id: int):
    """Customer self-removes from queue (no auth required for walk-ins)."""
    try:
        item = queue_service.get_queue_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Queue item not found")

        if item.status not in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]:
            raise HTTPException(status_code=400, detail="Customer is not in an active queue position")

        queue = queue_service.get_queue(item.queue_id)
        updated = queue_service.update_queue_item(item_id, {
            "status": QUEUE_STATUS_CANCELLED,
            "completed_at": datetime.utcnow().isoformat(),
        })
        if queue:
            redis_client.invalidate_queue_cache(queue.shop_id)
            await _broadcast_shop_live_snapshot(queue.shop_id)
        return {"message": "Left queue successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to leave queue: {str(e)}")


@router.delete("/{queue_id}")
async def delete_queue(
    queue_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a queue and all its items (owner only)."""
    try:
        queue = queue_service.get_queue(queue_id)
        if not queue:
            raise HTTPException(status_code=404, detail="Queue not found")
        check_shop_access(queue.shop_id, current_user, require_owner=True)
        # Delete all items first (cascade)
        db = SessionLocal()
        try:
            from modules.queues.models import Queue as QueueModel, QueueItem as QueueItemModel
            db.query(QueueItemModel).filter(QueueItemModel.queue_id == queue_id).delete()
            db.query(QueueModel).filter(QueueModel.id == queue_id).delete()
            db.commit()
        finally:
            db.close()
        redis_client.invalidate_queue_cache(queue.shop_id)
        return {"message": "Queue deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete queue: {str(e)}")


@router.post("/{queue_id}/reset")
async def reset_queue(
    queue_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Remove all items from a queue without deleting the queue itself (owner only)."""
    try:
        queue = queue_service.get_queue(queue_id)
        if not queue:
            raise HTTPException(status_code=404, detail="Queue not found")
        check_shop_access(queue.shop_id, current_user, require_owner=True)
        db = SessionLocal()
        try:
            from modules.queues.models import QueueItem as QueueItemModel
            deleted = db.query(QueueItemModel).filter(QueueItemModel.queue_id == queue_id).delete()
            db.commit()
        finally:
            db.close()
        redis_client.invalidate_queue_cache(queue.shop_id)
        await _broadcast_shop_live_snapshot(queue.shop_id)
        return {"message": f"Queue reset: {deleted} items removed"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset queue: {str(e)}")


@router.delete("/items/{item_id}")
async def remove_queue_item(
    item_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Remove a customer from queue (owner/employee action)."""
    try:
        item = queue_service.get_queue_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Queue item not found")

        queue = queue_service.get_queue(item.queue_id)
        if not queue:
            raise HTTPException(status_code=404, detail="Queue not found")
        check_shop_access(queue.shop_id, current_user, require_owner=False)

        updated = queue_service.update_queue_item(item_id, {
            "status": QUEUE_STATUS_CANCELLED,
            "completed_at": datetime.utcnow().isoformat(),
        })
        redis_client.invalidate_queue_cache(queue.shop_id)
        await _broadcast_shop_live_snapshot(queue.shop_id)
        return {"message": "Customer removed from queue"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove customer: {str(e)}")
