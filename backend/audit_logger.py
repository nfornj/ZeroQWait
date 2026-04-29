"""Async audit logger.

Usage:
    from audit_logger import audit

    # Fire-and-forget — never raises, never blocks the request
    await audit(
        action="AUTH",
        detail="login_success",
        user_id=user.id,
        ip_address=request.client.host,
        metadata={"username": user.username},
    )

    # With shop context
    await audit(
        action="QUEUE",
        detail="queue_join",
        shop_id=shop_id,
        ip_address=request.client.host,
        metadata={"customer_name": "John D."},
    )

High-impact actions that should be audited
(non-exhaustive — add new ones as the platform grows):

AUTH:    login_success, login_failure, password_reset_request
QUEUE:   queue_join, queue_leave, queue_close, call_next
SERVICE: service_create, service_update, service_delete
EMPLOYEE: employee_add, employee_remove, shift_assign
PAYMENT: invoice_create, payment_register
ADMIN:   user_role_change, shop_delete, super_admin_action
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from database import SessionLocal
from modules.audit.models import AuditLog

logger = logging.getLogger(__name__)

# Background worker queue — bounded to avoid unbounded memory growth
_queue: asyncio.Queue = asyncio.Queue(maxsize=10_000)
_worker_task: Optional[asyncio.Task] = None


async def _worker() -> None:
    """Drain the queue and write records in small batches."""
    while True:
        try:
            record: Dict = await _queue.get()
            db = SessionLocal()
            try:
                db.add(AuditLog(**record))
                db.commit()
            except Exception as exc:
                logger.warning("audit_logger: write failed: %s", exc)
                db.rollback()
            finally:
                db.close()
                _queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("audit_logger: unexpected error: %s", exc)


def start_worker() -> None:
    """Start the background audit writer task.  Call once from app lifespan."""
    global _worker_task
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    if _worker_task is None or _worker_task.done():
        _worker_task = loop.create_task(_worker())
        logger.info("audit_logger: background writer started")


async def stop_worker() -> None:
    """Gracefully drain the queue then cancel the worker.  Call from lifespan shutdown."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        # Give in-flight items time to flush
        try:
            await asyncio.wait_for(_queue.join(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("audit_logger: flush timed-out; some records may be lost")
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    _worker_task = None
    logger.info("audit_logger: background writer stopped")


async def audit(
    *,
    action: str,
    detail: str,
    shop_id: Optional[int] = None,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Enqueue an audit record.  Never raises; safe to call from any endpoint."""
    record = {
        "action": action[:64],
        "detail": detail[:256],
        "shop_id": shop_id,
        "user_id": user_id,
        "ip_address": ip_address,
        "metadata_": metadata,
    }
    try:
        _queue.put_nowait(record)
    except asyncio.QueueFull:
        logger.warning("audit_logger: queue full — dropping record: %s/%s", action, detail)
