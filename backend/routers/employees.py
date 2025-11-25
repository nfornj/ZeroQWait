from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import List, Optional
from supabase_client import supabase
from schemas import EmployeeCreate, ShopEmployee, User
from auth_utils import get_password_hash, get_current_user
from permissions import check_shop_access, get_employee_shops
from datetime import datetime

router = APIRouter()

@router.post("/shops/{shop_id}/employees", response_model=User, status_code=status.HTTP_201_CREATED)
def add_employee(
    shop_id: int,
    employee: EmployeeCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Add a new employee to a shop (Shop owner only).
    Creates a new user account with employee role and links them to the shop.
    """
    # Verify user is shop owner
    check_shop_access(shop_id, current_user, require_owner=True)
    
    # Check if username already exists
    try:
        username_check = supabase.table("users").select("id").eq("username", employee.username).execute()
        if username_check.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    except HTTPException:
        raise
    except Exception:
        pass
    
    # Check if email already exists
    try:
        email_check = supabase.table("users").select("id").eq("email", employee.email).execute()
        if email_check.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    except HTTPException:
        raise
    except Exception:
        pass
    
    # Create user with employee role
    hashed_password = get_password_hash(employee.password)
    user_data = {
        "email": employee.email,
        "username": employee.username,
        "hashed_password": hashed_password,
        "role": "employee",
        "is_active": True
    }
    
    try:
        user_response = supabase.table("users").insert(user_data).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create employee account"
            )
        
        new_user = user_response.data[0]
        
        # Link employee to shop
        shop_employee_data = {
            "shop_id": shop_id,
            "user_id": new_user["id"],
            "created_by": current_user["id"],
            "is_active": True
        }
        
        link_response = supabase.table("shop_employees").insert(shop_employee_data).execute()
        if not link_response.data:
            # Rollback user creation if linking fails
            supabase.table("users").delete().eq("id", new_user["id"]).execute()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to link employee to shop"
            )
        
        return new_user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add employee: {str(e)}"
        )


@router.get("/shops/{shop_id}/employees", response_model=List[dict])
def list_employees(
    shop_id: int,
    include_inactive: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """
    List all employees for a shop (Shop owner only).
    Returns employees with their user details and active status.
    """
    # Verify user is shop owner
    check_shop_access(shop_id, current_user, require_owner=True)
    
    try:
        # Get shop employees
        query = supabase.table("shop_employees").select("*").eq("shop_id", shop_id)
        
        if not include_inactive:
            query = query.eq("is_active", True)
        
        employees_response = query.execute()
        
        if not employees_response.data:
            return []
        
        # Fetch user details for each employee
        result = []
        for emp in employees_response.data:
            user_response = supabase.table("users").select(
                "id, username, email, role, is_active"
            ).eq("id", emp["user_id"]).execute()
            
            if user_response.data:
                user = user_response.data[0]
                result.append({
                    "employee_link_id": emp["id"],
                    "shop_id": emp["shop_id"],
                    "created_at": emp["created_at"],
                    "is_active": emp["is_active"],
                    "user": user
                })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list employees: {str(e)}"
        )


@router.delete("/shops/{shop_id}/employees/{employee_id}", status_code=status.HTTP_200_OK)
def remove_employee(
    shop_id: int,
    employee_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Remove an employee from a shop (Shop owner only).
    Performs soft delete by setting is_active=False.
    Does not delete the user account.
    """
    # Verify user is shop owner
    check_shop_access(shop_id, current_user, require_owner=True)
    
    try:
        # Find the shop_employee link
        link_response = supabase.table("shop_employees").select("*").eq(
            "shop_id", shop_id
        ).eq("user_id", employee_id).execute()
        
        if not link_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found for this shop"
            )
        
        # Soft delete: set is_active to False
        update_response = supabase.table("shop_employees").update(
            {"is_active": False}
        ).eq("shop_id", shop_id).eq("user_id", employee_id).execute()
        
        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove employee"
            )
        
        return {"message": "Employee removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove employee: {str(e)}"
        )


