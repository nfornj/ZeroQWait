"""
Telegram integration router.

Shop-scoped endpoints:
  GET    /api/shops/{shop_id}/telegram/status       — check connection status
  POST   /api/shops/{shop_id}/telegram/connect      — generate deep-link token
  DELETE /api/shops/{shop_id}/telegram/disconnect   — unlink Telegram account
  POST   /api/shops/{shop_id}/telegram/toggle       — enable/disable notifications

Platform endpoints:
  POST   /api/telegram/webhook                      — receive Telegram Bot API updates
  POST   /api/telegram/setup-webhook                — register webhook URL (super_admin only)
"""

import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

import telegram_service as tg
from database import get_db
from shared.auth_utils import get_current_user
from modules.shops.models import Shop
from redis_client import redis_client

logger = logging.getLogger(__name__)

router = APIRouter()

_CONNECT_TOKEN_TTL = 600        # 10 minutes (seconds) — single-use
_CONNECT_KEY_PREFIX = "zq:tg_connect:"


# ── Schemas ───────────────────────────────────────────────────────────────────

class TelegramStatusResponse(BaseModel):
    configured: bool    # Bot token is set server-side
    connected: bool     # This shop has a linked chat_id
    enabled: bool       # Notifications are enabled
    chat_id: Optional[str] = None


class TelegramConnectResponse(BaseModel):
    token: str
    bot_username: str
    deep_link: str
    expires_in: int     # seconds until token expires


class TelegramToggleRequest(BaseModel):
    enabled: bool


class SetupWebhookRequest(BaseModel):
    webhook_url: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_owned_shop(shop_id: int, current_user: Any, db: Session) -> Shop:
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    if shop.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your shop")
    return shop


# ── Shop-scoped endpoints ─────────────────────────────────────────────────────

@router.get("/shops/{shop_id}/telegram/status", response_model=TelegramStatusResponse)
async def telegram_status(
    shop_id: int,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current Telegram connection status for a shop."""
    shop = _get_owned_shop(shop_id, current_user, db)
    return TelegramStatusResponse(
        configured=tg.is_configured(),
        connected=bool(shop.telegram_chat_id),
        enabled=bool(shop.telegram_notifications_enabled),
        chat_id=shop.telegram_chat_id,
    )


@router.post("/shops/{shop_id}/telegram/connect", response_model=TelegramConnectResponse)
async def telegram_connect(
    shop_id: int,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a one-time connection token and deep-link for the owner."""
    if not tg.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Telegram integration is not enabled on this server.",
        )
    _get_owned_shop(shop_id, current_user, db)  # ownership check

    token = uuid.uuid4().hex[:20]
    redis_client.setex(
        f"{_CONNECT_KEY_PREFIX}{token}",
        _CONNECT_TOKEN_TTL,
        f"{shop_id}:{current_user.id}",
    )

    bot_info = await tg.get_bot_info()
    bot_username = bot_info.get("username", "ZeroQwaitBot")
    deep_link = f"https://t.me/{bot_username}?start={token}"

    return TelegramConnectResponse(
        token=token,
        bot_username=bot_username,
        deep_link=deep_link,
        expires_in=_CONNECT_TOKEN_TTL,
    )


