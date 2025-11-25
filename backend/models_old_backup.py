from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, Table, DateTime, LargeBinary, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database import Base

# Association table for many-to-many relationship between users and haircut services
user_favorites = Table(
    "user_favorites",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("haircut_service_id", Integer, ForeignKey("haircut_services.id")),
)

class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    SHOP_OWNER = "shop_owner"

class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"

class QueueStatus(str, enum.Enum):
    WAITING = "waiting"
    BEING_SERVED = "being_served"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    role = Column(SQLEnum(UserRole), default=UserRole.CUSTOMER)
    
    # Subscription fields
    subscription_tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE)
    subscription_started_at = Column(DateTime, nullable=True)
    subscription_expires_at = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
    
    # Relationship to favorite haircut services
    favorites = relationship(
        "HaircutService", 
        secondary=user_favorites,
        back_populates="favorited_by"
    )
    
    # Relationship to owned shops
    owned_shops = relationship("Shop", back_populates="owner")

class HaircutService(Base):
    __tablename__ = "haircut_services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    address = Column(String)
    city = Column(String)
    state = Column(String)
    zip_code = Column(String)
    phone = Column(String)
    website = Column(String, nullable=True)
    latitude = Column(Float)
    longitude = Column(Float)
    rating = Column(Float, default=0.0)
    price_range = Column(String, nullable=True)
    hours = Column(String, nullable=True)
    
    # Relationship to users who favorited this service
    favorited_by = relationship(
        "User", 
        secondary=user_favorites,
        back_populates="favorites"
    )

class Shop(Base):
    __tablename__ = "shops"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    shop_type = Column(String)  # e.g., "barber", "salon", "doctor", "restaurant"
    address = Column(String)
    city = Column(String)
    state = Column(String)  # State/Province/Region
    zip_code = Column(String)  # ZIP/Postal Code
    country = Column(String, default="United States")  # Country
    phone = Column(String)
    email = Column(String, nullable=True)
    website = Column(String, nullable=True)
    
    # Branding & Vanity URL
    logo_url = Column(String, nullable=True)
    # Database-stored logo (BLOB)
    logo_data = Column(LargeBinary, nullable=True)
    logo_mime_type = Column(String, nullable=True)
    
    # Branding colors
    primary_color = Column(String, default="#1976d2")  # Default MUI Blue
    secondary_color = Column(String, nullable=True)  # Optional secondary brand color
    accent_color = Column(String, nullable=True)
    background_color = Column(String, nullable=True)
    
    slug = Column(String, unique=True, index=True, nullable=True)
    
    average_service_time = Column(Integer, default=30)  # in minutes
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Foreign key to shop owner
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    owner = relationship("User", back_populates="owned_shops")
    queues = relationship("Queue", back_populates="shop", cascade="all, delete-orphan")

class Queue(Base):
    __tablename__ = "queues"
    
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id"))
    name = Column(String, default="Main Queue")  # e.g., "Barber 1", "Walk-ins"
    date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    shop = relationship("Shop", back_populates="queues")
    queue_items = relationship("QueueItem", back_populates="queue", cascade="all, delete-orphan")

class QueueItem(Base):
    __tablename__ = "queue_items"
    
    id = Column(Integer, primary_key=True, index=True)
    queue_id = Column(Integer, ForeignKey("queues.id"))
    customer_name = Column(String)
    customer_phone = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Optional for logged-in users
    position = Column(Integer)
    status = Column(SQLEnum(QueueStatus), default=QueueStatus.WAITING)
    checked_in_at = Column(DateTime, default=datetime.utcnow)
    service_started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(String, nullable=True)
    
    # Relationships
    queue = relationship("Queue", back_populates="queue_items")
    user = relationship("User")

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    used = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User")
