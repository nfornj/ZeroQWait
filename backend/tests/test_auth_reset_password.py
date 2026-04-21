from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

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
