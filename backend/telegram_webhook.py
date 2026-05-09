"""telegram_webhook.py — Process all incoming Telegram Bot API updates.

This module is the single entry point for all inbound Telegram traffic.
The HTTP layer (header validation, JSON parsing) is handled in telegram_router.py.
This module handles the business logic.

Handles:
  /start {token}           — owner onboarding handshake (links Telegram ↔ shop)
  callback_query           — inline button tap (✅ Approve / ❌ Decline / 📲 Defer)
  /approve {id}            — text-based approval command (legacy fallback)
  /deny {id}               — text-based rejection command (legacy fallback)
  owner free-text message  — routed to the LangGraph supervisor agent
  new customer message     — "Which shop?" prompt + routing

Security:
  - The X-Telegram-Bot-Api-Secret-Token header is validated by telegram_router.py
    *before* this module is ever called. Do not call process_update without it.
  - Tokens are single-use and expire in 10 minutes.
  - telegram_chat_id is stored encrypted at rest (see notification_preferences.py).
  - No internal error details are ever sent to the Telegram chat user.
"""

import asyncio
import logging
import os
from typing import Any, Optional

from sqlalchemy.orm import Session

import telegram_client as tgc
from notification_preferences import save_chat_id, find_shop_by_chat_id
from redis_client import redis_client
from modules.shops.models import Shop

logger = logging.getLogger(__name__)

_REDIS_PREFIX: str = "zq:tg_connect:"
_OWNER_REPLY_TIMEOUT_SECONDS: float = float(os.getenv("TELEGRAM_OWNER_REPLY_TIMEOUT_SECONDS", "120"))


# ── Entry point ───────────────────────────────────────────────────────────────

async def process_update(update: dict[str, Any], db: Session) -> None:
    """Dispatch a Telegram update to the appropriate handler.

    Called by telegram_router.telegram_webhook() after header validation.
    """

    # Inline button tap
    if "callback_query" in update:
        await _handle_callback_query(update["callback_query"], db)
        return

    message = update.get("message") or update.get("edited_message")
    if not message:
        return  # polls, channel posts, stickers — ignore

    chat_id: str = str(message.get("chat", {}).get("id", ""))
    text: str = (message.get("text") or "").strip()

    if not chat_id or not text:
        return

    if text.startswith("/start"):
        await _handle_start(chat_id, text, db)
    elif text.lower().startswith("/approve ") or text.lower().startswith("/deny "):
        await _handle_text_approval_command(chat_id, text, db)
    elif text.startswith("/"):
        await tgc.send_text(
            chat_id,
            "I don't recognise that command. Just send me a message — your AI team is listening!",
        )
    else:
        await _handle_free_text(chat_id, message, text, db)


# ── /start {token} handshake ──────────────────────────────────────────────────

async def _handle_start(chat_id: str, text: str, db: Session) -> None:
    """Link the owner's Telegram account to their shop via the one-time token."""
    parts = text.split(maxsplit=1)
    token = parts[1].strip() if len(parts) > 1 else ""

    if not token:
        await tgc.send_text(
            chat_id,
            "👋 Welcome to ZeroQwait!\n\n"
            "Tap *Connect Telegram* in your shop dashboard to link your account.",
        )
        return

    # ── Resolve token → shop_id ───────────────────────────────────────────────
    key = f"{_REDIS_PREFIX}{token}"
    raw = redis_client.get(key)
    shop: Optional[Shop] = None

    if raw:
        try:
            raw_str = raw.decode() if isinstance(raw, bytes) else str(raw)
            shop_id = int(raw_str.split(":", 1)[0])
            shop = db.query(Shop).filter(Shop.id == shop_id).first()
        except (ValueError, AttributeError):
            pass
    else:
        # Redis may have expired; check DB fallback
        shop = db.query(Shop).filter(Shop.telegram_connect_token == token).first()
        if shop:
            from datetime import datetime, timezone
            exp = shop.telegram_connect_token_expires_at
            if exp:
                # Ensure timezone-aware comparison
                exp_utc = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
                if exp_utc < datetime.now(timezone.utc):
                    shop = None  # expired

    if not shop:
        existing_shop = find_shop_by_chat_id(chat_id, db)
        if existing_shop:
            await tgc.send_text(
                chat_id,
                f"✅ *{existing_shop.name}* is already connected.\n\n"
                "You can just send me a message whenever you need something.",
            )
            return
        await tgc.send_text(
            chat_id,
            "❌ This link has expired.\n\n"
            "Please tap *Connect Telegram* in your dashboard to generate a fresh one.",
        )
        return

    # ── Persist encrypted chat_id ─────────────────────────────────────────────
    save_chat_id(shop.id, chat_id, db)

    # ── Invalidate token ──────────────────────────────────────────────────────
    redis_client.delete(key)

    # ── Confirm to owner ──────────────────────────────────────────────────────
    await tgc.send_text(
        chat_id,
        f"✅ *{shop.name}* is now connected!\n\n"
        "You'll receive:\n"
        "🔔 Approval requests — tap one button to decide\n"
        "📊 Daily business briefings\n"
        "💬 Chat with your AI operations team anytime\n\n"
        "Just send me a message whenever you need something.",
    )


