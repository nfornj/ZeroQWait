from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

# Define enums locally since we removed models.py
class UserRole(str, Enum):
    CUSTOMER = "customer"
    SHOP_OWNER = "shop_owner"
    MANAGER = "manager"
    EMPLOYEE = "employee"

class QueueStatus(str, Enum):
    WAITING = "waiting"
    BEING_SERVED = "being_served"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.CUSTOMER

class User(UserBase):
    id: int
    is_active: bool
    role: UserRole

    class Config:
        from_attributes = True

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None


# Shop schemas
class ShopBase(BaseModel):
    name: str
    description: Optional[str] = None
    shop_type: str
    address: str
    city: str
    state: str  # State/Province/Region
    zip_code: str  # ZIP/Postal Code
    country: str = "United States"  # Country
    phone: str
    email: Optional[str] = None
    website: Optional[str] = None
    average_service_time: int = 30
    logo_url: Optional[str] = None
    primary_color: Optional[str] = "#1976d2"
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    background_color: Optional[str] = None
    slug: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class ShopCreate(ShopBase):
    pass

class ShopUpdate(BaseModel):
    """Schema for updating shop details - all fields optional"""
    name: Optional[str] = None
    description: Optional[str] = None
    shop_type: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    average_service_time: Optional[int] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    background_color: Optional[str] = None
    slug: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class Shop(ShopBase):
    id: int
    owner_id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Queue Item schemas
class QueueItemBase(BaseModel):
    customer_name: str
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    notes: Optional[str] = None

class QueueItemCreate(QueueItemBase):
    pass

class QueueItem(QueueItemBase):
    id: int
    queue_id: int
    user_id: Optional[int] = None
    position: int
    status: QueueStatus
    checked_in_at: datetime
    service_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_employee_id: Optional[int] = None
    assigned_employee: Optional[dict] = None  # Will be populated with employee details

    class Config:
        from_attributes = True

# Queue schemas
class QueueBase(BaseModel):
    name: str = "Main Queue"

class QueueCreate(QueueBase):
    pass

class Queue(QueueBase):
    id: int
    shop_id: int
    date: datetime
    is_active: bool
    queue_items: List[QueueItem] = []

    class Config:
        from_attributes = True

# Shop with active queue
class ShopWithQueue(Shop):
    queues: List[Queue] = []

    class Config:
        from_attributes = True

# Employee schemas
class EmployeeCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class ShopEmployee(BaseModel):
    id: int
    shop_id: int
    user_id: int
    created_at: datetime
    created_by: Optional[int] = None
    is_active: bool
    user: User  # Nested user details

    class Config:
        from_attributes = True

# Employee shift schemas
class EmployeeShift(BaseModel):
    id: int
    user_id: int
    username: str
    shop_id: int
    clock_in: datetime
    clock_out: Optional[datetime] = None
    
    class Config:
        from_attributes = True
