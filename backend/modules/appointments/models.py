"""Appointment models for scheduled bookings."""

import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, Text,
    ForeignKey, Enum as SQLEnum,
)
from sqlalchemy.orm import relationship

from database import Base


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("shop_customers.id"), nullable=True, index=True)
    service_id = Column(Integer, ForeignKey("shop_services.id"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Customer info (denormalised for walk-in appointments without a customer record)
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, index=True)
    customer_email = Column(String)

    # Scheduling
    scheduled_start = Column(DateTime, nullable=False, index=True)
    scheduled_end = Column(DateTime, nullable=False)
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)

    status = Column(
        SQLEnum(AppointmentStatus),
        default=AppointmentStatus.SCHEDULED,
        nullable=False,
        index=True,
    )

    # Pricing snapshot at booking time
    service_cost = Column(Float, default=0.0)
    notes = Column(Text)

    # Cancellation / rescheduling
    cancelled_at = Column(DateTime)
    cancel_reason = Column(String)
    rescheduled_from_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    shop = relationship("Shop")
    customer = relationship("ShopCustomer")
    service = relationship("ShopService")
    employee = relationship("User", foreign_keys=[employee_id])
    rescheduled_from = relationship("Appointment", remote_side=[id])
