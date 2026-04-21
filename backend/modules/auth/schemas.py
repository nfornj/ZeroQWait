from pydantic import EmailStr, BaseModel
from typing import Optional
from shared.schemas import DictModel
from modules.auth.models import UserRole

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

# Token schemas
class Token(DictModel):
    access_token: str
    token_type: str

class TokenData(DictModel):
    username: Optional[str] = None
