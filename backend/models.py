"""
SQLAlchemy ORM models for local PostgreSQL database
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey, Enum as SQLEnum, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

# Enums
class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    SHOP_OWNER = "shop_owner"
    MANAGER = "manager"
    EMPLOYEE = "employee"

class QueueStatus(str, enum.Enum):
    WAITING = "waiting"
    BEING_SERVED = "being_served"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


# Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    is_active = Column(Boolean, default=True)
    subscription_tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    owned_shops = relationship("Shop", back_populates="owner", foreign_keys="Shop.owner_id")
    queue_items = relationship("QueueItem", back_populates="user", foreign_keys="QueueItem.user_id")
    employee_shops = relationship("ShopEmployee", back_populates="user", foreign_keys="ShopEmployee.user_id")
    employee_shifts = relationship("EmployeeShift", back_populates="user")


class Shop(Base):
    __tablename__ = "shops"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text)
    shop_type = Column(String, nullable=False)
    address = Column(String, nullable=False)
    city = Column(String, nullable=False, index=True)
    state = Column(String, nullable=False)
    zip_code = Column(String, nullable=False)
    country = Column(String, default="United States", index=True)
    phone = Column(String, nullable=False)
    email = Column(String)
    website = Column(String)
    average_service_time = Column(Integer, default=30)
    logo_url = Column(String)
    primary_color = Column(String, default="#1976d2")
    secondary_color = Column(String)
    accent_color = Column(String)
    background_color = Column(String)
    slug = Column(String, unique=True, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="owned_shops", foreign_keys=[owner_id])
    queues = relationship("Queue", back_populates="shop", cascade="all, delete-orphan")
    employees = relationship("ShopEmployee", back_populates="shop", cascade="all, delete-orphan")
    services = relationship("ShopService", back_populates="shop", cascade="all, delete-orphan")


class Queue(Base):
    __tablename__ = "queues"
    
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, default="Main Queue")
    date = Column(DateTime, default=datetime.utcnow, index=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # Relationships
    shop = relationship("Shop", back_populates="queues")
    queue_items = relationship("QueueItem", back_populates="queue", cascade="all, delete-orphan", order_by="QueueItem.position")


class QueueItem(Base):
    __tablename__ = "queue_items"
    
    id = Column(Integer, primary_key=True, index=True)
    queue_id = Column(Integer, ForeignKey("queues.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String)
    customer_email = Column(String)
    position = Column(Integer, nullable=False, index=True)
    status = Column(SQLEnum(QueueStatus), default=QueueStatus.WAITING, nullable=False, index=True)
    notes = Column(Text)
    checked_in_at = Column(DateTime, default=datetime.utcnow)
    service_started_at = Column(DateTime)
    completed_at = Column(DateTime)
    assigned_employee_id = Column(Integer, ForeignKey("users.id"))
    
    # Service Link
    service_id = Column(Integer, ForeignKey("shop_services.id"), nullable=True)
    service_cost = Column(Float, default=0.0)  # Snapshot of cost at time of service
    
    # Relationships
    queue = relationship("Queue", back_populates="queue_items")
    user = relationship("User", foreign_keys=[user_id], back_populates="queue_items")
    assigned_employee = relationship("User", foreign_keys=[assigned_employee_id], post_update=True)
    service = relationship("ShopService", back_populates="queue_items")


class ShopEmployee(Base):
    __tablename__ = "shop_employees"
    
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True, index=True)
    employee_code = Column(String, nullable=True) # Visible ID for shop use
    
    # Relationships
    shop = relationship("Shop", back_populates="employees")
    user = relationship("User", back_populates="employee_shops", foreign_keys=[user_id])
    creator = relationship("User", foreign_keys=[created_by])


class EmployeeShift(Base):
    __tablename__ = "employee_shifts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    clock_in = Column(DateTime, default=datetime.utcnow, nullable=False)
    clock_out = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="employee_shifts")
    shop = relationship("Shop")



class ShopService(Base):
    __tablename__ = "shop_services"
    
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    duration_minutes = Column(Integer, default=30)
    cost = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    shop = relationship("Shop", back_populates="services")
    queue_items = relationship("QueueItem", back_populates="service")


class DailyAnalytics(Base):
    __tablename__ = "daily_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    total_customers = Column(Integer, default=0)
    completed_services = Column(Integer, default=0)
    cancelled_services = Column(Integer, default=0)
    total_revenue = Column(Float, default=0.0)
    avg_wait_time_minutes = Column(Float)
    avg_service_time_minutes = Column(Float)
    peak_hour_start = Column(Integer)
    peak_hour_customers = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    shop = relationship("Shop")


class ShopCloseDay(Base):
    __tablename__ = "shop_close_days"
    
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DateTime, nullable=False)
    reason = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    shop = relationship("Shop", back_populates="close_days")

# Update Shop relationship
Shop.close_days = relationship("ShopCloseDay", back_populates="shop", cascade="all, delete-orphan")
