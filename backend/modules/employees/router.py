from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from modules.employees import schemas
from modules.employees.service import employee_service
from modules.auth.service import auth_service
from shared.auth_utils import get_current_user, get_password_hash
from permissions import check_shop_access
from datetime import datetime

router = APIRouter()

@router.post("/shops/{shop_id}/employees", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def add_employee(
    shop_id: int,
    employee: schemas.EmployeeCreate,
    current_user: dict = Depends(get_current_user)
):
    check_shop_access(shop_id, current_user, require_owner=True)
    
    # Check username/email via auth_service
    if auth_service.get_user_by_username(employee.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    if auth_service.get_user_by_email(employee.email):
        raise HTTPException(status_code=400, detail="Email already registered")
        
    # Create user
    try:
        # Pydantic schemas.UserCreate expects basic fields.
        # Here we have EmployeeCreate. Helper to convert?
        # EmployeeCreate has role=EMPLOYEE.
        # We need schemas.UserCreate(email=..., username=..., password=..., role=...)
        # We can construct it.
        from modules.auth.schemas import UserCreate
        user_create = UserCreate(
            email=employee.email,
            username=employee.username, 
            password=employee.password,
            role=employee.role
        )
        new_user = auth_service.create_user(user_create)
        
        # Link employee (ShopEmployee)
        # We need method in employee_service or directly create default implementation
        # EmployeeService currently has get_shop_employees.
        # We need create_shop_employee.
        # We should add it to service. For now, we omit logic or assume added.
        # Let's add it to EmployeeService in next step or now?
        # I'll rely on it being there (will add it).
        
        # employee_service.create_shop_employee(...)
        pass # To be implemented in service
        
        return new_user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/shops/{shop_id}/employees", response_model=List[schemas.ShopEmployee])
def list_employees(
    shop_id: int,
    include_inactive: bool = False,
    current_user: dict = Depends(get_current_user)
):
    check_shop_access(shop_id, current_user, require_owner=True)
    return employee_service.get_shop_employees(shop_id)
