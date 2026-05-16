from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database import Base

class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    SHOP_OWNER = "shop_owner"
    MANAGER = "manager"
    EMPLOYEE = "employee"
    SUPER_ADMIN = "super_admin"

class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "platform"}

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    is_active = Column(Boolean, default=True)
    subscription_tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    # Using string references to avoid circular imports
    owned_shops = relationship("Shop", back_populates="owner", foreign_keys="Shop.owner_id")
    queue_items = relationship("QueueItem", back_populates="user", foreign_keys="QueueItem.user_id")
    employee_shops = relationship("ShopEmployee", back_populates="user", foreign_keys="ShopEmployee.user_id")
    employee_shifts = relationship("EmployeeShift", back_populates="user")
