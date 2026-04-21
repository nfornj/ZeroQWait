from typing import Any, Dict, Optional

from db_interface import db_interface
from integrations.booking_mcp_client import BookingMCPClient


def _get_booking_client() -> BookingMCPClient:
    return BookingMCPClient()


def list_queue(shop_id: int) -> Dict[str, Any]:
    """Get active queue items for a shop through the booking MCP service."""
    result = _get_booking_client().list_queue(shop_id)
    if result.get("error"):
        return result
    return {
        "queue_items": list(result.get("items") or result.get("queue_items") or []),
        "live_metrics": result.get("live_metrics") or {},
        "shop_id": result.get("shop_id", shop_id),
        "queue_id": result.get("queue_id"),
        "total_in_queue": result.get("total_in_queue"),
        "waiting_count": result.get("waiting_count"),
        "serving_count": result.get("serving_count"),
        "next_customer": result.get("next_customer"),
    }


def join_queue(shop_id: int, customer_name: str, phone: Optional[str] = None) -> Dict[str, Any]:
    """Join a queue through the booking MCP service."""
    result = _get_booking_client().join_queue(shop_id, customer_name, phone)
    if result.get("error"):
        return result
    result.setdefault("shop_id", shop_id)
    return result


def call_next(shop_id: int, employee_id: Optional[int] = None) -> Dict[str, Any]:
    """Call the next customer through the booking MCP service."""
    result = _get_booking_client().call_next(shop_id, employee_id)
    if result.get("error"):
        return result
    if result.get("message"):
        result.setdefault("shop_id", shop_id)
        return result

    queue_item = result
    customer_name = queue_item.get("customer_name") or "customer"
    return {
        "message": f"Now serving {customer_name}",
        "queue_item": queue_item,
        "shop_id": shop_id,
        "status": queue_item.get("status") or "serving",
    }


def get_wait_time(shop_id: int, queue_item_id: Optional[int] = None) -> Dict[str, Any]:
    """Get wait time estimate through the booking MCP service."""
    result = _get_booking_client().get_wait_time(shop_id, queue_item_id)
    if result.get("error"):
        return result
    if queue_item_id is not None:
        result.setdefault("shop_id", shop_id)
        return result
    return {
        "estimated_wait_minutes": result.get("estimated_wait_minutes", 0),
        "queue_length": result.get("queue_length", 0),
        "shop_id": result.get("shop_id", shop_id),
    }


def close_queue(shop_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
    """Close the active queue for a shop after owner approval via booking MCP."""
    result = _get_booking_client().close_queue(shop_id, reason)
    if result.get("error"):
        return result
    success = bool(result.get("success", True))
    if not success:
        return {"error": result.get("error") or "Failed to close queue", "shop_id": shop_id}
    return {
        "message": f"Queue closed. Reason: {reason or result.get('reason') or 'Not specified'}",
        "shop_id": result.get("shop_id", shop_id),
        "status": "closed",
        "closed_queues": result.get("closed_queues", 1),
    }


def search_services(shop_id: int, query: Optional[str] = None) -> Dict[str, Any]:
    """Search available services through the booking MCP service."""
    result = _get_booking_client().search_services(shop_id, query)
    if result.get("error"):
        return result
    return {
        "services": list(result.get("services") or []),
        "shop_id": result.get("shop_id", shop_id),
        "count": result.get("count"),
    }


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
