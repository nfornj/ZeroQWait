from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from modules.auth.router import router as auth_router


app = FastAPI()
app.include_router(auth_router)
client = TestClient(app)


def test_forgot_password_persists_token_and_sends_email(monkeypatch):
    dummy_user = SimpleNamespace(id=42, email="owner@example.com")

    captured = {"set": None, "email": None}

    monkeypatch.setattr(
        "modules.auth.router.auth_service.get_user_by_email",
        lambda email: dummy_user if email == "owner@example.com" else None,
    )
    monkeypatch.setattr("modules.auth.router.secrets.token_urlsafe", lambda _: "fixed-token")

    def fake_set(key, value, ttl=300):
        captured["set"] = (key, value, ttl)
        return True

    def fake_send(email, token):
        captured["email"] = (email, token)
        return True

    monkeypatch.setattr("modules.auth.router.redis_client.set", fake_set)
    monkeypatch.setattr("modules.auth.router.send_password_reset_email", fake_send)

    response = client.post("/auth/forgot-password", params={"email": "owner@example.com"})

    assert response.status_code == 200
    assert response.json()["message"].startswith("If that email exists")
    assert captured["set"] == (
        "password_reset:fixed-token",
        {"user_id": 42},
        3600,
    )
    assert captured["email"] == ("owner@example.com", "fixed-token")


def test_reset_password_rejects_invalid_or_expired_token(monkeypatch):
    monkeypatch.setattr("modules.auth.router.redis_client.get", lambda _key: None)

    response = client.post(
        "/auth/reset-password",
        params={"token": "bad-token", "new_password": "new-password-123"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired reset token"


def test_reset_password_updates_password_and_invalidates_token(monkeypatch):
    deleted = {"key": None}

    monkeypatch.setattr(
        "modules.auth.router.redis_client.get",
        lambda key: {"user_id": 99} if key == "password_reset:good-token" else None,
    )
    monkeypatch.setattr(
        "modules.auth.router.auth_service.update_user_password",
        lambda user_id, new_password: user_id == 99 and new_password == "new-password-123",
    )
    monkeypatch.setattr(
        "modules.auth.router.redis_client.delete",
        lambda key: deleted.update({"key": key}),
    )

    response = client.post(
        "/auth/reset-password",
        params={"token": "good-token", "new_password": "new-password-123"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Password has been reset successfully."
    assert deleted["key"] == "password_reset:good-token"


# ── SES path in send_password_reset_email ────────────────────────────────────

def test_send_password_reset_email_uses_ses_when_configured():
    """When SES is configured, send_password_reset_email queues SES via asyncio.create_task."""
    import asyncio

    tasks_created = []

    # asyncio.create_task accepts a coroutine; we capture it without actually awaiting
    def fake_create_task(coro):
        tasks_created.append(coro)
        # Close the coroutine to avoid "coroutine was never awaited" warnings
        coro.close()
        return MagicMock()

    mock_ses_send = AsyncMock(return_value=True)

    with patch("shared.email_utils.is_ses_configured", return_value=True), \
         patch("shared.email_utils.ses_send_email", mock_ses_send), \
         patch("shared.email_utils.asyncio.create_task", fake_create_task):
        from shared import email_utils
        import importlib
        importlib.reload(email_utils)

        result = email_utils.send_password_reset_email(
            email="owner@example.com",
            reset_token="ses-test-token",
        )

    assert result is True
    assert len(tasks_created) == 1   # one coroutine was queued


def test_send_password_reset_email_falls_back_to_smtp_when_ses_not_configured(monkeypatch):
    """When SES is not configured but EMAIL_PASSWORD is set, SMTP is used."""
    import smtplib
    from unittest.mock import MagicMock

    smtp_calls = {"send": False}

    class FakeSMTP:
        def __init__(self, host, port):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
        def starttls(self):
            pass
        def login(self, user, password):
            pass
        def send_message(self, msg):
            smtp_calls["send"] = True

    with patch("shared.email_utils.is_ses_configured", return_value=False), \
         patch("shared.email_utils.EMAIL_PASSWORD", "fake-password"), \
         patch("shared.email_utils.smtplib.SMTP", FakeSMTP):
        from shared import email_utils
        import importlib
        importlib.reload(email_utils)

        result = email_utils.send_password_reset_email(
            email="owner@example.com",
            reset_token="smtp-test-token",
        )

    assert result is True
    assert smtp_calls["send"] is True
