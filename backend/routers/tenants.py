"""
Tenant management API — provision, migrate, and monitor per-shop schemas.

All endpoints require super_admin role.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
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


# ── List tenant schemas ─────────────────────────────────────────────

@router.get("/", summary="List all premium tenants")
def list_tenants(
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
):
    return tenant_manager.list_tenant_schemas(db)


# ── Upgrade a shop to premium ──────────────────────────────────────

@router.post("/upgrade/{shop_id}", summary="Upgrade shop to premium (isolated schema)")
def upgrade_shop(
    shop_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
):
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    if shop.tenant_schema:
        raise HTTPException(status_code=409, detail=f"Shop already has schema: {shop.tenant_schema}")

    schema = tenant_manager.migrate_to_premium(db, shop_id)

    # Also update the owner's subscription tier
    owner = db.query(User).filter(User.id == shop.owner_id).first()
    if owner:
        owner.subscription_tier = SubscriptionTier.PREMIUM
        db.commit()

    return {
        "status": "upgraded",
        "shop_id": shop_id,
        "shop_name": shop.name,
        "schema": schema,
    }


# ── Downgrade a shop to free ───────────────────────────────────────

@router.post("/downgrade/{shop_id}", summary="Downgrade shop to free (shared schema)")
def downgrade_shop(
    shop_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
):
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    if not shop.tenant_schema:
        raise HTTPException(status_code=409, detail="Shop is already on free tier")

    tenant_manager.migrate_to_free(db, shop_id)

    # Also update the owner's subscription tier
    owner = db.query(User).filter(User.id == shop.owner_id).first()
    if owner:
        owner.subscription_tier = SubscriptionTier.FREE
        db.commit()

    return {
        "status": "downgraded",
        "shop_id": shop_id,
        "shop_name": shop.name,
    }


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
