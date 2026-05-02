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

Business logic is split into dedicated modules:
  telegram_onboarding.py   — token generation and deep links
  telegram_webhook.py      — update processing (start, callbacks, messages)
  notification_preferences.py — encrypted preference CRUD
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

import telegram_client as tgc
import telegram_service as tg
from database import get_db
from shared.auth_utils import get_current_user
from modules.shops.models import Shop
from notification_preferences import (
    get_telegram_prefs,
    disconnect_telegram,
    set_notifications_enabled,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class TelegramStatusResponse(BaseModel):
    configured: bool    # Bot token is set server-side
    connected: bool     # This shop has a linked chat_id
    enabled: bool       # Notifications are enabled
    chat_id: Optional[str] = None   # Masked for display (last 6 digits only)


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


def _mask_chat_id(chat_id: Optional[str]) -> Optional[str]:
    """Show only the last 6 digits of the chat_id for the dashboard display."""
    if not chat_id:
        return None
    return f"...{chat_id[-6:]}" if len(chat_id) > 6 else chat_id


# ── Shop-scoped endpoints ─────────────────────────────────────────────────────

@router.get("/shops/{shop_id}/telegram/status", response_model=TelegramStatusResponse)
async def telegram_status(
    shop_id: int,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current Telegram connection status for a shop."""
    _get_owned_shop(shop_id, current_user, db)  # ownership check
    prefs = get_telegram_prefs(shop_id, db)
    if not prefs:
        raise HTTPException(status_code=404, detail="Shop not found")

    return TelegramStatusResponse(
        configured=tgc.is_configured(),
        connected=prefs.connected,
        enabled=prefs.enabled,
        chat_id=_mask_chat_id(prefs.chat_id),
    )


@router.post("/shops/{shop_id}/telegram/connect", response_model=TelegramConnectResponse)
async def telegram_connect(
    shop_id: int,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a one-time connection token and deep-link for the owner."""
    if not tgc.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Telegram integration is not enabled on this server. "
                   "Contact your administrator.",
        )
    _get_owned_shop(shop_id, current_user, db)  # ownership check

    from telegram_onboarding import generate_connect_link
    link = await generate_connect_link(shop_id=shop_id, user_id=current_user.id, db=db)

    return TelegramConnectResponse(
        token=link.token,
        bot_username=link.bot_username,
        deep_link=link.deep_link,
        expires_in=link.expires_in,
    )


@router.delete("/shops/{shop_id}/telegram/disconnect", status_code=204)
async def telegram_disconnect(
    shop_id: int,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unlink the owner's Telegram account from this shop."""
    _get_owned_shop(shop_id, current_user, db)
    disconnect_telegram(shop_id, db)


@router.post("/shops/{shop_id}/telegram/toggle", status_code=204)
async def telegram_toggle(
    shop_id: int,
    body: TelegramToggleRequest,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enable or disable Telegram notifications for a shop."""
    _get_owned_shop(shop_id, current_user, db)
    prefs = get_telegram_prefs(shop_id, db)
    if not prefs or not prefs.connected:
        raise HTTPException(
            status_code=400, detail="Connect Telegram before toggling notifications."
        )
    set_notifications_enabled(shop_id, body.enabled, db)


# ── Webhook endpoint ──────────────────────────────────────────────────────────

@router.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Receive all updates pushed by Telegram's servers (webhook mode).

    Security: validates X-Telegram-Bot-Api-Secret-Token before processing.
    Delegates all business logic to telegram_webhook.process_update().
    Always returns {"ok": True} — Telegram ignores the body but retries on
    non-2xx status codes, so we must not surface errors here.
    """
    secret = tg.TELEGRAM_WEBHOOK_SECRET
    if secret:
        if x_telegram_bot_api_secret_token != secret:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

    try:
        update = await request.json()
    except Exception:
        return {"ok": True}  # malformed body — ignore silently

    try:
        from telegram_webhook import process_update
        await process_update(update, db)
    except Exception as exc:
        logger.error("Telegram webhook processing error: %s", exc)
        # Do NOT re-raise — Telegram would retry indefinitely on 5xx

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
    ok = await tgc.set_webhook(body.webhook_url)
    if not ok:
        raise HTTPException(
            status_code=500, detail="Failed to register webhook with Telegram."
        )
    return {"ok": True, "webhook_url": body.webhook_url}


