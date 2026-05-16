from pydantic import EmailStr, BaseModel
from typing import Optional
from shared.schemas import DictModel
from modules.auth.models import UserRole, SubscriptionTier

# User schemas
class UserBase(DictModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.CUSTOMER

class User(UserBase):
    id: int
    is_active: bool
    role: UserRole
    subscription_tier: Optional[SubscriptionTier] = SubscriptionTier.FREE

class UserProfile(DictModel):
    """Embeddable user summary for related models. Email is Optional to handle
    system/employee accounts that may not have a valid email on record."""
    id: int
    username: str
    email: Optional[str] = None
    is_active: bool
    role: UserRole

# Token schemas
class Token(DictModel):
    access_token: str
    token_type: str

class TokenData(DictModel):
    username: Optional[str] = None
