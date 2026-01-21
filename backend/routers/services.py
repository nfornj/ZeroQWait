from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from db_interface import db_interface
from schemas import ShopService, ShopServiceCreate, ShopServiceUpdate
from auth_utils import get_current_user
from permissions import check_shop_access

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
            return new_service
        raise HTTPException(status_code=500, detail="Failed to create service")
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create service: {str(e)}"
        )

@router.get("/shops/{shop_id}/services", response_model=List[ShopService])
def list_services(
    shop_id: int,
    include_inactive: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """
    List services for a shop.
    """
    # Allow read access to anyone logged in? No, should check shop access.
    # Actually, queue creation needs to see services. 
    # If this is public for the Queue View, we might need a public endpoint too.
    # For now, this is the internal management endpoint.
    check_shop_access(shop_id, current_user, require_owner=False)

    try:
        services = db_interface.get_shop_services(shop_id, include_inactive=include_inactive)
        return services
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
            return {"message": "Service deleted successfully"}
        raise HTTPException(status_code=404, detail="Service not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete service: {str(e)}"
        )
