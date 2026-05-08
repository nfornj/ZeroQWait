from typing import Optional
from datetime import datetime
from pydantic import EmailStr
from shared.schemas import DictModel
from modules.auth.models import UserRole
from modules.auth.schemas import User, UserProfile

class EmployeeCreate(DictModel):
    username: str
    email: EmailStr
    password: str
    role: Optional[UserRole] = UserRole.EMPLOYEE

class ShopEmployee(DictModel):
    id: int
    shop_id: int
    user_id: int
    created_at: datetime
    created_by: Optional[int] = None
    is_active: bool
    user: UserProfile  # Nested user summary — email is Optional for system accounts

class EmployeeShift(DictModel):
    id: int
    user_id: int
    username: str
    email: Optional[str] = None
    profile_photo_url: Optional[str] = None
    shop_id: int
    clock_in: datetime
    clock_out: Optional[datetime] = None
