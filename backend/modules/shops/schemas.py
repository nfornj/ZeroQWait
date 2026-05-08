from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from shared.schemas import DictModel

class ShopBase(DictModel):
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
    primary_color: Optional[str] = "#FF5A5F"
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    background_color: Optional[str] = None
    ai_agent_name: Optional[str] = None
    slug: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class ShopCreate(ShopBase):
    pass

class ShopUpdate(DictModel):
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
    ai_agent_name: Optional[str] = None
    slug: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class Shop(ShopBase):
    id: int
    owner_id: int
    is_active: bool
    created_at: datetime
    odoo_company_id: Optional[int] = None
    telegram_chat_id: Optional[str] = None
    telegram_notifications_enabled: bool = False

# Service schemas
class ShopServiceBase(DictModel):
    name: str
    description: Optional[str] = None
    duration_minutes: int = 30
    cost: float = 0.0
    currency: Optional[str] = "USD"
    is_active: bool = True

class ShopServiceCreate(ShopServiceBase):
    pass

class ShopServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    cost: Optional[float] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None

class ShopService(ShopServiceBase):
    id: int
    shop_id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
