from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, Table
from sqlalchemy.orm import relationship
from database import Base

# Association table for many-to-many relationship between users and haircut services
user_favorites = Table(
    "user_favorites",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("haircut_service_id", Integer, ForeignKey("haircut_services.id")),
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    
    # Relationship to favorite haircut services
    favorites = relationship(
        "HaircutService", 
        secondary=user_favorites,
        back_populates="favorited_by"
    )

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