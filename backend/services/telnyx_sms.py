"""Telnyx transactional SMS helpers for customer notifications."""

from __future__ import annotations

import logging
import re

import httpx

from observability.metrics import sms_delivery_total
from shared.secrets import getenv, load_infisical_secrets

logger = logging.getLogger(__name__)

load_infisical_secrets()

_TELNYX_MESSAGES_URL = "https://api.telnyx.com/v2/messages"


def is_telnyx_configured() -> bool:
    return bool(getenv("TELNYX_API_KEY") and getenv("TELNYX_FROM_NUMBER"))


def _record_sms(sent: bool) -> None:
    sms_delivery_total.labels(status="sent" if sent else "failed").inc()


def _strip_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


async def send_transactional_sms(
    phone_number: str,
    message: str,
    *,
    record_metrics: bool = True,
) -> bool:
    """Send a transactional SMS through Telnyx.

    Returns True on success and False on any configuration or delivery error.
    Errors are logged so notification failures are observable without breaking
    queue, appointment, or receipt workflows.
    """
    api_key = getenv("TELNYX_API_KEY", "") or ""
    from_number = getenv("TELNYX_FROM_NUMBER", "") or ""
    messaging_profile_id = getenv("TELNYX_MESSAGING_PROFILE_ID", "") or ""

    if not api_key or not from_number:
        logger.warning("Telnyx SMS is not configured; set TELNYX_API_KEY and TELNYX_FROM_NUMBER")
        if record_metrics:
            _record_sms(False)
        return False

    text = _strip_markdown(message)
    if len(text) > 400:
        text = text[:397] + "..."

    payload: dict[str, str] = {
        "from": from_number,
        "to": phone_number,
        "text": text,
    }
    if messaging_profile_id:
        payload["messaging_profile_id"] = messaging_profile_id

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(_TELNYX_MESSAGES_URL, headers=headers, json=payload)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("Telnyx SMS failed status=%s body=%s", exc.response.status_code, exc.response.text[:300])
        if record_metrics:
            _record_sms(False)
        return False
    except Exception as exc:
        logger.error("Telnyx SMS unexpected error: %s", exc)
        if record_metrics:
            _record_sms(False)
        return False

    logger.info("Telnyx SMS sent to %s", phone_number)
    if record_metrics:
        _record_sms(True)
    return True
