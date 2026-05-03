"""telegram_polling.py — local long-polling worker for Telegram test environments.

Use polling mode for local Docker setups where Telegram cannot reach localhost
with a public webhook URL. This worker reuses telegram_webhook.process_update()
so webhook mode and polling mode behave the same after an update is received.
"""

import asyncio
import logging
import os
from typing import Optional

import telegram_client as tgc
from database import SessionLocal

logger = logging.getLogger(__name__)

TELEGRAM_MODE: str = os.getenv("TELEGRAM_MODE", "webhook").strip().lower()
TELEGRAM_POLL_TIMEOUT: int = int(os.getenv("TELEGRAM_POLL_TIMEOUT", "30"))
TELEGRAM_POLL_RETRY_DELAY: float = float(os.getenv("TELEGRAM_POLL_RETRY_DELAY", "3"))

_polling_task: Optional[asyncio.Task] = None
_stop_event: Optional[asyncio.Event] = None
_last_update_id: Optional[int] = None


def is_polling_enabled() -> bool:
    """Return True when Telegram should run in local polling mode."""
    return TELEGRAM_MODE == "polling" and tgc.is_configured()


async def start_polling() -> None:
    """Start the Telegram polling worker if enabled."""
    global _polling_task, _stop_event

    if not is_polling_enabled():
        return

    if _polling_task and not _polling_task.done():
        return

    # Polling and webhooks are mutually exclusive in Telegram. Clear the
    # webhook first so getUpdates can receive the same traffic locally.
    ok = await tgc.delete_webhook(drop_pending_updates=False)
    if not ok:
        logger.warning("Telegram polling mode could not delete the existing webhook.")

    _stop_event = asyncio.Event()
    _polling_task = asyncio.create_task(_poll_loop(_stop_event), name="telegram-polling")
    logger.info("Telegram polling worker started.")


async def stop_polling() -> None:
    """Stop the Telegram polling worker cleanly on app shutdown."""
    global _polling_task, _stop_event

    if not _polling_task:
        return

    if _stop_event:
        _stop_event.set()

    try:
        await asyncio.wait_for(_polling_task, timeout=TELEGRAM_POLL_TIMEOUT + 5)
    except asyncio.TimeoutError:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
    finally:
        _polling_task = None
        _stop_event = None
        logger.info("Telegram polling worker stopped.")


async def _poll_loop(stop_event: asyncio.Event) -> None:
    """Fetch updates from Telegram and pass them into the existing processor."""
    global _last_update_id

    from telegram_webhook import process_update

    while not stop_event.is_set():
        try:
            updates = await tgc.get_updates(
                offset=_last_update_id,
                timeout=TELEGRAM_POLL_TIMEOUT,
                allowed_updates=["message", "callback_query"],
            )

            if not updates:
                continue

            for update in updates:
                if stop_event.is_set():
                    break

                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    _last_update_id = update_id + 1

                db = SessionLocal()
                try:
                    await process_update(update, db)
                except Exception as exc:
                    logger.error("Telegram polling update error: %s", exc)
                finally:
                    db.close()

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Telegram polling loop retrying after error: %s", exc)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=TELEGRAM_POLL_RETRY_DELAY)
            except asyncio.TimeoutError:
                pass
