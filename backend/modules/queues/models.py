from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database import Base

class QueueStatus(str, enum.Enum):
    WAITING = "waiting"
    BEING_SERVED = "being_served"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class Queue(Base):
    __tablename__ = "queues"
    
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, default="Main Queue")
    date = Column(DateTime, default=datetime.utcnow, index=True)
    is_active = Column(Boolean, default=True, index=True)
    # Set to False to stop new joins while still serving the people already in queue
    accepting_joins = Column(Boolean, default=True, index=True)
    lock_reason = Column(Text, nullable=True)
    
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
    checked_in_at = Column(DateTime, default=datetime.utcnow, index=True)
    service_started_at = Column(DateTime)
    completed_at = Column(DateTime, index=True)
    assigned_employee_id = Column(Integer, ForeignKey("users.id"))
    
    # Service Link
    service_id = Column(Integer, ForeignKey("shop_services.id"), nullable=True, index=True)
    service_cost = Column(Float, default=0.0)  # Snapshot of cost at time of service
    
    # Relationships
    queue = relationship("Queue", back_populates="queue_items")
    user = relationship("User", foreign_keys=[user_id], back_populates="queue_items")
    assigned_employee = relationship("User", foreign_keys=[assigned_employee_id], post_update=True)
    service = relationship("ShopService", back_populates="queue_items")
