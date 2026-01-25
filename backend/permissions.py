"""
Permission checking utilities for role-based access control.
"""
from fastapi import HTTPException, status
from db_interface import db_interface


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
        shop = db_interface.get_shop_by_id(shop_id)
        if not shop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shop not found"
            )
        
        is_owner = shop["owner_id"] == user["id"]
        
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
        
        # Check if user is an active employee or manager
        if user.get("role") in ["employee", "manager"]:
            employee = db_interface.get_shop_employee(shop_id, user["id"])
            
            if employee and employee.get("is_active"):
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
        shop = db_interface.get_shop_by_id(shop_id)
        if not shop:
            return False
        return shop["owner_id"] == user_id
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
        return db_interface.get_employee_shops(user_id)
    except Exception:
        return []


def verify_queue_item_access(queue_item_id: int, user: dict, require_owner: bool = False) -> dict:
    """
    Verify user has access to a queue item by checking shop ownership/employee status.
    
    This helper traces the access chain: queue_item → queue → shop → owner/employee check.
    
    Args:
        queue_item_id: Queue item ID to check access for
        user: Current user dict from auth
        require_owner: If True, only shop owner allowed.
                      If False, owner OR active employee allowed.
    
    Returns:
        dict: Queue item data with queue and shop information if access granted
    
    Raises:
        HTTPException: 404 if not found, 403 if access denied
    """
    try:
        # Fetch queue item
        try:
           # Assuming db_interface has get_queue_item_by_id? No, use filters
           items = db_interface.get_queue_items(filters={"id": queue_item_id})
           if not items:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Queue item not found"
                )
           queue_item = items[0]
        except Exception: 
            # Fallback if get_queue_items is list based
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Queue item not found"
            )

        queue_id = queue_item["queue_id"]
        
        # Fetch queue to get shop_id
        queue = db_interface.get_queue_by_id(queue_id)
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Queue not found"
            )
        
        shop_id = queue["shop_id"]
        
        # Verify user has access to this shop
        check_shop_access(shop_id, user, require_owner)
        
        # Return enriched data for convenience
        return {
            "queue_item": queue_item,
            "queue": queue,
            "shop_id": shop_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying queue item access: {str(e)}"
        )


def sanitize_queue_data_for_public(queue_data: dict, user: dict = None, shop_id: int = None) -> dict:
    """
    Sanitize queue data by removing sensitive employee information for public access.
    
    Only authenticated shop owners and employees should see employee details like:
    - Employee names
    - Employee profile photos
    - Employee assignment information
    
    Args:
        queue_data: Queue dict with queue_items list
        user: Current authenticated user (None if unauthenticated)
        shop_id: Shop ID to check if user has staff access
    
    Returns:
        dict: Sanitized queue data safe for public viewing
    """
    # Check if user is authenticated staff member
    is_staff = False
    if user and shop_id:
        try:
            # Check if user is owner or active employee
            check_shop_access(shop_id, user, require_owner=False)
            is_staff = True
        except HTTPException:
            is_staff = False
    
    # If staff member, return full data
    if is_staff:
        return queue_data
    
    # For public users, sanitize employee data
    sanitized = queue_data.copy()
    
    if "queue_items" in sanitized:
        sanitized_items = []
        for item in sanitized["queue_items"]:
            sanitized_item = item.copy()
            # Remove employee assignment details
            if "assigned_employee" in sanitized_item:
                del sanitized_item["assigned_employee"]
            if "assigned_employee_id" in sanitized_item:
                sanitized_item["assigned_employee_id"] = None
            sanitized_items.append(sanitized_item)
        sanitized["queue_items"] = sanitized_items
    
    return sanitized