@router.delete("/shops/{shop_id}/telegram/disconnect", status_code=204)
async def telegram_disconnect(
    shop_id: int,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unlink the owner's Telegram account from this shop."""
    shop = _get_owned_shop(shop_id, current_user, db)
    shop.telegram_chat_id = None
    shop.telegram_notifications_enabled = False
    db.commit()


@router.post("/shops/{shop_id}/telegram/toggle", status_code=204)
async def telegram_toggle(
    shop_id: int,
    body: TelegramToggleRequest,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enable or disable Telegram notifications for a shop."""
    shop = _get_owned_shop(shop_id, current_user, db)
    if not shop.telegram_chat_id:
        raise HTTPException(
            status_code=400, detail="Connect Telegram before toggling notifications."
        )
    shop.telegram_notifications_enabled = body.enabled
    db.commit()


# ── Webhook endpoint ───────────────────────────────────────────────────────────

@router.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Receive updates pushed by Telegram's servers (webhook mode)."""
    if tg.TELEGRAM_WEBHOOK_SECRET:
        if x_telegram_bot_api_secret_token != tg.TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

    update: Dict[str, Any] = await request.json()
    await _process_update(update, db)
    return {"ok": True}


@router.post("/telegram/setup-webhook")
async def setup_webhook(
    body: SetupWebhookRequest,
    current_user: Any = Depends(get_current_user),
):
    """Register a public webhook URL with Telegram. Super admin only."""
    role = getattr(current_user, "role", "")
    if role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")
    ok = await tg.set_webhook(body.webhook_url)
    if not ok:
        raise HTTPException(
            status_code=500, detail="Failed to register webhook with Telegram"
        )
    return {"ok": True, "webhook_url": body.webhook_url}


# ── Update processor ──────────────────────────────────────────────────────────

async def _process_update(update: Dict[str, Any], db: Session) -> None:
    """Route a Telegram update to the correct handler."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return  # ignore non-message updates (polls, channel posts, etc.)

    chat_id = str(message.get("chat", {}).get("id", ""))
    text: str = (message.get("text") or "").strip()

    if not chat_id or not text:
        return

    if text.startswith("/start"):
        await _handle_start(chat_id, text, db)
    elif text.lower().startswith("/approve ") or text.lower().startswith("/deny "):
        await _handle_approval_command(chat_id, text, db)
    elif text.startswith("/"):
        await tg.send_message(
            chat_id,
            "Unknown command. Just send a message to chat with your AI team!",
        )
    else:
        await _handle_chat_message(chat_id, text, db)


async def _handle_start(chat_id: str, text: str, db: Session) -> None:
    """Handle /start {token} — link owner's Telegram to their shop."""
    parts = text.split(maxsplit=1)
    token = parts[1].strip() if len(parts) > 1 else ""

    if not token:
        await tg.send_message(
            chat_id,
            "👋 Welcome to ZeroQwait!\n\nUse the *Connect Telegram* button in your shop settings to link your account.",
        )
        return

    key = f"{_CONNECT_KEY_PREFIX}{token}"
    raw = redis_client.get(key)

    if not raw:
        await tg.send_message(
            chat_id,
            "❌ This link has expired or is invalid.\n\nPlease generate a new one from your shop settings.",
        )
        return

    try:
        raw_str = raw.decode() if isinstance(raw, bytes) else str(raw)
        shop_id_str, _ = raw_str.split(":", 1)
        shop_id = int(shop_id_str)
    except (ValueError, AttributeError):
        await tg.send_message(chat_id, "❌ Invalid token format. Please try again.")
        return

    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        await tg.send_message(chat_id, "❌ Shop not found. Please contact support.")
        return

    shop.telegram_chat_id = chat_id
    shop.telegram_notifications_enabled = True
    db.commit()
    redis_client.delete(key)  # single-use — delete immediately

    await tg.send_message(
        chat_id,
        f"✅ *{shop.name}* is now connected to Telegram!\n\n"
        "You'll receive:\n"
        "🔔 Approval requests\n"
        "📊 Business summaries on demand\n"
        "💬 Chat with your AI operations team\n\n"
        "Just send me a message anytime.",
    )


async def _handle_approval_command(chat_id: str, text: str, db: Session) -> None:
    """Handle /approve {action_id} or /deny {action_id}."""
    shop = db.query(Shop).filter(Shop.telegram_chat_id == chat_id).first()
    if not shop:
        await tg.send_message(
            chat_id,
            "❌ Account not linked. Reconnect from your shop settings.",
        )
        return

    parts = text.split(maxsplit=1)
    cmd = parts[0].lstrip("/").lower()  # "approve" or "deny"
    action_id = parts[1].strip() if len(parts) > 1 else ""

    if not action_id:
        await tg.send_message(
            chat_id,
            "Usage:\n`/approve <action_id>`\n`/deny <action_id>`",
        )
        return

    approved = cmd == "approve"
    try:
        from agents.chat_service import _record_approval_decision

        await _record_approval_decision(shop.id, action_id, approved)
        verb = "approved ✅" if approved else "rejected ❌"
        await tg.send_message(chat_id, f"Action has been *{verb}*.")
    except Exception as exc:
        logger.error("Telegram approval command error: %s", exc)
        await tg.send_message(
            chat_id, "⚠️ Could not process decision. Please use the dashboard."
        )


async def _handle_chat_message(chat_id: str, text: str, db: Session) -> None:
    """Route an owner's Telegram message to the supervisor agent and reply."""
    shop = db.query(Shop).filter(Shop.telegram_chat_id == chat_id).first()
    if not shop:
        await tg.send_message(
            chat_id,
            "❌ Account not linked. Reconnect from your shop settings.",
        )
        return

    # Acknowledge quickly so the owner knows the message was received
    await tg.send_message(chat_id, "⏳ _Thinking…_")

    try:
        from agents.telegram_agent_bridge import handle_telegram_message

        response = await handle_telegram_message(
            shop_id=shop.id,
            owner_user_id=shop.owner_id,
            message=text,
        )
        await tg.send_message(chat_id, response or "_No response generated._")
    except Exception as exc:
        logger.error("Telegram chat message error: %s", exc)
        await tg.send_message(
            chat_id,
            "⚠️ Something went wrong. Please try again or use the dashboard.",
        )
