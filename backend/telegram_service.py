"""
Telegram Bot Service — lightweight httpx-based Telegram Bot API client.

No additional library needed — httpx is already in the project.

Key functions:
  is_configured()    → bool: True if TELEGRAM_BOT_TOKEN is set
  send_message()     → bool: send a text message to a chat
  get_bot_info()     → dict: getMe result
  set_webhook()      → bool: register public webhook URL with Telegram
  delete_webhook()   → bool: remove registered webhook
"""

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")


def is_configured() -> bool:
    """Return True if the bot token is set."""
    return bool(TELEGRAM_BOT_TOKEN)


def _base() -> str:
    return f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


async def send_message(
    chat_id: str | int,
    text: str,
    parse_mode: str = "Markdown",
) -> bool:
    """Send a text message to a Telegram chat. Returns True on success."""
    if not TELEGRAM_BOT_TOKEN:
        logger.debug("TELEGRAM_BOT_TOKEN not set — skipping send_message")
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_base()}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
            )
        data = resp.json()
        if resp.status_code == 200 and data.get("ok"):
            return True
        logger.warning(
            "Telegram sendMessage failed (%s): %s", resp.status_code, resp.text[:300]
        )
        return False
    except Exception as exc:
        logger.error("Telegram send_message error: %s", exc)
        return False


async def get_bot_info() -> Dict[str, Any]:
    """Return the bot's getMe result, or {} on error."""
    if not TELEGRAM_BOT_TOKEN:
        return {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{_base()}/getMe")
        data = resp.json()
        return data.get("result", {}) if data.get("ok") else {}
    except Exception:
        return {}


async def set_webhook(webhook_url: str) -> bool:
    """Register a public HTTPS webhook URL with Telegram."""
    if not TELEGRAM_BOT_TOKEN:
        return False
    try:
        payload: Dict[str, Any] = {
            "url": webhook_url,
            "allowed_updates": ["message"],
        }
        if TELEGRAM_WEBHOOK_SECRET:
            payload["secret_token"] = TELEGRAM_WEBHOOK_SECRET
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{_base()}/setWebhook", json=payload)
        ok = resp.json().get("ok", False)
        if ok:
            logger.info("Telegram webhook registered: %s", webhook_url)
        else:
            logger.warning("Telegram setWebhook failed: %s", resp.text)
        return ok
    except Exception as exc:
        logger.error("Telegram setWebhook error: %s", exc)
        return False


async def delete_webhook() -> bool:
    """Remove the registered webhook (switches bot to polling mode)."""
    if not TELEGRAM_BOT_TOKEN:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{_base()}/deleteWebhook")
        return resp.json().get("ok", False)
    except Exception:
        return False


async def format_approval_notification(
    action: str, details: str, action_id: str
) -> str:
    """Format an approval notification for Telegram Markdown."""
    detail_line = f"*Details:* {details}\n" if details else ""
    return (
        f"🔔 *Approval Required*\n\n"
        f"*Action:* {action}\n"
        f"{detail_line}\n"
        f"Reply with:\n"
        f"✅ `/approve {action_id}` — to approve\n"
        f"❌ `/deny {action_id}` — to reject\n\n"
        f"_Or handle it from your ZeroQwait dashboard._"
    )
