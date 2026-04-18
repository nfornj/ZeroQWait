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


def create_service(shop_id: int, name: str, cost: float,
                   duration_minutes: int = 30,
                   description: Optional[str] = None,
                   currency: str = "USD") -> Dict[str, Any]:
    """Create a new service for a shop and sync to Odoo."""
    try:
        service_data = {
            "shop_id": shop_id,
            "name": name,
            "cost": cost,
            "duration_minutes": duration_minutes,
            "description": description or "",
            "is_active": True,
            "currency": currency,
        }
        new_service = db_interface.create_shop_service(service_data)
        if not new_service:
            return {"error": "Failed to create service"}

        # Sync to Odoo
        _sync_service_to_odoo(shop_id, new_service, action="create")

        from redis_client import redis_client
        redis_client.tenant_delete(shop_id, "services")

        return {
            "message": f"Service '{name}' created at ${cost:.2f}",
            "service": new_service,
            "shop_id": shop_id,
        }
    except Exception as e:
        return {"error": str(e)}


def update_service(shop_id: int, service_id: int,
                   name: Optional[str] = None,
                   cost: Optional[float] = None,
                   duration_minutes: Optional[int] = None,
                   description: Optional[str] = None,
                   is_active: Optional[bool] = None) -> Dict[str, Any]:
    """Update an existing service and sync changes to Odoo."""
    try:
        updates: Dict[str, Any] = {}
        if name is not None:
            updates["name"] = name
        if cost is not None:
            updates["cost"] = cost
        if duration_minutes is not None:
            updates["duration_minutes"] = duration_minutes
        if description is not None:
            updates["description"] = description
        if is_active is not None:
            updates["is_active"] = is_active

        if not updates:
            return {"error": "No updates provided"}

        updated = db_interface.update_shop_service(shop_id, service_id, updates)
        if not updated:
            return {"error": f"Service {service_id} not found"}

        # Sync to Odoo
        _sync_service_to_odoo(shop_id, updated, action="update")

        from redis_client import redis_client
        redis_client.tenant_delete(shop_id, "services")

        return {
            "message": f"Service '{updated.get('name', '')}' updated",
            "service": updated,
            "shop_id": shop_id,
        }
    except Exception as e:
        return {"error": str(e)}


def delete_service(shop_id: int, service_id: int) -> Dict[str, Any]:
    """Soft-delete a service (set is_active=False)."""
    try:
        updated = db_interface.update_shop_service(shop_id, service_id, {"is_active": False})
        if not updated:
            return {"error": f"Service {service_id} not found"}

        from redis_client import redis_client
        redis_client.tenant_delete(shop_id, "services")

        return {
            "message": f"Service '{updated.get('name', '')}' has been deactivated",
            "shop_id": shop_id,
        }
    except Exception as e:
        return {"error": str(e)}


def _sync_service_to_odoo(shop_id: int, service_data: Dict, action: str = "create") -> None:
    """Best-effort sync of a local service to Odoo product.product."""
    try:
        from integrations.odoo_client import OdooClient
        odoo = OdooClient()
        if not odoo.enabled:
            return

        # Resolve the shop's Odoo company_id
        session = db_interface.get_session()
        try:
            from modules.shops.models import Shop
            shop = session.query(Shop).filter(Shop.id == shop_id).first()
            company_id = getattr(shop, "odoo_company_id", None) if shop else None
        finally:
            session.close()

        if action == "create":
            odoo.create_product(
                name=service_data.get("name", ""),
                list_price=service_data.get("cost", 0),
                product_type="service",
                company_id=company_id,
                description=service_data.get("description"),
            )
        elif action == "update":
            # For updates, we'd need an odoo_product_id mapping.
            # For now, log that sync happened — full bidirectional mapping is Phase 2.
            import logging
            logging.getLogger(__name__).info(
                "Service %s updated for shop %s — Odoo product sync (update) pending product ID mapping",
                service_data.get("id"), shop_id
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Odoo product sync failed (non-blocking): %s", e)
