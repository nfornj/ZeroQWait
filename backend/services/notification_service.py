"""Notification service stubs — SMS, email, and push notification placeholders.

When NOTIFICATIONS_ENABLED=true, routes through configured providers.
When NOTIFICATIONS_ENABLED=false (default), logs the notification and returns success.

Providers will be plugged in later (Twilio for SMS, SendGrid for email, FCM for push).
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

NOTIFICATIONS_ENABLED = os.getenv("NOTIFICATIONS_ENABLED", "false").lower() in ("true", "1", "yes")


class NotificationService:
    """Unified notification dispatch — SMS, email, push."""

    def __init__(self):
        self.enabled = NOTIFICATIONS_ENABLED

    def send_sms(self, phone: str, message: str, shop_id: Optional[int] = None) -> Dict[str, Any]:
        """Send an SMS notification to a customer."""
        if not self.enabled:
            logger.info("[notify-stub] SMS to %s: %s (shop_id=%s)", phone, message[:60], shop_id)
            return {"sent": False, "channel": "sms", "reason": "notifications_disabled"}

        # Future: Twilio integration
        logger.info("[notify] SMS to %s: %s", phone, message[:60])
        return {"sent": True, "channel": "sms", "phone": phone}

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        shop_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send an email notification."""
        if not self.enabled:
            logger.info("[notify-stub] Email to %s: %s (shop_id=%s)", to_email, subject, shop_id)
            return {"sent": False, "channel": "email", "reason": "notifications_disabled"}

        # Future: SendGrid / SES integration
        logger.info("[notify] Email to %s: %s", to_email, subject)
        return {"sent": True, "channel": "email", "to": to_email}

    def send_push(
        self,
        user_id: int,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a push notification to a user's device."""
        if not self.enabled:
            logger.info("[notify-stub] Push to user_%s: %s", user_id, title)
            return {"sent": False, "channel": "push", "reason": "notifications_disabled"}

        # Future: FCM integration
        logger.info("[notify] Push to user_%s: %s", user_id, title)
        return {"sent": True, "channel": "push", "user_id": user_id}

    # ── Convenience methods for common notifications ──────────────

    def notify_queue_position(self, phone: str, shop_name: str, position: int, wait_minutes: int, shop_id: int) -> Dict[str, Any]:
        """Notify customer of their queue position."""
        message = (
            f"Hi! You're #{position} in line at {shop_name}. "
            f"Estimated wait: ~{wait_minutes} min. We'll let you know when you're next!"
        )
        return self.send_sms(phone, message, shop_id=shop_id)

    def notify_your_turn(self, phone: str, shop_name: str, shop_id: int) -> Dict[str, Any]:
        """Notify customer it's their turn."""
        message = f"It's your turn at {shop_name}! Please head to the service area."
        return self.send_sms(phone, message, shop_id=shop_id)

    def notify_appointment_confirmation(
        self,
        phone: Optional[str],
        email: Optional[str],
        customer_name: str,
        service_name: str,
        scheduled_time: str,
        shop_name: str,
        shop_id: int,
    ) -> Dict[str, Any]:
        """Send appointment confirmation via SMS and/or email."""
        results = {}
        message = (
            f"Hi {customer_name}, your appointment for {service_name} at {shop_name} "
            f"is confirmed for {scheduled_time}. See you then!"
        )
        if phone:
            results["sms"] = self.send_sms(phone, message, shop_id=shop_id)
        if email:
            results["email"] = self.send_email(
                email,
                f"Appointment Confirmed — {shop_name}",
                message,
                shop_id=shop_id,
            )
        return results

    def notify_appointment_reminder(
        self,
        phone: Optional[str],
        email: Optional[str],
        customer_name: str,
        service_name: str,
        scheduled_time: str,
        shop_name: str,
        shop_id: int,
    ) -> Dict[str, Any]:
        """Send appointment reminder (typically 24h or 1h before)."""
        results = {}
        message = (
            f"Reminder: {customer_name}, your appointment for {service_name} "
            f"at {shop_name} is coming up at {scheduled_time}."
        )
        if phone:
            results["sms"] = self.send_sms(phone, message, shop_id=shop_id)
        if email:
            results["email"] = self.send_email(
                email,
                f"Appointment Reminder — {shop_name}",
                message,
                shop_id=shop_id,
            )
        return results

    async def send_telegram_async(
        self,
        chat_id: str,
        text: str,
        shop_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a Telegram message to a connected shop owner.

        Always attempted regardless of NOTIFICATIONS_ENABLED — Telegram
        connectivity depends only on TELEGRAM_BOT_TOKEN being set.
        """
        import telegram_service as tg

        if not tg.is_configured():
            logger.debug(
                "[notify-stub] Telegram to %s: %s (shop_id=%s)", chat_id, text[:60], shop_id
            )
            return {"sent": False, "channel": "telegram", "reason": "bot_not_configured"}

        ok = await tg.send_message(chat_id, text)
        if ok:
            logger.info("[notify] Telegram to %s (shop_id=%s): sent", chat_id, shop_id)
        return {"sent": ok, "channel": "telegram", "chat_id": chat_id}


# Singleton
notification_service = NotificationService()
