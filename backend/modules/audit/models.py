"""AuditLog SQLAlchemy model.

Stores immutable records of high-impact actions for compliance and debugging.
Written asynchronously via audit_logger.py so request latency is unaffected.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, Index
from database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    # ISO timestamp (UTC) — set server-side for consistency
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Tenant this action belongs to (shop_id) — NULL for platform-level actions
    shop_id = Column(Integer, nullable=True, index=True)
    # Authenticated user who performed the action — NULL for anonymous actions
    user_id = Column(Integer, nullable=True, index=True)
    # Coarse action category: AUTH, QUEUE, SERVICE, EMPLOYEE, PAYMENT, ADMIN
    action = Column(String(64), nullable=False, index=True)
    # Fine-grained detail: e.g. "login_success", "queue_join", "service_delete"
    detail = Column(String(256), nullable=False)
    # Caller's IP address
    ip_address = Column(String(45), nullable=True)
    # Optional free-form payload (keep small — no PII blobs)
    metadata_ = Column("metadata", JSON, nullable=True)

    __table_args__ = (
        # Fast queries: latest events for a shop, filtered by action
        Index("ix_audit_logs_shop_action_created", "shop_id", "action", "created_at"),
    )
