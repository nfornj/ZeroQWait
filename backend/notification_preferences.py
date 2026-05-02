"""notification_preferences.py — Read / write Telegram notification preferences for a shop.

All telegram_chat_id values are stored encrypted at rest (Fernet via shared/crypto.py)
and indexed by an HMAC hash for fast reverse lookups (chat_id → shop).

Callers always receive and supply *plain* (decrypted) chat IDs — encryption and
decryption are transparent at this layer.

Functions:
    get_telegram_prefs(shop_id, db)         → TelegramPrefs | None
    save_chat_id(shop_id, chat_id, db)      → None  (persists after handshake)
    disconnect_telegram(shop_id, db)        → None
    set_notifications_enabled(shop_id, enabled, db) → None
    find_shop_by_chat_id(plain_chat_id, db) → Shop | None
"""

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from modules.shops.models import Shop
from shared.crypto import encrypt_text, decrypt_text, hmac_text

logger = logging.getLogger(__name__)


@dataclass
class TelegramPrefs:
    shop_id: int
    chat_id: Optional[str]   # plaintext (decrypted) — None when not connected
    connected: bool
    enabled: bool


# ── Read ──────────────────────────────────────────────────────────────────────

def get_telegram_prefs(shop_id: int, db: Session) -> Optional[TelegramPrefs]:
    """Return Telegram preferences for a shop, or None if the shop doesn't exist."""
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        return None

    plain_chat_id: Optional[str] = None
    if shop.telegram_chat_id:
        try:
            plain_chat_id = decrypt_text(shop.telegram_chat_id)
        except Exception:
            # Stored plaintext (pre-encryption migration) — use as-is
            plain_chat_id = shop.telegram_chat_id

    return TelegramPrefs(
        shop_id=shop_id,
        chat_id=plain_chat_id,
        connected=bool(plain_chat_id),
        enabled=bool(shop.telegram_notifications_enabled),
    )


# ── Write ─────────────────────────────────────────────────────────────────────

def save_chat_id(shop_id: int, chat_id: str, db: Session) -> None:
    """Encrypt and persist the owner's Telegram chat_id; flip connected to True.

    Also clears the one-time connect token so it can never be reused.
    Stores an HMAC hash alongside the encrypted value for O(1) reverse lookup.
    """
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise ValueError(f"Shop {shop_id} not found")

    shop.telegram_chat_id = encrypt_text(chat_id)
    shop.telegram_chat_id_hash = hmac_text(chat_id)
    shop.telegram_notifications_enabled = True

    # Invalidate the one-time token
    shop.telegram_connect_token = None
    shop.telegram_connect_token_expires_at = None

    db.commit()
    logger.info("Telegram chat_id saved for shop %s (encrypted at rest)", shop_id)

    # Cache reverse lookup in Redis for fast webhook routing
    try:
        from redis_client import redis_client
        redis_client.setex(f"zq:tg_chat:{chat_id}", 86400, str(shop_id))  # 24-hour TTL
    except Exception:
        pass  # Redis failure is non-fatal here


def disconnect_telegram(shop_id: int, db: Session) -> None:
    """Remove all Telegram linkage from a shop."""
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        return

    # Invalidate Redis reverse-lookup cache before clearing
    if shop.telegram_chat_id:
        try:
            plain = decrypt_text(shop.telegram_chat_id)
        except Exception:
            plain = shop.telegram_chat_id
        if plain:
            try:
                from redis_client import redis_client
                redis_client.delete(f"zq:tg_chat:{plain}")
            except Exception:
                pass

    shop.telegram_chat_id = None
    shop.telegram_chat_id_hash = None
    shop.telegram_notifications_enabled = False
    shop.telegram_connect_token = None
    shop.telegram_connect_token_expires_at = None
    db.commit()


def set_notifications_enabled(shop_id: int, enabled: bool, db: Session) -> None:
    """Enable or disable Telegram notifications without touching the chat_id."""
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        return
    shop.telegram_notifications_enabled = enabled
    db.commit()


# ── Reverse lookup ────────────────────────────────────────────────────────────

def find_shop_by_chat_id(plain_chat_id: str, db: Session) -> Optional[Shop]:
    """Find the shop that owns the given plain Telegram chat_id.

    Lookup order (fast → slow):
    1. Redis TTL cache (chat_id → shop_id)
    2. DB HMAC-hash index (deterministic — no decrypt needed)
    3. Fallback: plaintext comparison (pre-encryption rows, dev/test only)
    """
    # 1. Redis fast path
    try:
        from redis_client import redis_client
        cached = redis_client.get(f"zq:tg_chat:{plain_chat_id}")
        if cached:
            shop_id = int(cached.decode() if isinstance(cached, bytes) else cached)
            shop = db.query(Shop).filter(
                Shop.id == shop_id,
                Shop.telegram_chat_id.isnot(None),
            ).first()
            if shop:
                return shop
    except Exception:
        pass

    # 2. HMAC-hash index (O(1), no decryption)
    hash_val = hmac_text(plain_chat_id)
    if hash_val:
        shop = db.query(Shop).filter(Shop.telegram_chat_id_hash == hash_val).first()
        if shop:
            try:
                from redis_client import redis_client
                redis_client.setex(f"zq:tg_chat:{plain_chat_id}", 86400, str(shop.id))
            except Exception:
                pass
            return shop

    # 3. Fallback: plaintext (pre-encryption migration; dev/test only)
    shop = db.query(Shop).filter(Shop.telegram_chat_id == plain_chat_id).first()
    if shop:
        # Opportunistically migrate to encrypted storage
        try:
            save_chat_id(shop.id, plain_chat_id, db)
        except Exception:
            pass
        return db.query(Shop).filter(Shop.id == shop.id).first()

    return None
