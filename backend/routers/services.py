from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from db_interface import db_interface
from schemas import ShopService, ShopServiceCreate, ShopServiceUpdate
from shared.auth_utils import get_current_user, get_current_user_optional
from permissions import check_shop_access
from redis_client import redis_client

router = APIRouter()

@router.post("/shops/{shop_id}/services", response_model=ShopService, status_code=status.HTTP_201_CREATED)
def create_service(
    shop_id: int,
    service: ShopServiceCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new service for a shop (Owner/Manager only).
    """
    # Verify access (Manager can add services? Plan said Owner, but Manager makes sense too)
    # Let's start with Owner for safety, or allow both. Plan didn't specify.
    check_shop_access(shop_id, current_user, require_owner=False) 
    
    try:
        service_data = service.dict()
        service_data["shop_id"] = shop_id
        
        new_service = db_interface.create_shop_service(service_data)
        if new_service:
            redis_client.tenant_delete(shop_id, "services")
            return new_service
        raise HTTPException(status_code=500, detail="Failed to create service")
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create service: {str(e)}"
        )

from shared.auth_utils import get_current_user, get_current_user_optional

@router.get("/shops/{shop_id}/services", response_model=List[ShopService])
def list_services(
    shop_id: int,
    include_inactive: bool = False,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    List services for a shop (Public).
    """
    # Public access allowed for listing services
    try:
        # If user is logged in, we could do extra checks, but for now just return active services for public
        # If internal/owner, maybe show inactive? 
        # The param include_inactive defaults to False.
        
        # If include_inactive is requested, enforce auth
        if include_inactive:
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required to view inactive services")
            check_shop_access(shop_id, current_user, require_owner=False)

        services = db_interface.get_shop_services(shop_id, include_inactive=include_inactive)
        # Cache active services for premium shops
        if not include_inactive:
            redis_client.set_services_cache(shop_id, [s.dict() if hasattr(s, 'dict') else s for s in services])
        return services
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list services: {str(e)}"
        )

@router.put("/shops/{shop_id}/services/{service_id}", response_model=ShopService)
def update_service(
    shop_id: int,
    service_id: int,
    service_update: ShopServiceUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update a service (Owner/Manager only).
    """
    check_shop_access(shop_id, current_user, require_owner=False)
    
    try:
        updated = db_interface.update_shop_service(shop_id, service_id, service_update.dict(exclude_unset=True))
        if updated:
            redis_client.tenant_delete(shop_id, "services")
            return updated
        raise HTTPException(status_code=404, detail="Service not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update service: {str(e)}"
        )

@router.delete("/shops/{shop_id}/services/{service_id}")
def delete_service(
    shop_id: int,
    service_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Soft delete a service.
    """
    check_shop_access(shop_id, current_user, require_owner=False)
    
    try:
        updated = db_interface.update_shop_service(shop_id, service_id, {"is_active": False})
        if updated:
            redis_client.tenant_delete(shop_id, "services")
            return {"message": "Service deleted successfully"}
        raise HTTPException(status_code=404, detail="Service not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete service: {str(e)}"
        )
