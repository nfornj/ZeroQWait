"""
Platform provisioner API — schema isolation + premium runtime assignment.

Endpoints:
  POST /api/platform/shops/{shop_id}/provision-schema
    → ensure_shop_schema: creates tenant_<id> schema and replicates table structure
  POST /api/platform/shops/{shop_id}/provision-premium
    → assign_dedicated_runtime: marks shop for dedicated backend + worker
  GET  /api/platform/shops/{shop_id}/runtime
    → returns current runtime assignment for a shop
  POST /api/platform/shops/{shop_id}/revert-shared
    → assign_shared_runtime: moves shop back to shared compute

All endpoints require super_admin role.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from database import SessionLocal
from shared.auth_utils import get_current_user
from tenant_manager import (
    ensure_shop_schema,
    assign_dedicated_runtime,
    assign_shared_runtime,
    tenant_schema_exists,
    _get_shop_metadata,
    resolve_shop_schema_from_metadata,
)
from sqlalchemy import text

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_super_admin(current_user=Depends(get_current_user)):
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="super_admin role required",
        )
    return current_user


@router.post("/platform/shops/{shop_id}/provision-schema")
def provision_schema(
    shop_id: int,
    _: object = Depends(_require_super_admin),
):
    """
    Provision an isolated PostgreSQL schema for a shop.
    Creates tenant_<shop_id> schema and replicates all tenant table structures.
    Idempotent — safe to call multiple times.
    """
    db = SessionLocal()
    try:
        schema = ensure_shop_schema(db, shop_id)
        return {
            "shop_id": shop_id,
            "schema": schema,
            "status": "provisioned",
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Schema provisioning failed for shop %s: %s", shop_id, exc)
        raise HTTPException(status_code=500, detail=f"Provisioning failed: {exc}")
    finally:
        db.close()


@router.post("/platform/shops/{shop_id}/provision-premium")
def provision_premium(
    shop_id: int,
    _: object = Depends(_require_super_admin),
):
    """
    Assign a shop to dedicated backend + temporal-worker compute (premium tier).
    Also ensures a tenant schema exists.
    Returns the runtime assignment details.
    """
    db = SessionLocal()
    try:
        result = assign_dedicated_runtime(db, shop_id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Premium provisioning failed for shop %s: %s", shop_id, exc)
        raise HTTPException(status_code=500, detail=f"Provisioning failed: {exc}")
    finally:
        db.close()


@router.get("/platform/shops/{shop_id}/runtime")
def get_runtime(
    shop_id: int,
    _: object = Depends(_require_super_admin),
):
    """Return the current runtime assignment for a shop."""
    db = SessionLocal()
    try:
        shop = _get_shop_metadata(db, shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail=f"Shop {shop_id} not found")

        row = db.execute(text(
            "SELECT * FROM platform.shop_runtime_assignments WHERE shop_id = :sid"
        ), {"sid": shop_id}).mappings().first()

        schema = resolve_shop_schema_from_metadata(shop)
        return {
            "shop_id": shop_id,
            "data_isolation_mode": shop.get("data_isolation_mode", "shared_public"),
            "compute_mode": shop.get("compute_mode", "shared_instance"),
            "tenant_schema": schema,
            "schema_exists": tenant_schema_exists(db, shop_id) if schema else False,
            "runtime_assignment": dict(row) if row else None,
        }
    finally:
        db.close()


@router.post("/platform/shops/{shop_id}/revert-shared")
def revert_to_shared(
    shop_id: int,
    _: object = Depends(_require_super_admin),
):
    """Revert a premium shop back to shared compute (does not touch schema)."""
    db = SessionLocal()
    try:
        result = assign_shared_runtime(db, shop_id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Revert-to-shared failed for shop %s: %s", shop_id, exc)
        raise HTTPException(status_code=500, detail=f"Revert failed: {exc}")
    finally:
        db.close()
