from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from modules.employees import schemas
from modules.employees.service import employee_service
from modules.auth.service import auth_service
from db_interface import db_interface
from shared.auth_utils import get_current_user, get_password_hash
from permissions import check_shop_access, get_employee_shops
from datetime import datetime, timedelta

router = APIRouter()


# ──────────────────────────────────────
# Shop-owner employee management
# ──────────────────────────────────────

@router.post("/shops/{shop_id}/employees", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def add_employee(
    shop_id: int,
    employee: schemas.EmployeeCreate,
    current_user: dict = Depends(get_current_user)
):
    check_shop_access(shop_id, current_user, require_owner=True)

    if auth_service.get_user_by_username(employee.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    if auth_service.get_user_by_email(employee.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        from modules.auth.schemas import UserCreate
        user_create = UserCreate(
            email=employee.email,
            username=employee.username,
            password=employee.password,
            role=employee.role
        )
        new_user = auth_service.create_user(user_create)

        # Link employee to shop
        employee_service.create_shop_employee({
            "shop_id": shop_id,
            "user_id": new_user.id,
            "created_by": current_user["id"],
            "is_active": True,
        })

        return new_user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shops/{shop_id}/employee-shifts", response_model=List[schemas.EmployeeShift])
def list_employee_shifts(
    shop_id: int,
    months: int = 1,
    employee_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    check_shop_access(shop_id, current_user, require_owner=True)
    try:
        from datetime import timedelta
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30 * months)
        shifts = db_interface.get_employee_shifts(shop_id, start_date, end_date, user_id=employee_id)
        return shifts
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load shifts: {str(e)}")


@router.get("/shops/{shop_id}/employees", response_model=List[schemas.ShopEmployee])
def list_employees(
    shop_id: int,
    include_inactive: bool = False,
    current_user: dict = Depends(get_current_user)
):
    check_shop_access(shop_id, current_user, require_owner=True)
    return employee_service.get_shop_employees(shop_id, include_inactive=include_inactive)


@router.get("/shops/{shop_id}/employee-shifts")
def list_employee_shifts(
    shop_id: int,
    months: int = 3,
    employee_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    check_shop_access(shop_id, current_user, require_owner=True)
    bounded_months = max(1, min(months, 12))
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=bounded_months * 31)

    try:
        shifts = db_interface.get_employee_shifts(shop_id, start_date, end_date, user_id=employee_id)
        enriched_shifts = []
        for shift in shifts:
            user = db_interface.get_user_by_id(shift["user_id"])
            enriched_shifts.append({
                **shift,
                "username": user["username"] if user else "Unknown employee",
                "email": user["email"] if user else "",
                "profile_photo_url": user.get("profile_photo_url") if user else None,
            })
        return enriched_shifts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load employee shifts: {str(e)}")


@router.delete("/shops/{shop_id}/employees/{employee_id}", status_code=status.HTTP_200_OK)
def remove_employee(
    shop_id: int,
    employee_id: int,
    current_user: dict = Depends(get_current_user)
):
    check_shop_access(shop_id, current_user, require_owner=True)
    try:
        updated = db_interface.update_shop_employee(shop_id, employee_id, {"is_active": False})
        if not updated:
            raise HTTPException(status_code=404, detail="Employee not found or update failed")
        return {"message": "Employee removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove employee: {str(e)}")


@router.put("/shops/{shop_id}/employees/{employee_id}/reactivate", status_code=status.HTTP_200_OK)
def reactivate_employee(
    shop_id: int,
    employee_id: int,
    current_user: dict = Depends(get_current_user)
):
    check_shop_access(shop_id, current_user, require_owner=True)
    try:
        updated = db_interface.update_shop_employee(shop_id, employee_id, {"is_active": True})
        if not updated:
            raise HTTPException(status_code=404, detail="Employee not found or update failed")
        return {"message": "Employee reactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reactivate employee: {str(e)}")


# ──────────────────────────────────────
# Username / email availability checks
# ──────────────────────────────────────

@router.get("/check-username/{username}")
def check_username_availability(username: str):
    try:
        return {"available": not db_interface.check_username_exists(username)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check username: {str(e)}")


@router.get("/check-email/{email}")
def check_email_availability(email: str):
    try:
        return {"available": not db_interface.check_email_exists(email)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check email: {str(e)}")


# ──────────────────────────────────────
# Employee-facing endpoints (dashboard)
# ──────────────────────────────────────

@router.get("/employees/my-shops")
def get_my_shops(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "employee":
        raise HTTPException(status_code=403, detail="This endpoint is for employees only")
    try:
        shop_ids = get_employee_shops(current_user["id"])
        if not shop_ids:
            return []
        shops = []
        for sid in shop_ids:
            shop = db_interface.get_shop_by_id(sid)
            if shop:
                shops.append(shop.model_dump() if hasattr(shop, 'model_dump') else shop)
        return shops
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch shops: {str(e)}")


@router.get("/current-shift")
def get_current_shift(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "employee":
        raise HTTPException(status_code=403, detail="This endpoint is for employees only")
    try:
        active_shift = db_interface.get_active_shift(current_user["id"])
        if active_shift:
            return active_shift
        return None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get shift: {str(e)}")


@router.post("/clock-in/{shop_id}")
def clock_in(shop_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "employee":
        raise HTTPException(status_code=403, detail="This endpoint is for employees only")
    check_shop_access(shop_id, current_user, require_owner=False)
    try:
        active_shift = db_interface.get_active_shift(current_user["id"])
        if active_shift:
            raise HTTPException(status_code=400, detail="You are already clocked in. Please clock out first.")
        shift_data = {
            "user_id": current_user["id"],
            "shop_id": shop_id,
            "clock_in": datetime.utcnow().isoformat()
        }
        new_shift = db_interface.create_employee_shift(shift_data)
        if new_shift:
            return {"message": "Clocked in successfully", "shift": new_shift}
        raise HTTPException(status_code=500, detail="Failed to clock in")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clock in: {str(e)}")


@router.post("/clock-out")
def clock_out(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "employee":
        raise HTTPException(status_code=403, detail="This endpoint is for employees only")
    try:
        active_shift = db_interface.get_active_shift(current_user["id"])
        if not active_shift:
            raise HTTPException(status_code=400, detail="You are not currently clocked in")
        updated_shift = db_interface.update_employee_shift(
            active_shift["id"],
            {"clock_out": datetime.utcnow().isoformat()}
        )
        if updated_shift:
            return {"message": "Clocked out successfully", "shift": updated_shift}
        raise HTTPException(status_code=500, detail="Failed to clock out")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clock out: {str(e)}")


@router.post("/upload-profile-photo")
async def upload_profile_photo(photo_url: str, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "employee":
        raise HTTPException(status_code=403, detail="This endpoint is for employees only")
    try:
        updated = db_interface.update_user(current_user["id"], {"profile_photo_url": photo_url})
        if updated:
            return {"message": "Profile photo updated successfully", "photo_url": photo_url}
        raise HTTPException(status_code=500, detail="Failed to update profile photo")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update profile photo: {str(e)}")
