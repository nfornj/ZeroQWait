"""telegram_client.py — ZeroQWait Telegram Bot API client.

Single responsibility: send messages and answer callbacks via the Telegram HTTP API.
Uses httpx (already in dependencies). No third-party Telegram library required.

All public functions accept a *plain* (decrypted) chat_id (int or str).
Encryption / decryption of the stored chat_id happens in notification_preferences.py.

Public API:
    send_text(chat_id, text, parse_mode="Markdown") -> bool
    send_with_buttons(chat_id, text, buttons) -> bool
    answer_callback_query(callback_query_id, text="") -> bool
    is_configured() -> bool

The TELEGRAM_BOT_TOKEN is read once at import time from environment variables.
It is never logged, never returned in API responses, and never exposed to owners.
"""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
_WEBHOOK_SECRET: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")


def is_configured() -> bool:
    """Return True if TELEGRAM_BOT_TOKEN is present."""
    return bool(_BOT_TOKEN)


def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{_BOT_TOKEN}/{method}"


async def send_text(
    chat_id: str | int,
    text: str,
    parse_mode: str = "Markdown",
) -> bool:
    """Send a plain text message.  Returns True on success."""
    if not _BOT_TOKEN:
        logger.debug("Telegram not configured — skipping send_text")
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _api("sendMessage"),
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
        logger.warning("Telegram sendMessage failed (%s): %s", resp.status_code, resp.text[:300])
        return False
    except Exception as exc:
        logger.error("Telegram send_text error: %s", exc)
        return False


async def send_with_buttons(
    chat_id: str | int,
    text: str,
    buttons: list[list[dict[str, Any]]],
    parse_mode: str = "Markdown",
) -> bool:
    """Send a message with an InlineKeyboard.

    ``buttons`` is a 2-D list of button rows. Each button dict must have:
        {"text": "<label>", "callback_data": "<payload>"}

    Example:
        buttons = [
            [
                {"text": "✅ Approve", "callback_data": f"approve:{action_id}"},
                {"text": "❌ Decline", "callback_data": f"decline:{action_id}"},
            ],
            [{"text": "📲 I'll Handle It", "callback_data": f"defer:{action_id}"}],
        ]
    """
    if not _BOT_TOKEN:
        logger.debug("Telegram not configured — skipping send_with_buttons")
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _api("sendMessage"),
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                    "reply_markup": {"inline_keyboard": buttons},
                },
            )
        data = resp.json()
        if resp.status_code == 200 and data.get("ok"):
            return True
        logger.warning(
            "Telegram sendMessage (buttons) failed (%s): %s", resp.status_code, resp.text[:300]
        )
        return False
    except Exception as exc:
        logger.error("Telegram send_with_buttons error: %s", exc)
        return False


async def answer_callback_query(callback_query_id: str, text: str = "") -> bool:
    """Acknowledge a button tap.

    Telegram requires this to dismiss the loading spinner on the owner's phone.
    ``text`` is optional — shows a brief toast notification.
    """
    if not _BOT_TOKEN:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                _api("answerCallbackQuery"),
                json={"callback_query_id": callback_query_id, "text": text},
            )
        return resp.json().get("ok", False)
    except Exception as exc:
        logger.error("Telegram answerCallbackQuery error: %s", exc)
        return False


async def edit_message_reply_markup(
    chat_id: str | int,
    message_id: int,
    text: str,
) -> None:
    """Replace an existing message's text and remove its inline keyboard.

    Called after a button is tapped so the original message shows the outcome
    (e.g. "✅ Approved") instead of the stale action buttons.
    Best-effort — errors are silently swallowed.
    """
    if not _BOT_TOKEN:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                _api("editMessageText"),
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "reply_markup": {"inline_keyboard": []},
                },
            )
    except Exception:
        pass  # best-effort


async def set_webhook(webhook_url: str) -> bool:
    """Register a public HTTPS webhook URL with Telegram.

    Includes callback_query in allowed_updates so inline button taps reach us.
    """
    if not _BOT_TOKEN:
        return False
    try:
        payload: dict[str, Any] = {
            "url": webhook_url,
            "allowed_updates": ["message", "callback_query"],
        }
        if _WEBHOOK_SECRET:
            payload["secret_token"] = _WEBHOOK_SECRET
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(_api("setWebhook"), json=payload)
        ok = resp.json().get("ok", False)
        if ok:
            logger.info("Telegram webhook registered: %s", webhook_url)
        else:
            logger.warning("Telegram setWebhook failed: %s", resp.text[:300])
        return ok
    except Exception as exc:
        logger.error("Telegram setWebhook error: %s", exc)
        return False


async def get_bot_info() -> dict[str, Any]:
    """Return the bot's getMe result, or {} on error."""
    if not _BOT_TOKEN:
        return {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_api("getMe"))
        data = resp.json()
        return data.get("result", {}) if data.get("ok") else {}
    except Exception:
        return {}
