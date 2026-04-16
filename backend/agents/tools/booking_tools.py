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
    """Join a queue — calls db_interface.join_queue_for_shop with row locking."""
    try:
        result = db_interface.join_queue_for_shop(shop_id, customer_name, phone)
        return result
    except Exception as e:
        return {"error": str(e)}


def call_next(shop_id: int, employee_id: Optional[int] = None) -> Dict[str, Any]:
    """Call next customer from queue — marks current waiting item as serving."""
    try:
        from modules.queues.models import Queue, QueueItem, QueueStatus
        from datetime import datetime

        session = db_interface.get_session()
        try:
            queue = session.query(Queue).filter(
                Queue.shop_id == shop_id,
                Queue.is_active == True
            ).first()
            if not queue:
                return {"error": "No active queue found", "shop_id": shop_id}

            next_item = session.query(QueueItem).filter(
                QueueItem.queue_id == queue.id,
                QueueItem.status == QueueStatus.WAITING,
            ).order_by(QueueItem.position).first()

            if not next_item:
                return {"message": "No customers waiting in queue", "shop_id": shop_id}

            next_item.status = QueueStatus.BEING_SERVED
            next_item.service_started_at = datetime.utcnow()
            if employee_id:
                next_item.assigned_employee_id = employee_id
            session.commit()
            session.refresh(next_item)

            return {
                "message": f"Now serving {next_item.customer_name or 'customer'}",
                "queue_item": db_interface._model_to_dict(next_item),
                "shop_id": shop_id,
                "status": "serving",
            }
        finally:
            session.close()
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
    """Close the active queue for a shop. This is a high-impact action requiring HITL approval."""
    try:
        from modules.queues.models import Queue

        session = db_interface.get_session()
        try:
            queue = session.query(Queue).filter(
                Queue.shop_id == shop_id,
                Queue.is_active == True
            ).first()
            if not queue:
                return {"error": "No active queue to close", "shop_id": shop_id}

            queue.is_active = False
            session.commit()

            return {
                "message": f"Queue closed. Reason: {reason or 'Not specified'}",
                "shop_id": shop_id,
                "status": "closed",
                "requires_approval": True,
            }
        finally:
            session.close()
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
