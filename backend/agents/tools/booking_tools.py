from typing import Any, Dict, Optional
from db_interface import db_interface


def list_queue(shop_id: int) -> Dict[str, Any]:
    """Get active queue items for a shop via db_interface."""
    try:
        session = db_interface.get_session()
        from modules.queues.models import Queue, QueueItem
        from modules.queues.models import QueueStatus
        
        # Get active queue for this shop
        queue = session.query(Queue).filter(
            Queue.shop_id == shop_id,
            Queue.is_active == True
        ).first()
        
        if not queue:
            session.close()
            return {
                "queue_items": [],
                "live_metrics": {},
                "shop_id": shop_id,
                "error": "No active queue found"
            }
        
        # Get queue items for this queue
        items = session.query(QueueItem).filter(
            QueueItem.queue_id == queue.id,
            QueueItem.status == QueueStatus.WAITING
        ).order_by(QueueItem.position).all()
        
        live_metrics = db_interface.get_shop_live_wait_metrics(shop_id)
        session.close()
        
        items_list = [db_interface._model_to_dict(item) for item in items]
        return {
            "queue_items": items_list or [],
            "live_metrics": live_metrics or {},
            "shop_id": shop_id
        }
    except Exception as e:
        return {"error": str(e)}


def join_queue(shop_id: int, customer_name: str, phone: Optional[str] = None) -> Dict[str, Any]:
    """Join a queue (Phase 2 placeholder)."""
    try:
        # For now, return a confirmation message
        return {
            "message": f"Added {customer_name} to queue",
            "shop_id": shop_id,
            "status": "added"
        }
    except Exception as e:
        return {"error": str(e)}


def call_next(shop_id: int, employee_id: Optional[int] = None) -> Dict[str, Any]:
    """Call next customer from queue (Phase 2 placeholder)."""
    try:
        # For now, return placeholder response
        return {
            "message": "Next customer called",
            "shop_id": shop_id,
            "status": "called"
        }
    except Exception as e:
        return {"error": str(e)}


def get_wait_time(shop_id: int, queue_item_id: Optional[int] = None) -> Dict[str, Any]:
    """Get wait time estimate."""
    try:
        live_metrics = db_interface.get_shop_live_wait_metrics(shop_id)
        return {
            "estimated_wait_minutes": live_metrics.get("estimated_wait_minutes", 0),
            "queue_length": live_metrics.get("queue_length", 0),
            "shop_id": shop_id
        }
    except Exception as e:
        return {"error": str(e)}


def close_queue(shop_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
    """Close the queue (Phase 2 placeholder with HITL approval)."""
    try:
        return {
            "message": f"Queue closed. Reason: {reason or 'Not specified'}",
            "shop_id": shop_id,
            "status": "closed",
            "requires_approval": True
        }
    except Exception as e:
        return {"error": str(e)}


def search_services(shop_id: int, query: Optional[str] = None) -> Dict[str, Any]:
    """Search available services."""
    try:
        services = db_interface.get_shop_services(shop_id, include_inactive=False)
        if query:
            query_lower = query.lower()
            services = [s for s in services if query_lower in s.get("name", "").lower()]
        return {
            "services": services or [],
            "shop_id": shop_id
        }
    except Exception as e:
        return {"error": str(e)}
