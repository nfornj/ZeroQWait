"""temporal_inventory_activities.py — Temporal activity for inventory low-stock checks.

Replaces the stub in appointment_workflows.py with a proper Odoo-aware implementation.
When the shop has an Odoo company_id, stock data is fetched from Odoo; otherwise
the local inventory DB is used as fallback.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from temporalio import activity

logger = logging.getLogger(__name__)

_LOW_STOCK_THRESHOLD = 5  # default threshold when using the Odoo path


@activity.defn
async def check_low_stock_activity(shop_id: int) -> Dict[str, Any]:
    """Return low-stock items for *shop_id*.

    Returns a dict:
      {
        "shop_id": <int>,
        "low_stock_items": [<item>, …],
        "count": <int>,
        "source": "odoo" | "local",
      }
    """
    from agents.tools.odoo_tools import _get_odoo_company_id
    from integrations.odoo_client import odoo_client
    from agents.tools.inventory_tools import get_low_stock_alerts

    try:
        company_id = _get_odoo_company_id(shop_id)

        if company_id and odoo_client.enabled:
            result = odoo_client.get_low_stock_items(company_id=company_id, threshold=_LOW_STOCK_THRESHOLD)
            if "error" not in result:
                items: List[Any] = result.get("items", [])
                return {
                    "shop_id": shop_id,
                    "low_stock_items": items,
                    "count": len(items),
                    "source": "odoo",
                }
            # Odoo call failed — fall through to local
            logger.warning(
                "check_low_stock_activity shop=%d odoo error=%s, falling back to local",
                shop_id, result.get("error"),
            )

        # Local DB fallback
        items = get_low_stock_alerts(shop_id)
        return {
            "shop_id": shop_id,
            "low_stock_items": items,
            "count": len(items),
            "source": "local",
        }

    except Exception as exc:
        logger.exception("check_low_stock_activity shop=%d unexpected error", shop_id)
        return {
            "shop_id": shop_id,
            "low_stock_items": [],
            "count": 0,
            "source": "error",
            "error": str(exc),
        }
