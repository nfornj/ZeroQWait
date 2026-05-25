import asyncio
import importlib

import httpx


def test_telnyx_transactional_sms_payload(monkeypatch):
    monkeypatch.setenv("INFISICAL_ENABLED", "false")
    monkeypatch.setenv("TELNYX_API_KEY", "test-key")
    monkeypatch.setenv("TELNYX_FROM_NUMBER", "+15555550123")

    from services import telnyx_sms

    importlib.reload(telnyx_sms)

    calls = []

    class FakeResponse:
        status_code = 202
        text = "{}"

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            calls.append({"url": url, "headers": headers, "json": json})
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    ok = asyncio.run(telnyx_sms.send_transactional_sms("+14165551234", "**Queue** update"))

    assert ok is True
    assert calls[0]["url"] == "https://api.telnyx.com/v2/messages"
    assert calls[0]["headers"]["Authorization"] == "Bearer test-key"
    assert calls[0]["json"] == {
        "from": "+15555550123",
        "to": "+14165551234",
        "text": "Queue update",
    }


def test_generic_sms_prefers_telnyx(monkeypatch):
    monkeypatch.setenv("INFISICAL_ENABLED", "false")
    monkeypatch.setenv("TELNYX_API_KEY", "test-key")
    monkeypatch.setenv("TELNYX_FROM_NUMBER", "+15555550123")

    from services import aws_client, telnyx_sms

    importlib.reload(telnyx_sms)
    importlib.reload(aws_client)

    calls = []

    async def fake_send(phone_number, message, *, record_metrics=True):
        calls.append((phone_number, message, record_metrics))
        return True

    monkeypatch.setattr(telnyx_sms, "send_transactional_sms", fake_send)

    ok = asyncio.run(aws_client.send_sms("+14165551234", "Queue update"))

    assert ok is True
    assert calls == [("+14165551234", "Queue update", True)]
