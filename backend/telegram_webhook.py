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

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

import telegram_client as tgc
from notification_preferences import save_chat_id, find_shop_by_chat_id
from redis_client import redis_client
from modules.shops.models import Shop

logger = logging.getLogger(__name__)

_REDIS_PREFIX: str = "zq:tg_connect:"


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
            response = await handle_telegram_message(
                shop_id=shop.id,
                owner_user_id=shop.owner_id,
                message=text,
            )
            await tgc.send_text(chat_id, response or "_No response generated._")
        except Exception as exc:
            logger.error("Telegram owner message routing error: %s", exc)
            await tgc.send_text(
                chat_id,
                "⚠️ Something went wrong. Please try again or use the dashboard.",
            )
        return

    # Unknown user — new customer or misdirected message
    await _prompt_new_customer(chat_id, message)


async def _prompt_new_customer(chat_id: str, message: dict[str, Any]) -> None:
    """Greet an unknown Telegram user and ask which shop they want to contact.

    Step 7 of the spec: when a customer (not an owner) messages the bot, ask
    which shop they are reaching out to. The full customer routing system
    (linking Telegram customer IDs to shop_customers rows) will be implemented
    when the customer-facing booking flow is built out.
    """
    first_name: str = message.get("from", {}).get("first_name", "there")

    await tgc.send_text(
        chat_id,
        f"Hi {first_name}! 👋\n\n"
        "I'm the ZeroQwait assistant bot.\n\n"
        "Which shop are you reaching out to? Reply with the shop name and "
        "I'll connect you with their team.",
    )