@router.put("/shops/{shop_id}/employees/{employee_id}/reactivate", status_code=status.HTTP_200_OK)
def reactivate_employee(
    shop_id: int,
    employee_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Reactivate a previously removed employee (Shop owner only).
    Sets is_active=True.
    """
    # Verify user is shop owner
    check_shop_access(shop_id, current_user, require_owner=True)
    
    try:
        # Find the shop_employee link
        link_response = supabase.table("shop_employees").select("*").eq(
            "shop_id", shop_id
        ).eq("user_id", employee_id).execute()
        
        if not link_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found for this shop"
            )
        
        # Reactivate: set is_active to True
        update_response = supabase.table("shop_employees").update(
            {"is_active": True}
        ).eq("shop_id", shop_id).eq("user_id", employee_id).execute()
        
        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reactivate employee"
            )
        
        return {"message": "Employee reactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reactivate employee: {str(e)}"
        )


@router.get("/check-username/{username}", response_model=dict)
def check_username_availability(username: str):
    """
    Check if a username is available (public endpoint).
    Returns {"available": true/false}
    """
    try:
        username_check = supabase.table("users").select("id").eq("username", username).execute()
        return {"available": len(username_check.data) == 0}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check username: {str(e)}"
        )


@router.get("/check-email/{email}", response_model=dict)
def check_email_availability(email: str):
    """
    Check if an email is available (public endpoint).
    Returns {"available": true/false}
    """
    try:
        email_check = supabase.table("users").select("id").eq("email", email).execute()
        return {"available": len(email_check.data) == 0}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check email: {str(e)}"
        )


@router.post("/clock-in/{shop_id}")
def clock_in(
    shop_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Clock in for a shift at a shop (Employee only).
    """
    if current_user.get("role") != "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for employees only"
        )
    
    # Check if employee is assigned to this shop
    check_shop_access(shop_id, current_user, require_owner=False)
    
    try:
        # Check if already clocked in
        active_shift = supabase.table("employee_shifts").select("*").eq(
            "user_id", current_user["id"]
        ).is_("clock_out", "null").execute()
        
        if active_shift.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already clocked in. Please clock out first."
            )
        
        # Create new shift
        shift_data = {
            "user_id": current_user["id"],
            "shop_id": shop_id,
            "clock_in": datetime.utcnow().isoformat()
        }
        
        response = supabase.table("employee_shifts").insert(shift_data).execute()
        if response.data:
            return {"message": "Clocked in successfully", "shift": response.data[0]}
        raise HTTPException(status_code=500, detail="Failed to clock in")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clock in: {str(e)}"
        )


@router.post("/clock-out")
def clock_out(current_user: dict = Depends(get_current_user)):
    """
    Clock out from current shift (Employee only).
    """
    if current_user.get("role") != "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for employees only"
        )
    
    try:
        # Find active shift
        active_shift = supabase.table("employee_shifts").select("*").eq(
            "user_id", current_user["id"]
        ).is_("clock_out", "null").execute()
        
        if not active_shift.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are not currently clocked in"
            )
        
        shift = active_shift.data[0]
        
        # Update shift with clock out time
        update_response = supabase.table("employee_shifts").update(
            {"clock_out": datetime.utcnow().isoformat()}
        ).eq("id", shift["id"]).execute()
        
        if update_response.data:
            return {"message": "Clocked out successfully", "shift": update_response.data[0]}
        raise HTTPException(status_code=500, detail="Failed to clock out")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clock out: {str(e)}"
        )


@router.get("/current-shift")
def get_current_shift(current_user: dict = Depends(get_current_user)):
    """
    Get current active shift if clocked in (Employee only).
    """
    if current_user.get("role") != "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for employees only"
        )
    
    try:
        active_shift = supabase.table("employee_shifts").select("*").eq(
            "user_id", current_user["id"]
        ).is_("clock_out", "null").execute()
        
        if active_shift.data:
            return active_shift.data[0]
        return None
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get shift: {str(e)}"
        )


@router.post("/upload-profile-photo")
async def upload_profile_photo(
    photo_url: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Update profile photo URL for employee.
    Note: Actual file upload should be handled by frontend to storage service.
    This endpoint just updates the URL in the database.
    """
    if current_user.get("role") != "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for employees only"
        )
    
    try:
        response = supabase.table("users").update(
            {"profile_photo_url": photo_url}
        ).eq("id", current_user["id"]).execute()
        
        if response.data:
            return {"message": "Profile photo updated successfully", "photo_url": photo_url}
        raise HTTPException(status_code=500, detail="Failed to update profile photo")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile photo: {str(e)}"
        )


@router.get("/shops/{shop_id}/clocked-in", response_model=List[dict])
def get_clocked_in_employees(
    shop_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get list of employees currently clocked in at a shop.
    Available to shop owners and employees of the shop.
    """
    # Check if user has access to this shop
    check_shop_access(shop_id, current_user, require_owner=False)
    
    try:
        # Get active shifts for this shop
        active_shifts = supabase.table("employee_shifts").select("*").eq(
            "shop_id", shop_id
        ).is_("clock_out", "null").execute()
        
        if not active_shifts.data:
            return []
        
        # Get user IDs of clocked-in employees
        user_ids = [shift["user_id"] for shift in active_shifts.data]
        
        # Fetch user details
        users_response = supabase.table("users").select(
            "id, username, email, profile_photo_url"
        ).in_("id", user_ids).execute()
        
        if not users_response.data:
            return []
        
        # Combine shift and user data
        result = []
        for shift in active_shifts.data:
            user = next((u for u in users_response.data if u["id"] == shift["user_id"]), None)
            if user:
                result.append({
                    "shift_id": shift["id"],
                    "user_id": user["id"],
                    "username": user["username"],
                    "email": user["email"],
                    "profile_photo_url": user.get("profile_photo_url"),
                    "clock_in": shift["clock_in"]
                })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get clocked-in employees: {str(e)}"
        )


@router.get("/employees/my-shops", response_model=List[dict])
def get_my_shops(current_user: dict = Depends(get_current_user)):
    """
    Get list of shops where current user is an active employee.
    Available to users with employee role only.
    """
    if current_user.get("role") != "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for employees only"
        )
    
    try:
        shop_ids = get_employee_shops(current_user["id"])
        
        if not shop_ids:
            return []
        
        # Fetch shop details
        shops_response = supabase.table("shops").select("*").in_("id", shop_ids).execute()
        
        return shops_response.data if shops_response.data else []
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch shops: {str(e)}"
        )