# ── Inline button callback ────────────────────────────────────────────────────

async def _handle_callback_query(callback_query: dict[str, Any], db: Session) -> None:
    """Process an inline button tap from the owner."""
    callback_id: str = callback_query.get("id", "")
    chat_id: str = str(callback_query.get("from", {}).get("id", ""))
    data: str = callback_query.get("data", "")

    if not data or ":" not in data:
        await tgc.answer_callback_query(callback_id, "Unknown action.")
        return

    action, action_id = data.split(":", 1)

    shop = find_shop_by_chat_id(chat_id, db)
    if not shop:
        await tgc.answer_callback_query(
            callback_id, "Account not linked. Please reconnect from the dashboard."
        )
        return

    if action in ("approve", "decline"):
        approved = action == "approve"
        try:
            from agents.chat_service import _record_approval_decision
            await _record_approval_decision(shop.id, action_id, approved)

            label = "approved ✅" if approved else "declined ❌"
            await tgc.answer_callback_query(callback_id, f"Decision recorded — {label}")

            # Edit the original message to remove buttons and show outcome
            msg = callback_query.get("message", {})
            await tgc.edit_message_reply_markup(
                chat_id=msg.get("chat", {}).get("id", chat_id),
                message_id=msg.get("message_id", 0),
                text=f"{'✅ Approved' if approved else '❌ Declined'} — decision recorded.",
            )

        except Exception as exc:
            logger.error("Telegram callback approval error: %s", exc)
            await tgc.answer_callback_query(
                callback_id,
                "Could not record decision. Please use the dashboard.",
            )

    elif action == "defer":
        await tgc.answer_callback_query(callback_id, "Got it — I'll keep it in the inbox.")
        msg = callback_query.get("message", {})
        await tgc.edit_message_reply_markup(
            chat_id=msg.get("chat", {}).get("id", chat_id),
            message_id=msg.get("message_id", 0),
            text="📲 *You'll handle this from the dashboard.* It's waiting in your Agent Inbox.",
        )

    else:
        await tgc.answer_callback_query(callback_id, "Unknown action.")


# ── Text-based /approve /deny (legacy fallback) ───────────────────────────────

async def _handle_text_approval_command(chat_id: str, text: str, db: Session) -> None:
    shop = find_shop_by_chat_id(chat_id, db)
    if not shop:
        await tgc.send_text(chat_id, "❌ Account not linked. Reconnect from your shop settings.")
        return

    parts = text.split(maxsplit=1)
    cmd = parts[0].lstrip("/").lower()
    action_id = parts[1].strip() if len(parts) > 1 else ""

    if not action_id:
        await tgc.send_text(chat_id, "Usage:\n`/approve <action_id>`\n`/deny <action_id>`")
        return

    approved = cmd == "approve"
    try:
        from agents.chat_service import _record_approval_decision
        await _record_approval_decision(shop.id, action_id, approved)
        verb = "approved ✅" if approved else "declined ❌"
        await tgc.send_text(chat_id, f"Action has been *{verb}*.")
    except Exception as exc:
        logger.error("Telegram text approval command error: %s", exc)
        await tgc.send_text(chat_id, "⚠️ Could not process. Please use the dashboard.")


# ── Free-text message routing ─────────────────────────────────────────────────

