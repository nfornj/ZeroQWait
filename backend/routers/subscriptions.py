from fastapi import APIRouter, Depends, HTTPException
from db_interface import db_interface
from shared.auth_utils import get_current_user

from tier_limits import TIER_LIMITS
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional

router = APIRouter()

class SubscriptionResponse(BaseModel):
    tier: str
    started_at: Optional[datetime]
    expires_at: Optional[datetime]
    limits: dict
    
    class Config:
        from_attributes = True

@router.get("/me", response_model=SubscriptionResponse)
def get_my_subscription(
    current_user: dict = Depends(get_current_user),
):
    """Get current user's subscription details and limits"""
    tier = current_user.get("subscription_tier", "free")
    return {
        "tier": tier,
        "started_at": current_user.get("subscription_started_at"),
        "expires_at": current_user.get("subscription_expires_at"),
        "limits": TIER_LIMITS.get(tier, TIER_LIMITS.get("free", {})),
    }

@router.post("/upgrade")
def upgrade_subscription(
    tier: str,
    current_user: dict = Depends(get_current_user),
):
    """Upgrade user to a different tier (Stripe placeholder for now)"""
    if current_user.get("role") != "shop_owner":
        raise HTTPException(
            status_code=403,
            detail="Only shop owners can upgrade subscriptions"
        )
    
    # TODO: Integrate with Stripe for actual payment processing
    update_data = {
        "subscription_tier": tier,
        "subscription_started_at": datetime.utcnow().isoformat()
    }
    
    # Set expiration to 1 month from now for paid tiers
    if tier != "free":
        update_data["subscription_expires_at"] = (datetime.utcnow() + timedelta(days=30)).isoformat()
    else:
        update_data["subscription_expires_at"] = None
    
    try:
        updated_user = db_interface.update_user(current_user["id"], update_data)
        if updated_user:
            return {
                "message": f"Successfully upgraded to {tier} tier",
                "tier": tier,
                "expires_at": updated_user.get("subscription_expires_at"),
            }
        raise HTTPException(status_code=500, detail="Failed to upgrade subscription")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upgrade subscription: {str(e)}")
