from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

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