async def _handle_free_text(
    chat_id: str,
    message: dict[str, Any],
    text: str,
    db: Session,
) -> None:
    """Route a plain text message to the owner agent or the new-customer flow."""
    shop = find_shop_by_chat_id(chat_id, db)

    if shop:
        # Known owner — route to LangGraph supervisor agent
        await tgc.send_text(chat_id, "⏳ _Thinking…_")
        try:
            from agents.telegram_agent_bridge import handle_telegram_message
            response = await asyncio.wait_for(
                handle_telegram_message(
                    shop_id=shop.id,
                    owner_user_id=shop.owner_id,
                    message=text,
                ),
                timeout=_OWNER_REPLY_TIMEOUT_SECONDS,
            )
            await tgc.send_text(chat_id, response or "No response generated.", parse_mode=None)
        except asyncio.TimeoutError:
            logger.warning("Telegram owner message timed out for shop %s", shop.id)
            await tgc.send_text(
                chat_id,
                "⏱️ I'm still working on that request. Please try again in a moment or use the dashboard chat for a fuller reply.",
            )
        except Exception as exc:
            logger.error("Telegram owner message routing error: %s", exc)
            await tgc.send_text(
                chat_id,
                "⚠️ Something went wrong. Please try again or use the dashboard.",
            )
        return

    # Unknown user — new customer or misdirected message
    await _handle_unknown_user(chat_id, message, db)


_TELEGRAM_DEV_SHOP_ID: Optional[int] = (
    int(os.getenv("TELEGRAM_DEV_SHOP_ID"))
    if os.getenv("TELEGRAM_DEV_SHOP_ID", "").strip().isdigit()
    else None
)


async def _handle_unknown_user(
    chat_id: str,
    message: dict[str, Any],
    db: Session,
) -> None:
    """Handle a message from a Telegram user whose chat_id is not linked to any shop.

    In development/test environments a single `TELEGRAM_DEV_SHOP_ID` env var can be
    set to auto-link unknown users to a specific shop, removing the need for the
    /start {token} handshake during local testing.

    In production this env var must NOT be set — all owners must go through the
    proper /start {token} handshake from the dashboard.
    """
    first_name: str = message.get("from", {}).get("first_name", "there")

    # ── Dev/test shortcut: auto-link to the configured test shop ──────────────
    if _TELEGRAM_DEV_SHOP_ID is not None:
        shop = db.query(Shop).filter(Shop.id == _TELEGRAM_DEV_SHOP_ID).first()
        if shop:
            # Persist the link so subsequent messages skip this path
            save_chat_id(shop.id, chat_id, db)
            await tgc.send_text(
                chat_id,
                f"🔧 *Dev mode* — auto-linked to *{shop.name}*.\n\n"
                "Your messages will now route to this shop's AI agent.\n"
                "_To disable this, remove `TELEGRAM_DEV_SHOP_ID` from your environment._",
            )
            # Now route the original message immediately
            await tgc.send_text(chat_id, "⏳ _Thinking…_")
            try:
                from agents.telegram_agent_bridge import handle_telegram_message
                text: str = (message.get("text") or "").strip()
                response = await asyncio.wait_for(
                    handle_telegram_message(
                        shop_id=shop.id,
                        owner_user_id=shop.owner_id,
                        message=text,
                    ),
                    timeout=_OWNER_REPLY_TIMEOUT_SECONDS,
                )
                await tgc.send_text(chat_id, response or "No response generated.", parse_mode=None)
            except Exception as exc:
                logger.error("Telegram dev-mode auto-link message error: %s", exc)
                await tgc.send_text(chat_id, "⚠️ Something went wrong. Please try again.")
            return

    # ── Production: guide the user to link or find a shop ────────────────────
    await tgc.send_text(
        chat_id,
        f"Hi {first_name}! 👋\n\n"
        "I'm the ZeroQwait assistant bot.\n\n"
        "*Are you a shop owner?*\n"
        "Open your ZeroQwait dashboard → Settings → *Connect Telegram*, then tap the link to link your account.\n\n"
        "*Looking for a specific shop?*\n"
        "Reply with the shop name and I'll help you find them.",
    )


async def _prompt_new_customer(chat_id: str, message: dict[str, Any]) -> None:
    """Kept for backwards compatibility — delegates to _handle_unknown_user."""
    # This function is no longer called directly; _handle_unknown_user replaced it.
    # Retained so any external callers don't break.
    first_name: str = message.get("from", {}).get("first_name", "there")
    await tgc.send_text(
        chat_id,
        f"Hi {first_name}! 👋\n\n"
        "I'm the ZeroQwait assistant bot.\n\n"
        "*Are you a shop owner?*\n"
        "Open your ZeroQwait dashboard → Settings → *Connect Telegram*, then tap the link.\n\n"
        "*Looking for a specific shop?*\n"
        "Reply with the shop name and I'll help you find them.",
    )
