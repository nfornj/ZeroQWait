"""Queue email notifications sent to customers via AWS SES.

Two flows:
  1. Queue join — customer receives a confirmation with their position and a
     unique link to track their status without logging in.
  2. You're next — customer receives an alert when they reach the front of the
     queue (status transitions to BEING_SERVED).

Emails are designed to be called with asyncio.create_task() so they never
block the HTTP response.  All failures are logged but not re-raised.
"""

import logging
import os
from services.aws_client import send_email, is_ses_configured

logger = logging.getLogger(__name__)


async def send_queue_join_email(
    customer_email: str,
    customer_name: str,
    shop_name: str,
    position: int,
    estimated_wait_min: int | None,
    status_url: str,
) -> None:
    """Send a queue-joined confirmation email to the customer.

    Args:
        customer_email: Recipient address.
        customer_name: Full name as entered by the customer.
        shop_name: Display name of the shop.
        position: The customer's current position in the queue (1-indexed).
        estimated_wait_min: Estimated minutes until being served, or None if unknown.
        status_url: Public URL the customer can visit to check live status.
    """
    if not is_ses_configured():
        logger.debug("SES not configured — skipping queue join email to %s", customer_email)
        return

    first_name = customer_name.split()[0] if customer_name else "there"
    wait_line = (
        f"**Estimated wait:** {estimated_wait_min} minute{'s' if estimated_wait_min != 1 else ''}"
        if estimated_wait_min is not None
        else ""
    )

    subject = f"You're in the queue at {shop_name} — position #{position}"
    body = f"""
## You're in the queue at {shop_name}!

Hi {first_name},

You've been added to the queue at **{shop_name}**.

| | |
|---|---|
| **Your position** | #{position} |
{f'| **Estimated wait** | ~{estimated_wait_min} min |' if estimated_wait_min is not None else ''}

---

### Track your status

You'll receive another email when it's almost your turn. You can also check your live position at any time:

[**Check my queue status →**]({status_url})

---

*Reply to this email or ask staff if you need to leave early.*
*— ZeroQwait*
""".strip()

    try:
        await send_email(to_address=customer_email, subject=subject, markdown_text=body)
        logger.info("Queue join email sent to %s (position #%d, shop=%s)", customer_email, position, shop_name)
    except Exception as exc:
        logger.error("Failed to send queue join email to %s: %s", customer_email, exc)


async def send_youre_next_email(
    customer_email: str,
    customer_name: str,
    shop_name: str,
    service_name: str | None,
    status_url: str,
) -> None:
    """Send a "you're next" notification email to the customer.

    Args:
        customer_email: Recipient address.
        customer_name: Full name as entered by the customer.
        shop_name: Display name of the shop.
        service_name: Booked service name, or None if not specified.
        status_url: The customer's status link (for reference).
    """
    if not is_ses_configured():
        logger.debug("SES not configured — skipping you're next email to %s", customer_email)
        return

    first_name = customer_name.split()[0] if customer_name else "there"
    service_line = f"\n**Service:** {service_name}\n" if service_name else ""

    subject = f"It's almost your turn at {shop_name}!"
    body = f"""
## It's your turn, {first_name}!

You're **now being served** at **{shop_name}**. Please head to the counter now.
{service_line}
---

[**View your queue status**]({status_url})

*— ZeroQwait*
""".strip()

    try:
        await send_email(to_address=customer_email, subject=subject, markdown_text=body)
        logger.info("You're-next email sent to %s (shop=%s)", customer_email, shop_name)
    except Exception as exc:
        logger.error("Failed to send you're-next email to %s: %s", customer_email, exc)
