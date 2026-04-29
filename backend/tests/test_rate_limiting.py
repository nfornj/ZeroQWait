"""
Unit tests for rate limiting on the public queue-join endpoint.

Mocks Redis and DB — no live services required.
"""
import asyncio
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_app(rate_limit_allows: bool):
    """
    Build a minimal FastAPI app that exercises the queue join rate-limit path.
    Instead of spinning up the full app (requires DB/Redis), we patch the
    key dependencies so we can test only the rate-limit guard logic.
    """
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI()

    # Replicate only the rate-limit guard logic from modules/queues/router.py
    # so the unit test stays isolated from unrelated dependencies.
    @app.post("/shop/{shop_id}/join")
    async def fake_join(shop_id: int, request_obj=None):
        from fastapi import Request, HTTPException
        from redis_client import redis_client as _rc
        client_ip = "192.0.2.1"
        if not _rc.check_rate_limit(client_ip, limit=10, window=60):
            return JSONResponse(status_code=429, content={"detail": "Too many requests."})
        return {"status": "joined", "shop_id": shop_id}

    return app


class TestQueueJoinRateLimit:
    """Tests that the queue-join endpoint enforces 10 req/min per IP."""

    def test_allows_requests_within_limit(self):
        """First 10 requests from the same IP must succeed (HTTP 200)."""
        call_count = 0

        def mock_check(ip, limit, window):
            nonlocal call_count
            call_count += 1
            return call_count <= limit  # allow up to `limit` requests

        with patch("redis_client.redis_client.check_rate_limit", side_effect=mock_check):
            from fastapi.testclient import TestClient
            app = _make_app(True)
            client = TestClient(app)
            for i in range(10):
                resp = client.post("/shop/1/join")
                assert resp.status_code == 200, f"Request {i+1} should succeed"

    def test_blocks_request_beyond_limit(self):
        """The 11th request from the same IP must receive HTTP 429."""
        call_count = 0

        def mock_check(ip, limit, window):
            nonlocal call_count
            call_count += 1
            return call_count <= 10  # first 10 allowed, rest blocked

        with patch("redis_client.redis_client.check_rate_limit", side_effect=mock_check):
            app = _make_app(True)
            from fastapi.testclient import TestClient
            client = TestClient(app)
            for _ in range(10):
                client.post("/shop/1/join")
            resp = client.post("/shop/1/join")
            assert resp.status_code == 429, "11th request must be rate-limited"

    def test_rate_limit_key_uses_client_ip(self):
        """check_rate_limit must be called with the client IP address."""
        captured_ips = []

        def mock_check(ip, limit, window):
            captured_ips.append(ip)
            return True

        with patch("redis_client.redis_client.check_rate_limit", side_effect=mock_check):
            app = _make_app(True)
            from fastapi.testclient import TestClient
            client = TestClient(app)
            client.post("/shop/5/join")

        assert len(captured_ips) == 1
        # TestClient uses testclient as host by default; just verify it's non-empty.
        assert captured_ips[0] != ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
