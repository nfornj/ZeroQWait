"""
Unit tests for the async audit logger.

All DB access is mocked — no live database or Redis required.
"""
import asyncio
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Helpers ──────────────────────────────────────────────────────────

def make_mock_session():
    """Return a mock SQLAlchemy session that records added objects."""
    session = MagicMock()
    session.added = []
    session.add.side_effect = lambda obj: session.added.append(obj)
    session.commit = MagicMock()
    session.close = MagicMock()
    return session


# ── Tests ────────────────────────────────────────────────────────────

class TestAuditLogger:
    """Unit tests for backend/audit_logger.py"""

    def setup_method(self):
        # Re-import fresh module state for each test to avoid worker task leaks.
        import importlib
        import audit_logger
        importlib.reload(audit_logger)
        self.module = audit_logger

    def test_audit_enqueues_without_raising(self):
        """audit() must never raise even if the queue is full."""
        loop = asyncio.new_event_loop()
        try:
            # Even without a running worker the put_nowait should not raise.
            loop.run_until_complete(
                self.module.audit(action="AUTH", detail="login_test", ip_address="127.0.0.1")
            )
        finally:
            loop.close()

    def test_audit_drops_on_full_queue(self):
        """When the queue is full, audit() logs a warning and does not block."""
        loop = asyncio.new_event_loop()
        try:
            # Fill the queue to capacity.
            q = self.module._queue
            while not q.full():
                try:
                    q.put_nowait(None)
                except asyncio.QueueFull:
                    break

            # This must not block or raise.
            loop.run_until_complete(
                self.module.audit(action="QUEUE", detail="flood_test")
            )
        finally:
            loop.close()

    def test_worker_writes_audit_record(self):
        """_worker() drains the queue and writes rows to the DB session."""
        mock_session = make_mock_session()

        with patch("audit_logger.SessionLocal", return_value=mock_session):
            loop = asyncio.new_event_loop()
            try:
                async def run():
                    # Enqueue ONE record then a sentinel to stop the worker.
                    await self.module.audit(
                        action="AUTH",
                        detail="login_success",
                        user_id=42,
                        shop_id=7,
                        ip_address="10.0.0.1",
                        metadata={"username": "alice"},
                    )
                    # start_worker() is synchronous (creates a task)
                    self.module.start_worker()
                    await asyncio.sleep(0.1)
                    await self.module.stop_worker()

                loop.run_until_complete(run())
            finally:
                loop.close()

        # At least one write occurred.
        assert mock_session.add.call_count >= 1, "Expected at least one AuditLog row written"
        record = mock_session.added[0]
        assert record.action == "AUTH"
        assert record.detail == "login_success"
        assert record.user_id == 42
        assert record.shop_id == 7
        assert record.ip_address == "10.0.0.1"

    def test_audit_metadata_stored(self):
        """metadata dict is preserved on the AuditLog record."""
        mock_session = make_mock_session()

        with patch("audit_logger.SessionLocal", return_value=mock_session):
            loop = asyncio.new_event_loop()
            try:
                async def run():
                    await self.module.audit(
                        action="QUEUE",
                        detail="queue_join",
                        shop_id=3,
                        ip_address="1.2.3.4",
                        metadata={"customer_name": "Bob", "position": 5},
                    )
                    # start_worker() is synchronous
                    self.module.start_worker()
                    await asyncio.sleep(0.1)
                    await self.module.stop_worker()

                loop.run_until_complete(run())
            finally:
                loop.close()

        assert mock_session.add.call_count >= 1
        record = mock_session.added[0]
        assert record.metadata_ == {"customer_name": "Bob", "position": 5}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
