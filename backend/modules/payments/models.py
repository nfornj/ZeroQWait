"""Payment, Invoice, and Transaction models for POS & billing."""

import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, Text,
    ForeignKey, Enum as SQLEnum, JSON,
)
from sqlalchemy.orm import relationship

from database import Base


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    CARD = "card"
    ONLINE = "online"
    OTHER = "other"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    FAILED = "failed"
    VOIDED = "voided"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class Invoice(Base):
    """An invoice issued to a customer — may group multiple line items."""
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("platform.shops.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("shop_customers.id"), nullable=True, index=True)

    invoice_number = Column(String, nullable=False, index=True)
    status = Column(SQLEnum(InvoiceStatus), default=InvoiceStatus.DRAFT, nullable=False, index=True)

    subtotal = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    tax_rate = Column(Float, default=0.0)  # e.g. 0.13 for 13%
    discount_amount = Column(Float, default=0.0)
    tip_amount = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    currency = Column(String, default="USD")

    notes = Column(Text)
    due_date = Column(DateTime)
    paid_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    shop = relationship("Shop")
    customer = relationship("ShopCustomer")
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice")


class InvoiceLineItem(Base):
    """Individual line on an invoice — mirrors a service rendered."""
    __tablename__ = "invoice_line_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(Integer, ForeignKey("shop_services.id"), nullable=True)
    queue_item_id = Column(Integer, ForeignKey("queue_items.id"), nullable=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)

    description = Column(String, nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, default=0.0)
    total = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    invoice = relationship("Invoice", back_populates="line_items")
    service = relationship("ShopService")


class Payment(Base):
    """A payment transaction against an invoice (supports split payments)."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("platform.shops.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey("shop_customers.id"), nullable=True, index=True)

    amount = Column(Float, nullable=False)
    tip_amount = Column(Float, default=0.0)
    currency = Column(String, default="USD")

    method = Column(SQLEnum(PaymentMethod), default=PaymentMethod.CASH, nullable=False)
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False, index=True)

    # External payment reference (Stripe charge ID, etc.)
    external_ref = Column(String, nullable=True)
    payment_meta = Column(JSON, nullable=True)

    processed_by = Column(Integer, ForeignKey("platform.users.id"), nullable=True)
    processed_at = Column(DateTime)
    refunded_at = Column(DateTime)
    refund_amount = Column(Float, default=0.0)

    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    shop = relationship("Shop")
    invoice = relationship("Invoice", back_populates="payments")
    customer = relationship("ShopCustomer")
    processor = relationship("User", foreign_keys=[processed_by])
