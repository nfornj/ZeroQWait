import logging

from db_interface import db_interface


logger = logging.getLogger(__name__)


def sync_service_to_odoo(shop_id: int, service_data: dict, action: str = "create") -> None:
    """Best-effort Odoo product sync for shop services."""
    try:
        from integrations.odoo_client import OdooClient
        from modules.shops.models import Shop

        odoo = OdooClient()
        if not odoo.enabled:
            return

        session = db_interface.get_session()
        try:
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
            logger.info(
                "Service %s updated for shop %s — Odoo update sync pending product ID mapping",
                service_data.get("id"),
                shop_id,
            )
    except Exception as exc:
        logger.warning("Odoo product sync failed (non-blocking): %s", exc)