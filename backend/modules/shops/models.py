from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

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
    ai_agent_name = Column(String, nullable=True)
    slug = Column(String, unique=True, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    is_active = Column(Boolean, default=True, index=True)
    tenant_schema = Column(String, nullable=True, index=True)  # NULL = shared/free, 'tenant_<id>' = premium
    odoo_company_id = Column(Integer, nullable=True, index=True)  # Odoo res.company ID for multi-tenant ERP isolation
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="owned_shops", foreign_keys=[owner_id])
    queues = relationship("Queue", back_populates="shop", cascade="all, delete-orphan")
    employees = relationship("ShopEmployee", back_populates="shop", cascade="all, delete-orphan")
    services = relationship("ShopService", back_populates="shop", cascade="all, delete-orphan")
    close_days = relationship("ShopCloseDay", back_populates="shop", cascade="all, delete-orphan")
    customers = relationship("ShopCustomer", back_populates="shop", cascade="all, delete-orphan")

class ShopService(Base):
    __tablename__ = "shop_services"
    
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    duration_minutes = Column(Integer, default=30)
    cost = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    catalog_section = Column(String(32), default="popular", nullable=False)
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

class ShopCustomer(Base):
    __tablename__ = "shop_customers"
    
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    phone = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    email = Column(String)
    visit_count = Column(Integer, default=1)
    last_visit = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    shop = relationship("Shop", back_populates="customers")
