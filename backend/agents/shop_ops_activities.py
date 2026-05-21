"""Temporal activities for intelligent shop operational scheduling.

Three activity groups:
  1. Morning open — create/activate today's queue, notify owner
  2. Pre-close intelligence — 15 min before close, assess queue depth and decide
     whether to lock new joins, escalate HITL, or allow with warning
  3. Evening close — close the queue, notify remaining customers, send daily summary
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from temporalio import activity

from database import SessionLocal
from integrations.booking_mcp_client import BookingMCPClient
from modules.agent.models import RunStatus
from modules.agent.work_repository import AgentWorkRepository
from modules.shops.models import Shop, ShopOperatingHours

logger = logging.getLogger(__name__)


# ─── Helpers ────────────────────────────────────────────────────────────────

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _now_in_tz(tz_name: str) -> datetime:
    """Return current datetime in the given IANA timezone, falling back to UTC."""
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, Exception):
        tz = ZoneInfo("UTC")
    return datetime.now(tz)


def _minutes_until(target: time, now_local: datetime) -> float:
    """Signed minutes from now_local until target time today."""
    target_dt = now_local.replace(
        hour=target.hour,
        minute=target.minute,
        second=0,
        microsecond=0,
    )
    delta = target_dt - now_local
    return delta.total_seconds() / 60.0


def _is_operating_day(operating_days: List[int], now_local: datetime) -> bool:
    """Monday=0 … Sunday=6 matching Python weekday()."""
    return now_local.weekday() in operating_days


# ─── Activity: get shops due to open ────────────────────────────────────────

@activity.defn
async def get_shops_due_to_open_activity() -> List[Dict[str, Any]]:
    """Return shops whose open_time is within ±5 minutes of now (local time)."""
    session = SessionLocal()
    try:
        rows = (
            session.query(Shop, ShopOperatingHours)
            .join(ShopOperatingHours, Shop.id == ShopOperatingHours.shop_id)
            .filter(Shop.is_active == True, ShopOperatingHours.auto_open_queue == True)
            .all()
        )
        due: List[Dict[str, Any]] = []
        for shop, oh in rows:
            now_local = _now_in_tz(oh.timezone)
            if not _is_operating_day(oh.operating_days or list(range(7)), now_local):
                continue
            diff = _minutes_until(oh.open_time, now_local)
            if -5.0 <= diff <= 5.0:
                due.append({
                    "shop_id": shop.id,
                    "shop_name": shop.name,
                    "open_time": oh.open_time.strftime("%H:%M"),
                    "timezone": oh.timezone,
                    "avg_service_minutes": shop.average_service_time or 30,
                })
        logger.info("get_shops_due_to_open_activity: %d shops due", len(due))
        return due
    finally:
        session.close()


# ─── Activity: get all open shops for continuous capacity monitoring ─────────

@activity.defn
async def get_shops_approaching_close_activity() -> List[Dict[str, Any]]:
    """Return all shops that are currently open (between open_time and close_time).

    The pre-close intelligence activity uses queue math — not the clock — to decide
    whether to lock joins.  This means a shop that is already overloaded at 3 PM will
    be locked at 3 PM, not at 4:45 PM.  Including all open shops ensures continuous
    capacity monitoring throughout the operating day.

    A shop is considered "open" when: 0 < remaining_minutes_to_close ≤ remaining_minutes_since_open
    (i.e. current local time is between open_time and close_time).
    """
    session = SessionLocal()
    try:
        rows = (
            session.query(Shop, ShopOperatingHours)
            .join(ShopOperatingHours, Shop.id == ShopOperatingHours.shop_id)
            .filter(Shop.is_active == True)
            .all()
        )
        open_shops: List[Dict[str, Any]] = []
        for shop, oh in rows:
            now_local = _now_in_tz(oh.timezone)
            if not _is_operating_day(oh.operating_days or list(range(7)), now_local):
                continue
            mins_since_open = -_minutes_until(oh.open_time, now_local)   # positive = past open
            mins_to_close = _minutes_until(oh.close_time, now_local)     # positive = before close
            # Only include shops that are currently within their operating window
            if mins_since_open >= 0 and mins_to_close > 0:
                open_shops.append({
                    "shop_id": shop.id,
                    "shop_name": shop.name,
                    "close_time": oh.close_time.strftime("%H:%M"),
                    "timezone": oh.timezone,
                    "remaining_minutes": round(mins_to_close, 1),
                    "avg_service_minutes": shop.average_service_time or 30,
                    "auto_lock_joins": oh.auto_lock_joins,
                    "pre_close_buffer_minutes": oh.pre_close_buffer_minutes,
                })
        logger.info("get_shops_approaching_close_activity: %d shops currently open", len(open_shops))
        return open_shops
    finally:
        session.close()


# ─── Activity: get shops due to close ───────────────────────────────────────

@activity.defn
async def get_shops_due_to_close_activity() -> List[Dict[str, Any]]:
    """Return shops whose close_time is within ±5 minutes of now (local time)."""
    session = SessionLocal()
    try:
        rows = (
            session.query(Shop, ShopOperatingHours)
            .join(ShopOperatingHours, Shop.id == ShopOperatingHours.shop_id)
            .filter(Shop.is_active == True, ShopOperatingHours.auto_close_queue == True)
            .all()
        )
        due: List[Dict[str, Any]] = []
        for shop, oh in rows:
            now_local = _now_in_tz(oh.timezone)
            if not _is_operating_day(oh.operating_days or list(range(7)), now_local):
                continue
            diff = _minutes_until(oh.close_time, now_local)
            if -5.0 <= diff <= 5.0:
                due.append({
                    "shop_id": shop.id,
                    "shop_name": shop.name,
                    "close_time": oh.close_time.strftime("%H:%M"),
                    "timezone": oh.timezone,
                    "avg_service_minutes": shop.average_service_time or 30,
                })
        logger.info("get_shops_due_to_close_activity: %d shops due", len(due))
        return due
    finally:
        session.close()


# ─── Activity: open shop queue ───────────────────────────────────────────────

@activity.defn
async def open_shop_queue_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Open today's queue for a shop, notify the owner."""
    shop_id = int(payload["shop_id"])
    shop_name = str(payload.get("shop_name") or "Shop")
    try:
        workflow_id = activity.info().workflow_id
    except RuntimeError:
        workflow_id = None

    session = SessionLocal()
    repo = AgentWorkRepository(session)
    run = None
    try:
        run = repo.create_run(
            shop_id=shop_id,
            run_type="shop_open",
            trigger_source="temporal",
            execution_mode="scheduled",
            graph_thread_id=workflow_id,
            input_payload=payload,
        )
        client = BookingMCPClient()
        result = client.open_queue(shop_id)
        if result.get("error"):
            raise RuntimeError(f"Failed to open queue: {result['error']}")

        repo.create_notification(
            shop_id=shop_id,
            run_id=run.id,
            notification_type="shop_open",
            title=f"{shop_name} is now open",
            message=(
                f"Queue opened automatically at {payload.get('open_time', 'scheduled open time')}. "
                f"Queue ID: {result.get('queue_id')}. Ready to accept customers."
            ),
            severity="info",
            payload={"result": result, "generated_at": _utcnow_iso()},
        )
        repo.update_run_status(run.id, RunStatus.COMPLETED, output_payload=result)
        logger.info("Opened queue for shop %s (%s)", shop_id, result.get("action"))
        return {"ok": True, "shop_id": shop_id, **result}
    except Exception as exc:
        logger.exception("open_shop_queue_activity failed for shop %s", shop_id)
        if run is not None:
            repo.update_run_status(run.id, RunStatus.FAILED, error_message=str(exc))
        raise
    finally:
        session.close()


