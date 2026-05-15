"""
Tenant management API — provision schemas and manage shop runtime placement.

All endpoints require super_admin role.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from database import get_db
from shared.auth_utils import get_current_user
from modules.auth.models import User, UserRole, SubscriptionTier
from modules.shops.models import Shop
from redis_client import redis_client
import tenant_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["tenants"])


def _require_super_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Super admin access required")
    return current_user


# ── List shop isolation/runtime state ──────────────────────────────

@router.get("/", summary="List shop isolation and runtime assignments")
def list_tenants(
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
):
    return tenant_manager.list_shop_runtimes(db)


# ── Schema provisioning ────────────────────────────────────────────

@router.post("/schema/{shop_id}/ensure", summary="Ensure a shop has an isolated schema")
def ensure_schema(
    shop_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
):
    try:
        schema = tenant_manager.ensure_shop_schema(db, shop_id)
        return {"status": "schema_ready", "shop_id": shop_id, "schema": schema}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/schema/{shop_id}/backfill", summary="Copy public shop rows into the isolated schema")
def backfill_schema(
    shop_id: int,
    delete_public: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
):
    try:
        return tenant_manager.migrate_shop_to_schema(db, shop_id, delete_public=delete_public)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Runtime assignment ─────────────────────────────────────────────

@router.post("/runtime/dedicated/{shop_id}", summary="Assign a shop to dedicated backend/agent compute")
def assign_dedicated_runtime(
    shop_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
):
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    assignment = tenant_manager.assign_dedicated_runtime(db, shop_id)
    owner = db.query(User).filter(User.id == shop.owner_id).first()
    if owner:
        owner.subscription_tier = SubscriptionTier.PREMIUM
        db.commit()
    return {"status": "dedicated_runtime_assigned", **assignment}


@router.post("/runtime/shared/{shop_id}", summary="Assign a shop back to shared backend/agent compute")
def assign_shared_runtime(
    shop_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
):
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    assignment = tenant_manager.assign_shared_runtime(db, shop_id)
    owner = db.query(User).filter(User.id == shop.owner_id).first()
    if owner:
        owner.subscription_tier = SubscriptionTier.FREE
        db.commit()
    return {"status": "shared_runtime_assigned", **assignment}


# ── Compatibility endpoints ────────────────────────────────────────

@router.post("/upgrade/{shop_id}", summary="Compatibility: assign premium compute metadata")
def upgrade_shop(
    shop_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
):
    return assign_dedicated_runtime(shop_id, db, _)


# ── Downgrade a shop to free ───────────────────────────────────────

@router.post("/downgrade/{shop_id}", summary="Compatibility: assign shared compute metadata")
def downgrade_shop(
    shop_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
):
    return assign_shared_runtime(shop_id, db, _)


# ── Stats for a tenant ─────────────────────────────────────────────

@router.get("/stats/{shop_id}", summary="Get row counts for a shop's tenant tables")
def get_stats(
    shop_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
):
    try:
        db_stats = tenant_manager.get_tenant_stats(db, shop_id)
        redis_stats = redis_client.get_tenant_stats(shop_id)
        return {**db_stats, "redis": redis_stats}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/flush-cache/{shop_id}", summary="Flush all Redis cache for a tenant")
def flush_tenant_cache(
    shop_id: int,
    _: User = Depends(_require_super_admin),
):
    count = redis_client.tenant_flush(shop_id)
    return {"status": "flushed", "shop_id": shop_id, "keys_deleted": count}
