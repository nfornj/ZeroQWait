"""telegram_onboarding.py — Generate one-time connect tokens and Telegram deep links.

Called when the owner clicks "Connect Telegram" in the dashboard.

The token is:
  - Cryptographically random (secrets.token_hex — 32 hex chars)
  - Stored in Redis for fast O(1) lookup (auto-expires after 10 minutes)
  - Stored in the shops table for durability (telegram_connect_token + expires_at)
  - Single-use: cleared immediately after a successful /start handshake
  - If expired or not found, the owner sees a friendly "please try again" message

Usage:
    from telegram_onboarding import generate_connect_link
    link = await generate_connect_link(shop_id=42, user_id=7, db=db)
    # link.deep_link = "https://t.me/ZeroQwaitBot?start=abc123..."
"""

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

import telegram_client as tgc
from modules.shops.models import Shop
from redis_client import redis_client

logger = logging.getLogger(__name__)

_TOKEN_TTL_SECONDS: int = 600  # 10 minutes
_REDIS_PREFIX: str = "zq:tg_connect:"


@dataclass
class ConnectLink:
    token: str
    bot_username: str
    deep_link: str
    expires_in: int  # seconds until the token expires


async def generate_connect_link(shop_id: int, user_id: int, db: Session) -> ConnectLink:
    """Generate a single-use connect token and return the Telegram deep link.

    Raises RuntimeError if TELEGRAM_BOT_TOKEN is not set.
    """
    if not tgc.is_configured():
        raise RuntimeError(
            "Telegram integration is not enabled on this server. "
            "Set the TELEGRAM_BOT_TOKEN environment variable."
        )

    token = secrets.token_hex(16)  # 32-char hex, cryptographically random

    # ── Persist in DB for durability ─────────────────────────────────────────
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if shop:
        shop.telegram_connect_token = token
        shop.telegram_connect_token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=_TOKEN_TTL_SECONDS
        )
        db.commit()
        logger.info("Connect token generated for shop %s (expires in %ss)", shop_id, _TOKEN_TTL_SECONDS)

    # ── Also store in Redis for fast webhook lookup ───────────────────────────
    redis_client.set(
        f"{_REDIS_PREFIX}{token}",
        f"{shop_id}:{user_id}",
        ttl=_TOKEN_TTL_SECONDS,
    )

    # ── Build deep link ───────────────────────────────────────────────────────
    bot_info = await tgc.get_bot_info()
    bot_username: str = bot_info.get("username", "ZeroQwaitBot")
    deep_link = f"https://t.me/{bot_username}?start={token}"

    return ConnectLink(
        token=token,
        bot_username=bot_username,
        deep_link=deep_link,
        expires_in=_TOKEN_TTL_SECONDS,
    )