# ─── Activity: pre-close intelligence ────────────────────────────────────────

@activity.defn
async def pre_close_intelligence_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Continuous capacity-driven intelligence — runs on every open shop every 30 min.

    The decision to lock joins is driven entirely by queue math, not the clock:

        est_service_minutes = (serving × avg/2) + (waiting × avg)
        capacity_slack       = remaining_open_minutes − est_service_minutes

    Decision matrix (evaluated at any point during the operating day):
      slack < 0             → Queue is already over capacity → lock joins + notify owner
      0 ≤ slack < avg       → One more customer would exceed close → HITL approval request
      slack ≥ avg  AND
        remaining < buffer  → Approaching close with healthy capacity → awareness notification
      slack ≥ avg  AND
        remaining ≥ buffer  → Capacity fine, not near close → silent (no notification)

    State-change guard: if the queue is already locked (accepting_joins=False) and the
    situation hasn't improved, skip re-notifying to avoid inbox spam.
    """
    shop_id = int(payload["shop_id"])
    shop_name = str(payload.get("shop_name") or "Shop")
    remaining_minutes = float(payload.get("remaining_minutes", 15))
    avg_service_minutes = max(int(payload.get("avg_service_minutes", 30)), 1)
    auto_lock = bool(payload.get("auto_lock_joins", True))
    pre_close_buffer = int(payload.get("pre_close_buffer_minutes", 15))
    close_time = payload.get("close_time", "17:00")

    try:
        workflow_id = activity.info().workflow_id
    except RuntimeError:
        workflow_id = None

    session = SessionLocal()
    repo = AgentWorkRepository(session)
    run = None
    try:
        run = repo.create_run(
            shop_id=shop_id,
            run_type="capacity_check",
            trigger_source="temporal",
            execution_mode="scheduled",
            graph_thread_id=workflow_id,
            input_payload=payload,
        )

        # Query current queue state (includes accepting_joins flag)
        client = BookingMCPClient()
        queue_data = client.list_queue(shop_id)
        waiting_count = int(queue_data.get("waiting_count") or 0)
        serving_count = int(queue_data.get("serving_count") or 0)
        already_locked = not bool(queue_data.get("accepting_joins", True))

        # ── Capacity math ──────────────────────────────────────────────────
        # serving customer is ~halfway through their slot on average
        est_remaining_service = (serving_count * avg_service_minutes * 0.5) + (waiting_count * avg_service_minutes)
        capacity_slack = remaining_minutes - est_remaining_service  # positive = room left
        near_close = remaining_minutes <= pre_close_buffer

        # ── Determine action ───────────────────────────────────────────────
        if capacity_slack < 0:
            if already_locked:
                # Still overloaded but already locked — no new action needed
                result = {
                    "ok": True, "shop_id": shop_id, "action": "no_change",
                    "reason": "queue_already_locked",
                    "waiting_count": waiting_count, "capacity_slack_minutes": round(capacity_slack, 1),
                }
                repo.update_run_status(run.id, RunStatus.COMPLETED, output_payload=result)
                return result

            # Overloaded and NOT yet locked — act now regardless of time of day
            action = "lock_joins"
            hours_left = remaining_minutes / 60
            severity = "warning"
            title = f"Queue overloaded: {shop_name}"
            reason = (
                f"~{est_remaining_service:.0f} min of service needed but only "
                f"{remaining_minutes:.0f} min until close ({close_time}). "
                f"New joins locked."
            )
            message = (
                f"{shop_name} has {waiting_count} customer(s) waiting "
                f"(~{est_remaining_service:.0f} min to serve all). "
                f"The shop closes at {close_time} in {hours_left:.1f} h — "
                f"new joins have been locked automatically. "
                f"Existing customers will be served even if it runs past closing time."
            )

        elif capacity_slack < avg_service_minutes:
            # One more customer would exceed close time — ask the owner
            action = "hitl_approval"
            severity = "warning"
            title = f"Capacity borderline: {shop_name}"
            reason = (
                f"One more customer (~{avg_service_minutes} min) would push service past {close_time}."
            )
            message = (
                f"{shop_name} closes at {close_time} in ~{remaining_minutes:.0f} min. "
                f"{waiting_count} customer(s) waiting. "
                f"Accepting one more customer would likely push service past closing time. "
                f"Should new joins still be accepted?"
            )

        elif near_close:
            # Within the pre-close buffer window with healthy capacity — send awareness ping
            action = "pre_close_awareness"
            severity = "info"
            title = f"Approaching close: {shop_name}"
            slots_left = int(capacity_slack / avg_service_minutes)
            reason = f"~{slots_left} more customer(s) can be served before {close_time}."
            message = (
                f"{shop_name} closes at {close_time} in ~{remaining_minutes:.0f} min. "
                f"{waiting_count} customer(s) in queue. "
                f"Room for ~{slots_left} more customer(s). "
                f"Accepting new joins."
            )

        else:
            # Capacity is fine, not near close — no action, no notification
            result = {
                "ok": True, "shop_id": shop_id, "action": "no_action",
                "waiting_count": waiting_count,
                "remaining_minutes": remaining_minutes,
                "capacity_slack_minutes": round(capacity_slack, 1),
            }
            repo.update_run_status(run.id, RunStatus.COMPLETED, output_payload=result)
            logger.debug(
                "capacity_check shop=%s no_action waiting=%d slack=%.1f min remaining=%.1f min",
                shop_id, waiting_count, capacity_slack, remaining_minutes,
            )
            return result

        # ── Execute the action ─────────────────────────────────────────────
        if action == "lock_joins" and auto_lock:
            lock_result = client.lock_queue_joins(shop_id, lock=True, reason=reason)
            if lock_result.get("error"):
                logger.warning("lock_queue_joins failed for shop %s: %s", shop_id, lock_result["error"])

        # ── Notify the owner ───────────────────────────────────────────────
        notification_type_map = {
            "lock_joins": "capacity_overload_lock",
            "hitl_approval": "capacity_borderline_approval",
            "pre_close_awareness": "pre_close_awareness",
        }
        repo.create_notification(
            shop_id=shop_id,
            run_id=run.id,
            notification_type=notification_type_map[action],
            title=title,
            message=message,
            severity=severity,
            payload={
                "action": action,
                "waiting_count": waiting_count,
                "serving_count": serving_count,
                "remaining_minutes": remaining_minutes,
                "est_remaining_service_minutes": round(est_remaining_service, 1),
                "capacity_slack_minutes": round(capacity_slack, 1),
                "avg_service_minutes": avg_service_minutes,
                "close_time": close_time,
                "generated_at": _utcnow_iso(),
                **({"requires_approval": True, "approval_context": {
                    "action": "allow_join",
                    "shop_id": shop_id,
                    "description": message,
                }} if action == "hitl_approval" else {}),
            },
        )

        result = {
            "ok": True,
            "shop_id": shop_id,
            "action": action,
            "waiting_count": waiting_count,
            "serving_count": serving_count,
            "remaining_minutes": remaining_minutes,
            "capacity_slack_minutes": round(capacity_slack, 1),
        }
        repo.update_run_status(run.id, RunStatus.COMPLETED, output_payload=result)
        logger.info(
            "capacity_check shop=%s action=%s waiting=%d slack=%.1f min remaining=%.1f min",
            shop_id, action, waiting_count, capacity_slack, remaining_minutes,
        )
        return result
    except Exception as exc:
        logger.exception("capacity_check activity failed for shop %s", shop_id)
        if run is not None:
            repo.update_run_status(run.id, RunStatus.FAILED, error_message=str(exc))
        raise
    finally:
        session.close()


# ─── Activity: close shop queue ──────────────────────────────────────────────

@activity.defn
async def close_shop_queue_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Close the shop queue at end-of-day, notify owner with daily summary."""
    shop_id = int(payload["shop_id"])
    shop_name = str(payload.get("shop_name") or "Shop")
    close_time = payload.get("close_time", "17:00")

    try:
        workflow_id = activity.info().workflow_id
    except RuntimeError:
        workflow_id = None

    session = SessionLocal()
    repo = AgentWorkRepository(session)
    run = None
    try:
        run = repo.create_run(
            shop_id=shop_id,
            run_type="shop_close",
            trigger_source="temporal",
            execution_mode="scheduled",
            graph_thread_id=workflow_id,
            input_payload=payload,
        )

        # Get final queue snapshot before closing
        client = BookingMCPClient()
        queue_data = client.list_queue(shop_id)
        waiting_count = int(queue_data.get("waiting_count") or 0)
        serving_count = int(queue_data.get("serving_count") or 0)
        total_today = int(queue_data.get("total_in_queue") or 0)

        # Close the queue
        result = client.close_queue(shop_id, reason=f"Auto-close at {close_time}")
        if result.get("error"):
            raise RuntimeError(f"Failed to close queue: {result['error']}")

        # Build notification message
        if waiting_count > 0:
            msg = (
                f"{shop_name} queue closed at {close_time}. "
                f"⚠️ {waiting_count} customer(s) were still waiting. "
                f"Consider notifying them manually. Total served today: {total_today - waiting_count}."
            )
            severity = "warning"
        else:
            msg = (
                f"{shop_name} queue closed at {close_time}. "
                f"All customers served. Great day! Total served: {total_today}."
            )
            severity = "info"

        repo.create_notification(
            shop_id=shop_id,
            run_id=run.id,
            notification_type="shop_close",
            title=f"{shop_name} closed for the day",
            message=msg,
            severity=severity,
            payload={
                "result": result,
                "final_waiting_count": waiting_count,
                "final_serving_count": serving_count,
                "total_in_queue_at_close": total_today,
                "close_time": close_time,
                "generated_at": _utcnow_iso(),
            },
        )

        repo.update_run_status(run.id, RunStatus.COMPLETED, output_payload={**result, "waiting_at_close": waiting_count})
        logger.info("Closed queue for shop %s (waiting at close: %d)", shop_id, waiting_count)
        return {"ok": True, "shop_id": shop_id, "waiting_at_close": waiting_count, **result}
    except Exception as exc:
        logger.exception("close_shop_queue_activity failed for shop %s", shop_id)
        if run is not None:
            repo.update_run_status(run.id, RunStatus.FAILED, error_message=str(exc))
        raise
    finally:
        session.close()
