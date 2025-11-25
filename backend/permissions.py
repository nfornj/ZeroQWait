"""
Permission checking utilities for role-based access control.
"""
from fastapi import HTTPException, status
from supabase_client import supabase


def check_shop_access(shop_id: int, user: dict, require_owner: bool = False) -> bool:
    """
    Check if user has access to a shop.
    
    Args:
        shop_id: Shop to check access for
        user: Current user dict from auth
        require_owner: If True, only shop owner allowed. 
                      If False, owner OR active employee allowed.
    
    Returns:
        True if access granted
    
    Raises:
        HTTPException: 404 if shop not found, 403 if access denied
    """
    # Check if shop exists and get owner
    try:
        shop_response = supabase.table("shops").select("owner_id").eq("id", shop_id).execute()
        if not shop_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shop not found"
            )
        
        is_owner = shop_response.data[0]["owner_id"] == user["id"]
        
        # If owner-only access is required
        if require_owner:
            if not is_owner:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only shop owner can perform this action"
                )
            return True
        
        # Check if user is owner (always has access)
        if is_owner:
            return True
        
        # Check if user is an active employee
        if user.get("role") == "employee":
            employee_response = supabase.table("shop_employees").select("*").eq(
                "shop_id", shop_id
            ).eq("user_id", user["id"]).eq("is_active", True).execute()
            
            if employee_response.data:
                return True
        
        # No access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You must be the shop owner or an active employee."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking shop access: {str(e)}"
        )


def is_shop_owner(shop_id: int, user_id: int) -> bool:
    """
    Check if user is the owner of a shop.
    
    Args:
        shop_id: Shop ID to check
        user_id: User ID to check
    
    Returns:
        True if user owns the shop, False otherwise
    """
    try:
        shop_response = supabase.table("shops").select("owner_id").eq("id", shop_id).execute()
        if not shop_response.data:
            return False
        return shop_response.data[0]["owner_id"] == user_id
    except Exception:
        return False


def get_employee_shops(user_id: int) -> list:
    """
    Get list of shops where user is an active employee.
    
    Args:
        user_id: User ID to check
    
    Returns:
        List of shop IDs where user is an active employee
    """
    try:
        response = supabase.table("shop_employees").select("shop_id").eq(
            "user_id", user_id
        ).eq("is_active", True).execute()
        
        if response.data:
            return [emp["shop_id"] for emp in response.data]
        return []
    except Exception:
        return []
