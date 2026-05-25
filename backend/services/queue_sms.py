"""queue_sms.py — Customer-facing SMS notifications via Telnyx or AWS SNS.

Fallback note: AWS SNS SMS sandbox only sends to *verified* destination phone
numbers. Verify numbers in the AWS console:
  SNS → Text messaging (SMS) → Sandbox destination phone numbers → Add phone number

To exit sandbox and send to any number, request production access in that same
SNS console section. The same IAM credentials used for SES work here — the user
only needs the `sns:Publish` action on `*`.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from services.aws_client import is_sns_configured, send_sms

logger = logging.getLogger(__name__)


def _normalize_phone(phone: str) -> Optional[str]:
    """Coerce a phone string to E.164 format best-effort.

    Handles common North American formats:
        (416) 555-1234  →  +14165551234
        416-555-1234    →  +14165551234
        14165551234     →  +14165551234
        +14165551234    →  +14165551234 (passthrough)

    Returns None if the result doesn't look like a plausible number.
    """
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) >= 7:
        # International — trust what's there, just ensure leading +
        if phone.lstrip().startswith("+"):
            return f"+{digits}"
    return None


async def send_queue_join_sms(
    customer_phone: str,
    customer_name: str,
    shop_name: str,
    position: int,
    estimated_wait_min: Optional[int],
    status_url: str,
) -> None:
    """Send a queue-join confirmation SMS."""
    if not is_sns_configured():
        logger.debug("SMS provider not configured — skipping queue join SMS to %s", customer_phone)
        return

    e164 = _normalize_phone(customer_phone)
    if not e164:
        logger.warning("queue_sms: unrecognised phone format %r — SMS skipped", customer_phone)
        return

    first_name = customer_name.split()[0] if customer_name else "there"
    wait_part = f" Est. wait: {estimated_wait_min} min." if estimated_wait_min is not None else ""
    message = (
        f"Hi {first_name}, you're #{position} in line at {shop_name}.{wait_part} "
        f"Track your spot: {status_url}"
    )

    try:
        await send_sms(phone_number=e164, markdown_text=message)
        logger.info("Queue join SMS sent to %s (shop=%s, pos=%d)", e164, shop_name, position)
    except Exception as exc:
        logger.error("Failed to send queue join SMS to %s: %s", e164, exc)


async def send_youre_next_sms(
    customer_phone: str,
    customer_name: str,
    shop_name: str,
    service_name: Optional[str],
    status_url: str,
) -> None:
    """Send an 'it's your turn' SMS."""
    if not is_sns_configured():
        logger.debug("SMS provider not configured — skipping you're-next SMS to %s", customer_phone)
        return

    e164 = _normalize_phone(customer_phone)
    if not e164:
        logger.warning("queue_sms: unrecognised phone format %r — SMS skipped", customer_phone)
        return

    first_name = customer_name.split()[0] if customer_name else "there"
    service_part = f" for your {service_name}" if service_name else ""
    message = (
        f"Hi {first_name}, it's your turn{service_part} at {shop_name}! "
        f"Head to the counter now. {status_url}"
    )

    try:
        await send_sms(phone_number=e164, markdown_text=message)
        logger.info("You're-next SMS sent to %s (shop=%s)", e164, shop_name)
    except Exception as exc:
        logger.error("Failed to send you're-next SMS to %s: %s", e164, exc)


async def send_appointment_confirmation_sms(
    customer_phone: str,
    customer_name: str,
    shop_name: str,
    service_name: str,
    scheduled_date: str,
    scheduled_time: str,
    status_url: str,
) -> None:
    """Send an appointment booking confirmation SMS."""
    if not is_sns_configured():
        logger.debug("SMS provider not configured — skipping appointment confirmation SMS to %s", customer_phone)
        return

    e164 = _normalize_phone(customer_phone)
    if not e164:
        logger.warning("queue_sms: unrecognised phone format %r — SMS skipped", customer_phone)
        return

    first_name = customer_name.split()[0] if customer_name else "there"
    message = (
        f"Hi {first_name}, your {service_name} at {shop_name} is confirmed: "
        f"{scheduled_date} at {scheduled_time}. Manage: {status_url}"
    )

    try:
        await send_sms(phone_number=e164, markdown_text=message)
        logger.info(
            "Appointment confirmation SMS sent to %s (service=%s, shop=%s)",
            e164, service_name, shop_name,
        )
    except Exception as exc:
        logger.error("Failed to send appointment confirmation SMS to %s: %s", e164, exc)
