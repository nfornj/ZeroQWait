"""Pydantic schemas for payment endpoints."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


class InvoiceLineItemCreate(BaseModel):
    description: str
    service_id: Optional[int] = None
    queue_item_id: Optional[int] = None
    appointment_id: Optional[int] = None
    quantity: int = 1
    unit_price: float = 0.0


class InvoiceCreate(BaseModel):
    shop_id: int
    customer_id: Optional[int] = None
    line_items: List[InvoiceLineItemCreate] = []
    tax_rate: float = 0.0
    discount_amount: float = 0.0
    tip_amount: float = 0.0
    notes: Optional[str] = None
    due_date: Optional[datetime] = None


class PaymentCreate(BaseModel):
    shop_id: int
    invoice_id: Optional[int] = None
    customer_id: Optional[int] = None
    amount: float
    tip_amount: float = 0.0
    method: str = "cash"
    notes: Optional[str] = None


class RefundCreate(BaseModel):
    payment_id: int
    amount: Optional[float] = None  # None = full refund
    reason: Optional[str] = None


class InvoiceResponse(BaseModel):
    id: int
    shop_id: int
    invoice_number: str
    status: str
    subtotal: float
    tax_amount: float
    discount_amount: float
    tip_amount: float
    total: float
    currency: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentResponse(BaseModel):
    id: int
    shop_id: int
    invoice_id: Optional[int] = None
    amount: float
    tip_amount: float
    method: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
