from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from typing import List
from supabase_client import supabase
from schemas import Shop, ShopCreate, ShopUpdate, ShopWithQueue
from auth_utils import get_current_user
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
        shops_response = supabase.table("shops").select("id").eq(
            "owner_id", current_user["id"]
        ).execute()
        user_shops_count = len(shops_response.data) if shops_response.data else 0
        
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
    try:
        existing_slug_response = supabase.table("shops").select("slug").eq("slug", base_slug).execute()
        if existing_slug_response.data:
            base_slug = f"{base_slug}-{random.randint(100, 999)}"
    except Exception:
        pass
    
    # Create shop
    shop_data = shop.dict()
    shop_data["owner_id"] = current_user["id"]
    shop_data["slug"] = base_slug
    shop_data["is_active"] = True
    
    try:
        shop_response = supabase.table("shops").insert(shop_data).execute()
        if not shop_response.data:
            raise HTTPException(status_code=500, detail="Failed to create shop")
        
        db_shop = shop_response.data[0]
        
        # Create an active queue for today
        queue_data = {
            "shop_id": db_shop["id"],
            "name": "Main Queue",
            "is_active": True
        }
        supabase.table("queues").insert(queue_data).execute()
        
        return db_shop
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create shop: {str(e)}")

@router.get("/", response_model=List[Shop])
def get_all_shops(
    skip: int = 0,
    limit: int = 100
):
    """Get all active shops"""
    try:
        response = supabase.table("shops").select("*").eq(
            "is_active", True
        ).range(skip, skip + limit - 1).execute()
        return response.data if response.data else []
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
        response = supabase.table("shops").select("*").eq(
            "owner_id", current_user["id"]
        ).execute()
        return response.data if response.data else []
    except Exception:
        return []

@router.get("/{shop_id}", response_model=ShopWithQueue)
def get_shop(shop_id: int):
    """Get shop details with active queue"""
    try:
        shop_response = supabase.table("shops").select("*").eq("id", shop_id).execute()
        if not shop_response.data:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        shop = shop_response.data[0]
        
        # Fetch queues with queue items
        queues_response = supabase.table("queues").select("*").eq(
            "shop_id", shop_id
        ).eq("is_active", True).execute()
        
        queues = []
        if queues_response.data:
            for queue in queues_response.data:
                # Fetch queue items for each queue
                items_response = supabase.table("queue_items").select("*").eq(
                    "queue_id", queue["id"]
                ).execute()
                queue["queue_items"] = items_response.data if items_response.data else []
                queues.append(queue)
        
        shop["queues"] = queues
        return shop
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch shop: {str(e)}")

@router.get("/s/{slug}", response_model=ShopWithQueue)
def get_shop_by_slug(slug: str):
    """Get shop details by slug (Public)"""
    try:
        shop_response = supabase.table("shops").select("*").eq("slug", slug).execute()
        if not shop_response.data:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        shop = shop_response.data[0]
        
        # Fetch queues with queue items
        queues_response = supabase.table("queues").select("*").eq(
            "shop_id", shop["id"]
        ).eq("is_active", True).execute()
        
        queues = []
        if queues_response.data:
            for queue in queues_response.data:
                # Fetch queue items for each queue
                items_response = supabase.table("queue_items").select("*").eq(
                    "queue_id", queue["id"]
                ).execute()
                queue["queue_items"] = items_response.data if items_response.data else []
                queues.append(queue)
        
        shop["queues"] = queues
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get logo: {str(e)}")
