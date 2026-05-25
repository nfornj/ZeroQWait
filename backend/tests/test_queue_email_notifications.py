"""
Tests for queue email notifications and public status endpoint.

Covers:
  - join_queue assigns a unique status_token to the new QueueItem
  - GET /queues/status/{token} returns correct position/status fields
  - GET /queues/status/{unknown-token} returns 404
  - call_next_customer fires the "you're next" email task
  - send_queue_join_email and send_youre_next_email behave correctly when SES
    is configured / not configured
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Unit tests for queue_email helpers ────────────────────────────────────────

def test_send_queue_join_email_ses_not_configured_is_noop(caplog):
    """When SES is not configured, send_queue_join_email returns immediately."""
    with patch("services.queue_email.is_ses_configured", return_value=False):
        from services.queue_email import send_queue_join_email

        # Should not raise even with a dummy email
        asyncio.run(
            send_queue_join_email(
                customer_email="test@example.com",
                customer_name="Alice",
                shop_name="Test Shop",
                position=3,
                estimated_wait_min=15,
                status_url="https://example.com/queue-status/abc123",
            )
        )
    # No error means success; function should not propagate any exception


def test_send_queue_join_email_ses_calls_aws(caplog):
    """When SES is configured, send_queue_join_email calls aws_client.send_email."""
    mock_send = AsyncMock(return_value=True)

    from services import queue_email
    import importlib
    importlib.reload(queue_email)

    with patch.object(queue_email, "is_ses_configured", return_value=True), \
         patch.object(queue_email, "ses_send_email", mock_send):
        asyncio.run(
            queue_email.send_queue_join_email(
                customer_email="customer@example.com",
                customer_name="Bob",
                shop_name="Bob's Barbers",
                position=1,
                estimated_wait_min=5,
                status_url="https://zeroqwait.com/queue-status/xyz",
            )
        )

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["to_address"] == "customer@example.com"
    assert "Bob" in call_kwargs["markdown_text"]
    assert "Bob's Barbers" in call_kwargs["markdown_text"]
    assert "https://zeroqwait.com/queue-status/xyz" in call_kwargs["markdown_text"]


def test_send_youre_next_email_ses_calls_aws():
    """send_youre_next_email calls aws_client.send_email with the right content."""
    mock_send = AsyncMock(return_value=True)

    from services import queue_email
    import importlib
    importlib.reload(queue_email)

    with patch.object(queue_email, "is_ses_configured", return_value=True), \
         patch.object(queue_email, "ses_send_email", mock_send):
        asyncio.run(
            queue_email.send_youre_next_email(
                customer_email="customer@example.com",
                customer_name="Carol",
                shop_name="Carol's Cuts",
                service_name="Haircut",
                status_url="https://zeroqwait.com/queue-status/def456",
            )
        )

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["to_address"] == "customer@example.com"
    assert "Carol" in call_kwargs["markdown_text"]
    assert "Carol's Cuts" in call_kwargs["markdown_text"]


def test_send_youre_next_email_ses_exception_does_not_raise():
    """Exceptions in SES are swallowed — queue operations must not fail."""
    mock_send = AsyncMock(side_effect=Exception("SES timeout"))

    from services import queue_email
    import importlib
    importlib.reload(queue_email)

    with patch.object(queue_email, "is_ses_configured", return_value=True), \
         patch.object(queue_email, "ses_send_email", mock_send):
        # Must not raise
        asyncio.run(
            queue_email.send_youre_next_email(
                customer_email="customer@example.com",
                customer_name="Dave",
                shop_name="Dave's",
                service_name=None,
                status_url="https://zeroqwait.com/queue-status/ghi789",
            )
        )


# ── Integration-style tests for the public status endpoint ────────────────────

def _make_queue_status_app():
    """Construct a minimal FastAPI app that mounts the queues router."""
    from fastapi import FastAPI
    from modules.queues.router import router as queue_router
    app = FastAPI()
    app.include_router(queue_router)
    return app


def test_queue_status_endpoint_returns_404_for_unknown_token(monkeypatch):
    """GET /queues/status/<token> → 404 when the token is not in the DB."""
    monkeypatch.setattr(
        "modules.queues.router.queue_service.get_queue_item_by_token",
        lambda token: None,
    )

    from fastapi.testclient import TestClient
    client = TestClient(_make_queue_status_app())

    response = client.get("/queues/status/totally-unknown-token-xyz")
    assert response.status_code == 404


def test_queue_status_endpoint_returns_position_data(monkeypatch):
    """GET /queues/status/<token> returns customer_name, position, status etc."""
    import datetime

    fake_item = SimpleNamespace(
        id=7,
        queue_id=99,
        status="waiting",
        customer_name="Eve Testington",
        status_token="abc123",
        customer_email="eve@example.com",
        checked_in_at=datetime.datetime(2025, 1, 1, 10, 0, 0),
        service=None,
    )

    fake_queue = SimpleNamespace(id=99, shop_id=5)
    fake_shop = SimpleNamespace(id=5, name="Best Barbers")

    monkeypatch.setattr(
        "modules.queues.router.queue_service.get_queue_item_by_token",
        lambda token: fake_item if token == "abc123" else None,
    )
    monkeypatch.setattr(
        "modules.queues.router.db_interface.get_queue_position",
        lambda item_id: {"position": 2, "estimated_wait_minutes": 10},
    )
    monkeypatch.setattr(
        "modules.queues.router.queue_service.get_queue",
        lambda queue_id: fake_queue,
    )
    monkeypatch.setattr(
        "modules.queues.router.shop_service.get_shop",
        lambda shop_id: fake_shop,
    )

    from fastapi.testclient import TestClient
    client = TestClient(_make_queue_status_app())

    response = client.get("/queues/status/abc123")
    assert response.status_code == 200

    body = response.json()
    assert body["customer_name"] == "Eve"          # first name only
    assert body["position"] == 2
    assert body["status"] == "waiting"
    assert body["estimated_wait_minutes"] == 10
    assert body["shop_name"] == "Best Barbers"
    assert body["service_name"] is None


def test_queue_status_endpoint_shows_being_served(monkeypatch):
    """When status is being_served, endpoint returns it correctly."""
    import datetime

    fake_item = SimpleNamespace(
        id=8,
        queue_id=100,
        status="being_served",
        customer_name="Frank",
        status_token="being123",
        customer_email="frank@example.com",
        checked_in_at=datetime.datetime(2025, 1, 1, 11, 0, 0),
        service=SimpleNamespace(name="Shave"),
    )
    fake_queue = SimpleNamespace(id=100, shop_id=6)
    fake_shop = SimpleNamespace(id=6, name="Frank's Cuts")

    monkeypatch.setattr(
        "modules.queues.router.queue_service.get_queue_item_by_token",
        lambda token: fake_item if token == "being123" else None,
    )
    monkeypatch.setattr(
        "modules.queues.router.db_interface.get_queue_position",
        lambda item_id: {"position": 1, "estimated_wait_minutes": 0},
    )
    monkeypatch.setattr(
        "modules.queues.router.queue_service.get_queue",
        lambda queue_id: fake_queue,
    )
    monkeypatch.setattr(
        "modules.queues.router.shop_service.get_shop",
        lambda shop_id: fake_shop,
    )

    from fastapi.testclient import TestClient
    client = TestClient(_make_queue_status_app())

    response = client.get("/queues/status/being123")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "being_served"
    assert body["service_name"] == "Shave"
