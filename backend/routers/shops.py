from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from typing import List, Optional
from db_interface import db_interface
from schemas import Shop, ShopCreate, ShopUpdate, ShopWithQueue
from auth_utils import get_current_user, get_current_user_optional
from permissions import sanitize_queue_data_for_public
from datetime import datetime
import random

router = APIRouter()

@router.post("/", response_model=Shop)
def create_shop(
    shop: ShopCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new shop (Shop Owner only)"""
    if current_user.get("role") != "shop_owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only shop owners can create shops"
        )
    
    # Check shop limit based on subscription tier
    try:
        from tier_limits import TIER_LIMITS
        user_shops = db_interface.get_shops({"owner_id": current_user["id"]})
        user_shops_count = len(user_shops)
        
        tier_limit = TIER_LIMITS.get(current_user.get("subscription_tier", "free"), {}).get("max_shops")
        if tier_limit is not None and user_shops_count >= tier_limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Shop limit reached for {current_user.get('subscription_tier', 'free')} tier. Current limit: {tier_limit} shops. Upgrade to Premium for unlimited shops."
            )
    except ImportError:
        # If tier_limits doesn't exist, skip the check
        pass
    except HTTPException:
        raise
    except Exception:
        pass
    
    # Generate slug from name
    base_slug = shop.name.lower().replace(" ", "-").replace("'", "").replace(".", "")
    # Ensure uniqueness (simple check)
    existing_shop = db_interface.get_shop_by_slug(base_slug)
    if existing_shop:
        base_slug = f"{base_slug}-{random.randint(100, 999)}"
    
    # Create shop
    shop_data = shop.dict()
    shop_data["owner_id"] = current_user["id"]
    shop_data["slug"] = base_slug
    shop_data["is_active"] = True
    
    try:
        db_shop = db_interface.create_shop(shop_data)
        if not db_shop:
            raise HTTPException(status_code=500, detail="Failed to create shop")
        
        # Create an active queue for today
        queue_data = {
            "shop_id": db_shop["id"],
            "name": "Main Queue",
            "is_active": True
        }
        db_interface.create_queue(queue_data)
        
        return db_shop
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create shop: {str(e)}")

@router.get("/", response_model=List[Shop])
def get_all_shops(
    skip: int = 0,
    limit: int = 100,
    country: Optional[str] = None
):
    """Get all active shops, optionally filtered by country"""
    try:
        filters = {"is_active": True}
        if country:
            filters["country"] = country
        
        shops = db_interface.get_shops(filters=filters, skip=skip, limit=limit)
        return shops
    except Exception:
        return []

@router.get("/countries")
def get_countries():
    """Get list of unique countries from active shops"""
    try:
        shops = db_interface.get_shops(filters={"is_active": True}, limit=1000)
        if shops:
            countries = list(set([shop["country"] for shop in shops if shop.get("country")]))
            return sorted(countries)
        return []
    except Exception:
        return []

@router.get("/my-shops", response_model=List[Shop])
def get_my_shops(
    current_user: dict = Depends(get_current_user)
):
    """Get shops owned by current user"""
    if current_user.get("role") != "shop_owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only shop owners can view their shops"
        )
    try:
        shops = db_interface.get_shops(filters={"owner_id": current_user["id"]})
        return shops
    except Exception:
        return []

@router.get("/{shop_id}", response_model=ShopWithQueue)
def get_shop(shop_id: int, current_user: Optional[dict] = Depends(get_current_user_optional)):
    """Get shop details with active queue (Public endpoint - sanitizes employee data for non-staff)"""
    try:
        shop = db_interface.get_shop_by_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        # Fetch queues with queue items
        queues = db_interface.get_queues(filters={"shop_id": shop_id, "is_active": True})
        
        for queue in queues:
            # Fetch queue items for each queue
            queue_items = db_interface.get_queue_items(filters={"queue_id": queue["id"]})
            queue["queue_items"] = queue_items
            
            # Sanitize employee data for public access
            queue = sanitize_queue_data_for_public(queue, current_user, shop_id)
        
        shop["queues"] = queues
        return shop
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch shop: {str(e)}")

@router.get("/s/{slug}", response_model=ShopWithQueue)
def get_shop_by_slug(slug: str, current_user: Optional[dict] = Depends(get_current_user_optional)):
    """Get shop details by slug (Public endpoint - sanitizes employee data for non-staff)"""
    try:
        shop = db_interface.get_shop_by_slug(slug)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        shop_id = shop["id"]
        
        # Fetch queues with queue items
        queues = db_interface.get_queues(filters={"shop_id": shop_id, "is_active": True})
        
        for queue in queues:
            # Fetch queue items for each queue
            queue_items = db_interface.get_queue_items(filters={"queue_id": queue["id"]})
            queue["queue_items"] = queue_items
            
            # Sanitize employee data for public access
            queue = sanitize_queue_data_for_public(queue, current_user, shop_id)
        
        shop["queues"] = queues
        return shop
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch shop: {str(e)}")

@router.get("/by-slug/{slug}", response_model=Shop)
def get_shop_by_slug_info(slug: str):
    """Get shop info by slug (Public endpoint - returns basic shop info)"""
    try:
        shop = db_interface.get_shop_by_slug(slug)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        return shop
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch shop: {str(e)}")

@router.put("/{shop_id}", response_model=Shop)
def update_shop(
    shop_id: int,
    shop_update: ShopUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update shop details (Owner only)"""
    try:
        shop_response = supabase.table("shops").select("*").eq("id", shop_id).execute()
        if not shop_response.data:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        db_shop = shop_response.data[0]
        
        if db_shop["owner_id"] != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this shop"
            )
        
        # Only update fields that were provided (not None)
        update_data = shop_update.dict(exclude_unset=True)
        if not update_data:
            return db_shop
        
        response = supabase.table("shops").update(update_data).eq("id", shop_id).execute()
        if response.data:
            return response.data[0]
        return db_shop
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update shop: {str(e)}")

