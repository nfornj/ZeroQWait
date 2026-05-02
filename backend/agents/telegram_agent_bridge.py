"""
Bridge: Telegram owner message → Supervisor Agent → response text.

Invokes the LangGraph supervisor graph with an owner's Telegram message and
returns the final response text. Uses the same checkpoint thread as the
dashboard chat so conversation context is shared.

The runnable is created lazily and cached as a module-level singleton.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_BRIDGE_RUNNABLE = None
_BRIDGE_CHECKPOINTER_CM = None
_BRIDGE_CHECKPOINTER = None


def _get_runnable():
    global _BRIDGE_RUNNABLE, _BRIDGE_CHECKPOINTER_CM, _BRIDGE_CHECKPOINTER
    if _BRIDGE_RUNNABLE is None:
        from agents.supervisor import create_supervisor_runnable
        from agents.checkpoints import get_sync_checkpoint_saver

        _BRIDGE_CHECKPOINTER_CM = get_sync_checkpoint_saver()
        _BRIDGE_CHECKPOINTER = _BRIDGE_CHECKPOINTER_CM.__enter__()
        if hasattr(_BRIDGE_CHECKPOINTER, "setup"):
            _BRIDGE_CHECKPOINTER.setup()
        _BRIDGE_RUNNABLE = create_supervisor_runnable(checkpointer=_BRIDGE_CHECKPOINTER)
        logger.info("Telegram agent bridge: supervisor runnable initialized")
    return _BRIDGE_RUNNABLE


async def handle_telegram_message(
    shop_id: int,
    owner_user_id: int,
    message: str,
) -> str:
    """
    Invoke the supervisor graph with the owner's Telegram message.
    Returns the final response text (plain string, suitable for Telegram).
    """
    from agents.state import AgentState
    from agents.checkpoints import build_checkpoint_config
    from langchain_core.messages import HumanMessage

    runnable = _get_runnable()
    thread_id = f"tenant_{shop_id}_{owner_user_id}"
    config = build_checkpoint_config(thread_id=thread_id)

    initial_state = AgentState(
        messages=[HumanMessage(content=message)],
        tenant_id=shop_id,
        user_id=owner_user_id,
        current_agent="supervisor",
        pending_approval=None,
        tool_results=None,
        needs_human_input=False,
    )

    final_text: str = ""

    def _run_sync() -> None:
        nonlocal final_text
        try:
            for update in runnable.stream(
                initial_state, config=config, stream_mode="updates"
            ):
                if not isinstance(update, dict):
                    continue
                for node_name, out in update.items():
                    if node_name == "synthesize_response" and isinstance(out, dict):
                        msgs = out.get("messages") or []
                        if msgs:
                            final_text = getattr(msgs[-1], "content", "") or ""
        except Exception as exc:
            exc_name = type(exc).__name__
            if "interrupt" not in exc_name.lower():
                logger.error("Telegram agent bridge stream error: %s", exc)
                raise

    await asyncio.to_thread(_run_sync)
    return final_text or "_No response. Please try again or use the dashboard._"
