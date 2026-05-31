from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey, Time, ARRAY, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Shop(Base):
    __tablename__ = "shops"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("platform.users.id"), nullable=False, index=True)
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
    tenant_schema = Column(String, nullable=True, index=True)  # Shop-specific schema name when data is isolated at schema level
    data_isolation_mode = Column(String(32), nullable=False, default="shared_public", index=True)
    compute_mode = Column(String(32), nullable=False, default="shared_instance", index=True)
    active_modules = Column(JSON, nullable=False, default=list)
    vertical = Column(String(50), default="generic", index=True)
    odoo_company_id = Column(Integer, nullable=True, index=True)  # Odoo res.company ID for multi-tenant ERP isolation
    created_at = Column(DateTime, default=datetime.utcnow)

    # Telegram integration
    telegram_chat_id = Column(String, nullable=True)                        # Fernet-encrypted chat ID (set after /start handshake)
    telegram_chat_id_hash = Column(String, nullable=True, index=True)       # HMAC-SHA256 of chat_id — used for fast reverse lookup
    telegram_notifications_enabled = Column(Boolean, default=False)         # Whether notifications are active
    telegram_connect_token = Column(String, nullable=True)                  # One-time onboarding token (cleared after handshake)
    telegram_connect_token_expires_at = Column(DateTime(timezone=True), nullable=True)  # Token expiry (10 min)

    __table_args__ = {"schema": "platform"}

    # Relationships
    owner = relationship("User", back_populates="owned_shops", foreign_keys=[owner_id])
    queues = relationship("Queue", back_populates="shop", cascade="all, delete-orphan")
    employees = relationship("ShopEmployee", back_populates="shop", cascade="all, delete-orphan")
    services = relationship("ShopService", back_populates="shop", cascade="all, delete-orphan")
    close_days = relationship("ShopCloseDay", back_populates="shop", cascade="all, delete-orphan")
    customers = relationship("ShopCustomer", back_populates="shop", cascade="all, delete-orphan")
    operating_hours = relationship("ShopOperatingHours", back_populates="shop", uselist=False, cascade="all, delete-orphan")
    runtime_assignment = relationship("ShopRuntimeAssignment", back_populates="shop", uselist=False, cascade="all, delete-orphan")


class ShopRuntimeAssignment(Base):
    __tablename__ = "shop_runtime_assignments"
    __table_args__ = {"schema": "platform"}

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("platform.shops.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    runtime_mode = Column(String(32), nullable=False, default="shared_instance", index=True)
    instance_key = Column(String(128), nullable=True, index=True)
    namespace = Column(String(64), nullable=True)
    backend_service = Column(String(128), nullable=True)
    worker_service = Column(String(128), nullable=True)
    route_host = Column(String(255), nullable=True, index=True)
    runtime_status = Column(String(32), nullable=False, default="pending", index=True)
    assigned_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    shop = relationship("Shop", back_populates="runtime_assignment")

class ShopService(Base):
    __tablename__ = "shop_services"
    
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("platform.shops.id", ondelete="CASCADE"), nullable=False, index=True)
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
    shop_id = Column(Integer, ForeignKey("platform.shops.id", ondelete="CASCADE"), nullable=False, index=True)
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
    shop_id = Column(Integer, ForeignKey("platform.shops.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DateTime, nullable=False)
    reason = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    shop = relationship("Shop", back_populates="close_days")


class ShopOperatingHours(Base):
    """Per-shop configuration for Temporal auto-open/close schedules."""
    __tablename__ = "shop_operating_hours"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("platform.shops.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    open_time = Column(Time, nullable=False, default="09:00:00")
    close_time = Column(Time, nullable=False, default="17:00:00")
    timezone = Column(String(64), nullable=False, default="UTC")

    auto_open_queue = Column(Boolean, nullable=False, default=True)
    auto_close_queue = Column(Boolean, nullable=False, default=True)
    pre_close_buffer_minutes = Column(Integer, nullable=False, default=15)
    auto_lock_joins = Column(Boolean, nullable=False, default=True)
    operating_days = Column(ARRAY(Integer), nullable=False, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    shop = relationship("Shop", back_populates="operating_hours")

class ShopCustomer(Base):
    __tablename__ = "shop_customers"
    
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("platform.shops.id", ondelete="CASCADE"), nullable=False, index=True)
    phone = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    email = Column(String)
    visit_count = Column(Integer, default=1)
    last_visit = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    shop = relationship("Shop", back_populates="customers")
