from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool

    class Config:
        orm_mode = True

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Haircut service schemas
class HaircutServiceBase(BaseModel):
    name: str
    address: str
    city: str
    state: str
    zip_code: str
    phone: str
    website: Optional[str] = None
    latitude: float
    longitude: float
    rating: float = 0.0
    price_range: Optional[str] = None
    hours: Optional[str] = None

class HaircutServiceCreate(HaircutServiceBase):
    pass

class HaircutService(HaircutServiceBase):
    id: int

    class Config:
        orm_mode = True

# Search schema
class HaircutSearch(BaseModel):
    latitude: float
    longitude: float
    radius: float = Field(default=10.0, description="Search radius in kilometers")

# User with favorites schema
class UserWithFavorites(User):
    favorites: List[HaircutService] = []

    class Config:
        orm_mode = True 