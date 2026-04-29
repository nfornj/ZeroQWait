"""Runtime host resolution helpers for local shell vs container contexts."""

from __future__ import annotations

import logging
import os
import socket
from typing import Optional

logger = logging.getLogger(__name__)

_LOCAL_SERVICE_FALLBACKS = {
    "db": "localhost",
    "redis": "localhost",
    "odoo": "localhost",
    "booking-mcp": "localhost",
    "finance-mcp": "localhost",
    "hr-mcp": "localhost",
}


def _is_container_runtime() -> bool:
    return os.path.exists("/.dockerenv") or bool(os.getenv("KUBERNETES_SERVICE_HOST"))


def resolve_runtime_host(host: Optional[str]) -> str:
    """Resolve compose service aliases to localhost when running outside containers."""
    normalized = str(host or "").strip()
    if not normalized:
        return "localhost"

    if _is_container_runtime() or normalized in {"localhost", "127.0.0.1"}:
        return normalized

    try:
        socket.getaddrinfo(normalized, None)
        return normalized
    except OSError:
        fallback = _LOCAL_SERVICE_FALLBACKS.get(normalized)
        if fallback:
            logger.info(
                "Runtime host '%s' is not resolvable outside container runtime; using '%s' instead.",
                normalized,
                fallback,
            )
            return fallback
        return normalized