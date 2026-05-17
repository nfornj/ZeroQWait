"""
observability/middleware.py — FastAPI HTTP instrumentation middleware.

Records per-request HTTP metrics (latency + status) for all routes.
Path labels are normalised to bounded groups so Prometheus cardinality
stays low even with ID-bearing paths like /api/shops/42/....
"""

import re
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from observability.metrics import http_requests_total, http_request_duration

# ── Path normalisation rules ───────────────────────────────────────────────────
# Patterns are applied in order; the first match wins.
# The goal is to collapse high-cardinality path segments (IDs) while keeping
# enough structure to be useful in dashboards.

_NORMALISATION_RULES: list[tuple[re.Pattern[str], str]] = [
    # Agent v2 routes
    (re.compile(r"^/api/v2/agent/chat/stream"), "/api/v2/agent/chat/stream"),
    (re.compile(r"^/api/v2/agent/chat"),         "/api/v2/agent/chat"),
    (re.compile(r"^/api/v2/agent/approve"),       "/api/v2/agent/approve"),
    (re.compile(r"^/api/v2/agent/history"),       "/api/v2/agent/history"),
    (re.compile(r"^/api/v2/agent/pending"),       "/api/v2/agent/pending"),
    (re.compile(r"^/api/v2/agent/feed"),          "/api/v2/agent/feed"),
    (re.compile(r"^/api/v2/agent/notifications"), "/api/v2/agent/notifications"),
    (re.compile(r"^/api/v2/agent/health"),        "/api/v2/agent/health"),
    (re.compile(r"^/api/v2/agent/"),              "/api/v2/agent/other"),
    # Legacy agent routes
    (re.compile(r"^/api/agent/master/chat/stream"), "/api/agent/chat/stream"),
    (re.compile(r"^/api/agent/master/chat"),         "/api/agent/chat"),
    (re.compile(r"^/api/agent/health"),              "/api/agent/health"),
    # Voice
    (re.compile(r"^/api/voice/tts"),        "/api/voice/tts"),
    (re.compile(r"^/api/voice/transcribe"), "/api/voice/transcribe"),
    (re.compile(r"^/api/voice/"),           "/api/voice/other"),
    # Auth
    (re.compile(r"^/api/auth/"), "/api/auth"),
    # Queue / shops (collapse IDs)
    (re.compile(r"^/api/queues/shop/\d+"), "/api/queues/shop/{id}"),
    (re.compile(r"^/api/queues/\d+"),       "/api/queues/{id}"),
    (re.compile(r"^/api/shops/my-shops"),   "/api/shops/my-shops"),
    (re.compile(r"^/api/shops/\d+"),        "/api/shops/{id}"),
    (re.compile(r"^/api/shops/"),           "/api/shops"),
    # Analytics
    (re.compile(r"^/api/analytics/"), "/api/analytics"),
    # Employees
    (re.compile(r"^/api/employees/"), "/api/employees"),
    # Services
    (re.compile(r"^/api/services/"), "/api/services"),
    # Users
    (re.compile(r"^/api/users/"), "/api/users"),
    # Prometheus scrape endpoint — skip recording to avoid self-referential loops
    (re.compile(r"^/metrics"), "__skip__"),
    # Health / docs — bundle as infra
    (re.compile(r"^/api/docs|^/api/openapi|^/docs/"), "__infra__"),
]


def _normalise_path(path: str) -> str:
    for pattern, label in _NORMALISATION_RULES:
        if pattern.match(path):
            return label
    return "/other"


class AgentMetricsMiddleware(BaseHTTPMiddleware):
    """Records HTTP latency and status code for every request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path_group = _normalise_path(request.url.path)

        # Do not instrument Prometheus scrape endpoint or infra paths to avoid
        # cardinality bloat and circular metrics.
        if path_group in ("__skip__", "__infra__"):
            return await call_next(request)

        method = request.method
        start = time.perf_counter()

        response: Response
        try:
            response = await call_next(request)
            status = str(response.status_code)
        except Exception:
            status = "500"
            http_requests_total.labels(
                method=method, path_group=path_group, status_code=status
            ).inc()
            http_request_duration.labels(
                method=method, path_group=path_group
            ).observe(time.perf_counter() - start)
            raise

        http_requests_total.labels(
            method=method, path_group=path_group, status_code=status
        ).inc()
        http_request_duration.labels(
            method=method, path_group=path_group
        ).observe(time.perf_counter() - start)

        return response