@router.delete("/{shop_id}")
def delete_shop(
    shop_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Deactivate a shop (Owner only)"""
    try:
        shop_response = supabase.table("shops").select("*").eq("id", shop_id).execute()
        if not shop_response.data:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        db_shop = shop_response.data[0]
        
        if db_shop["owner_id"] != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this shop"
            )
        
        supabase.table("shops").update({"is_active": False}).eq("id", shop_id).execute()
        return {"message": "Shop deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete shop: {str(e)}")

@router.put("/{shop_id}/logo")
async def upload_shop_logo(
    shop_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload and store a shop logo using Supabase Storage (Owner only)."""
    try:
        shop_response = supabase.table("shops").select("*").eq("id", shop_id).execute()
        if not shop_response.data:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        db_shop = shop_response.data[0]
        
        if db_shop["owner_id"] != current_user["id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this shop")
        
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large (max 5MB)")
        
        # Upload to Supabase Storage
        file_path = f"shop-logos/{shop_id}/{file.filename}"
        try:
            supabase.storage.from_("shop-logos").upload(
                file_path,
                content,
                file_options={"content-type": file.content_type}
            )
            
            # Get public URL
            public_url = supabase.storage.from_("shop-logos").get_public_url(file_path)
            
            # Update shop with logo URL
            supabase.table("shops").update({
                "logo_url": public_url,
                "logo_mime_type": file.content_type
            }).eq("id", shop_id).execute()
            
            return {"message": "Logo uploaded", "logo_url": public_url}
        except Exception as storage_error:
            # Fallback: store in database as BLOB
            supabase.table("shops").update({
                "logo_data": content,
                "logo_mime_type": file.content_type
            }).eq("id", shop_id).execute()
            return {"message": "Logo uploaded (stored in database)"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload logo: {str(e)}")

@router.get("/{shop_id}/logo")
def get_shop_logo(shop_id: int):
    """Return the shop logo - either from URL or database BLOB."""
    try:
        shop_response = supabase.table("shops").select("logo_url, logo_data, logo_mime_type").eq("id", shop_id).execute()
        if not shop_response.data:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        db_shop = shop_response.data[0]
        
        # If logo_url exists, redirect to it
        if db_shop.get("logo_url"):
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=db_shop["logo_url"])
        
        # Otherwise, return BLOB data if available
        if not db_shop.get("logo_data"):
            raise HTTPException(status_code=404, detail="Logo not set")
        
        return Response(
            content=db_shop["logo_data"],
            media_type=db_shop.get("logo_mime_type") or "image/png"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get logo: {str(e)}")

# Close Days Management

@router.get("/{shop_id}/close-days")
def get_close_days(
    shop_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get all future close days for a shop"""
    try:
        shop = db_interface.get_shop_by_id(shop_id)
        if not shop or shop["owner_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        db = db_interface.get_session()
        try:
            from models import ShopCloseDay
            from datetime import date
            
            close_days = db.query(ShopCloseDay).filter(
                ShopCloseDay.shop_id == shop_id,
                ShopCloseDay.date >= date.today()
            ).order_by(ShopCloseDay.date).all()
            
            return [db_interface._model_to_dict(day) for day in close_days]
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{shop_id}/close-days")
def add_close_day(
    shop_id: int,
    date_str: str, # Format YYYY-MM-DD
    reason: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Add a close day"""
    try:
        shop = db_interface.get_shop_by_id(shop_id)
        if not shop or shop["owner_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        db = db_interface.get_session()
        try:
            from models import ShopCloseDay
            from datetime import datetime
            
            close_date = datetime.strptime(date_str, "%Y-%m-%d")
            
            # Check existing
            existing = db.query(ShopCloseDay).filter(
                ShopCloseDay.shop_id == shop_id,
                ShopCloseDay.date == close_date
            ).first()
            
            if existing:
                return db_interface._model_to_dict(existing)
                
            new_day = ShopCloseDay(
                shop_id=shop_id,
                date=close_date,
                reason=reason
            )
            db.add(new_day)
            db.commit()
            db.refresh(new_day)
            return db_interface._model_to_dict(new_day)
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{shop_id}/close-days/{day_id}")
def delete_close_day(
    shop_id: int,
    day_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a close day"""
    try:
        shop = db_interface.get_shop_by_id(shop_id)
        if not shop or shop["owner_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        db = db_interface.get_session()
        try:
            from models import ShopCloseDay
            
            day = db.query(ShopCloseDay).filter(
                ShopCloseDay.id == day_id,
                ShopCloseDay.shop_id == shop_id
            ).first()
            
            if day:
                db.delete(day)
                db.commit()
            return {"success": True}
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
