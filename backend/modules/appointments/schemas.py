"""Pydantic schemas for appointment endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AppointmentBase(BaseModel):
    shop_id: int
    service_id: Optional[int] = None
    employee_id: Optional[int] = None
    customer_name: str
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    scheduled_start: datetime
    scheduled_end: Optional[datetime] = None
    notes: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(BaseModel):
    service_id: Optional[int] = None
    employee_id: Optional[int] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class AppointmentResponse(AppointmentBase):
    id: int
    customer_id: Optional[int] = None
    status: str
    service_cost: float = 0.0
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
