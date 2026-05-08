from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from database import SessionLocal
from db_interface import DatabaseInterface
from modules.shops.models import Shop
from redis_client import redis_client

from .tools import finance_tools

logger = logging.getLogger(__name__)

BRIEFING_CACHE_KEY = "briefing:latest"
BRIEFING_ALERT_HISTORY_KEY = "briefing:alert_history"
BRIEFING_CACHE_TTL_SECONDS = 900
BRIEFING_ALERT_HISTORY_TTL_SECONDS = 7 * 24 * 60 * 60


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_alert(alert: Dict[str, Any], created_at: Optional[str] = None) -> Dict[str, Any]:
    return {
        "severity": str(alert.get("severity") or "info"),
        "title": str(alert.get("title") or "Alert"),
        "body": str(alert.get("body") or ""),
        "created_at": created_at or str(alert.get("created_at") or _utcnow_iso()),
    }


def build_briefing_alerts(
    metrics: Dict[str, Any],
    pending_count: int,
    active_services: int,
) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    queue_length = int(metrics.get("queue_length", 0) or 0)
    wait_minutes = int(metrics.get("estimated_wait_minutes", 0) or 0)
    active_employees = int(metrics.get("active_employees", 0) or 0)

    if queue_length >= 8 or wait_minutes >= 45:
        alerts.append(
            {
                "severity": "warning",
                "title": "Queue pressure is building",
                "body": f"There are {queue_length} people waiting with an estimated wait of {wait_minutes} minutes.",
            }
        )

    if active_employees <= 1 and queue_length >= 4:
        alerts.append(
            {
                "severity": "warning",
                "title": "Staffing is thin for current demand",
                "body": "Only one active staff member is detected while the queue is still moving.",
            }
        )

    if pending_count > 0:
        alerts.append(
            {
                "severity": "info",
                "title": "Owner decisions are waiting",
                "body": f"You have {pending_count} approval request{'s' if pending_count != 1 else ''} that can unblock agent work.",
            }
        )

    if active_services == 0:
        alerts.append(
            {
                "severity": "warning",
                "title": "No active services are published",
                "body": "Customers may struggle to book or understand what your shop currently offers.",
            }
        )

    if not alerts:
        alerts.append(
            {
                "severity": "success",
                "title": "Operations look steady",
                "body": "No urgent issues were detected from the latest queue, staffing, and approval signals.",
            }
        )

    created_at = _utcnow_iso()
    return [_normalize_alert(alert, created_at=created_at) for alert in alerts[:3]]


def _get_low_stock_alerts(shop_id: int) -> List[Dict[str, Any]]:
    """Return low-stock alert dicts for the daily briefing."""
    alerts: List[Dict[str, Any]] = []
    try:
        from agents.tools.inventory_tools import get_low_stock_alerts
        items = get_low_stock_alerts(shop_id)
        if items:
            names = ", ".join(i.get("name", "item") for i in items[:5])
            alerts.append(
                {
                    "severity": "warning",
                    "title": f"{len(items)} item{'s' if len(items) != 1 else ''} running low",
                    "body": f"Low stock: {names}. Reorder before you run out during busy periods.",
                }
            )
    except Exception:  # noqa: BLE001 — never crash the briefing
        pass
    return alerts[:1]


def _get_payroll_alerts(shop_id: int) -> List[Dict[str, Any]]:
    """Return payroll-specific alert dicts for the daily briefing.

    Checks:
    - CRA remittances due within 3 days → severity "warning"
    - February T4 filing reminder (Feb 1–28) → severity "info"

    Returns at most 2 entries to avoid crowding the main alerts list.
    """
    from datetime import date
    alerts: List[Dict[str, Any]] = []
    try:
        from agents.tools.payroll_tools import remittance_due_soon
        due = remittance_due_soon(shop_id, days_ahead=3)
        if due:
            total = sum(float(r.get("amount") or 0) for r in due)
            earliest = min((r.get("due_date") or "") for r in due)
            alerts.append(
                {
                    "severity": "warning",
                    "title": "CRA remittance due soon",
                    "body": (
                        f"${total:,.2f} in source deductions due by {earliest}. "
                        "Review the remittance summary and arrange payment."
                    ),
                }
            )
    except Exception:  # noqa: BLE001 — never crash the briefing for payroll issues
        pass

    try:
        today = date.today()
        if today.month == 2:
            alerts.append(
                {
                    "severity": "info",
                    "title": "T4 filing month",
                    "body": (
                        "February is T4 month. Generate and distribute T4 slips to employees "
                        "and file with CRA by Feb 28."
                    ),
                }
            )
    except Exception:  # noqa: BLE001
        pass

    return alerts[:2]


def build_briefing_recommendations(
    metrics: Dict[str, Any],
    pending_count: int,
    active_services: int,
) -> List[str]:
    recommendations: List[str] = []
    queue_length = int(metrics.get("queue_length", 0) or 0)
    wait_minutes = int(metrics.get("estimated_wait_minutes", 0) or 0)
    active_employees = int(metrics.get("active_employees", 0) or 0)

    if pending_count > 0:
        recommendations.append("Review pending approvals first so agent work is not blocked.")
    if queue_length >= 5 or wait_minutes >= 30:
        recommendations.append("Check the live queue and consider opening another staff lane or adjusting queue flow.")
    if active_employees <= 1 and queue_length >= 3:
        recommendations.append("Review staffing coverage for the current rush period.")
    if active_services == 0:
        recommendations.append("Publish at least one active service so bookings and customer discovery work properly.")

    if not recommendations:
        recommendations.extend(
            [
                "Ask the supervisor for a queue summary to verify today is on track.",
                "Review this week's revenue trend to spot opportunities early.",
            ]
        )

    return recommendations[:3]


def build_owner_briefing_actions(
    metrics: Dict[str, Any],
    pending_count: int,
    active_services: int,
) -> List[Dict[str, str]]:
    actions: List[Dict[str, str]] = []
    queue_length = int(metrics.get("queue_length", 0) or 0)
    wait_minutes = int(metrics.get("estimated_wait_minutes", 0) or 0)
    active_employees = int(metrics.get("active_employees", 0) or 0)

    if pending_count > 0:
        actions.append(
            {
                "label": "Review approvals",
                "payload": "Show me the pending approvals and tell me what needs my decision first.",
                "description": "Unblock paused agent work.",
            }
        )

    if queue_length >= 3 or wait_minutes >= 20:
        actions.append(
            {
                "label": "Check queue",
                "payload": "Give me the live queue status and tell me if I need to intervene.",
                "description": "Review demand and wait time pressure.",
            }
        )

    if active_employees <= 1 and queue_length >= 3:
        actions.append(
            {
                "label": "Show staffing gaps",
                "payload": "Show staffing gaps for the current rush period and tell me what coverage is missing.",
                "description": "Check whether coverage is falling behind demand.",
            }
        )

    if active_services == 0:
        actions.append(
            {
                "label": "Fix services",
                "payload": "List my current services and tell me what customers can book today.",
                "description": "Make sure discovery and booking are available.",
            }
        )

    actions.append(
        {
            "label": "Review revenue",
            "payload": "Show this week's revenue trend and any operational concerns I should know about.",
            "description": "Check commercial performance for the week.",
        }
    )

    actions.append(
        {
            "label": "POS summary",
            "payload": "Show me today's POS summary: number of transactions, total revenue, and top services.",
            "description": "Review today's point-of-sale totals.",
        }
    )

    deduped: List[Dict[str, str]] = []
    seen_labels: set[str] = set()
    for action in actions:
        label = action["label"]
        if label in seen_labels:
            continue
        seen_labels.add(label)
        deduped.append(action)
    return deduped[:4]


def enrich_pending_approval_payload(
    payload: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    action = str(payload.get("action") or "pending_action")
    details = dict(payload.get("details") or {})
    metrics = metrics or {}
    queue_length = int(metrics.get("queue_length", 0) or 0)
    wait_minutes = int(metrics.get("estimated_wait_minutes", 0) or 0)

    title = action.replace("_", " ").title()
    summary = "A business action needs your approval before the agent can continue."
    reason = "No explicit reason was provided."
    expected_impact = "This will change shop operations once approved."
    risk_level = "medium"
    recommended_decision = "Review carefully before approving."

    if action == "close_queue":
        title = "Close Active Queue"
        summary = "Pause new customers from joining the queue for this shop."
        reason = str(details.get("reason") or "The agent believes queue intake should be paused.")
        expected_impact = (
            f"New walk-ins will stop joining while the current queue of {queue_length} customers continues to clear. "
            f"Current estimated wait is {wait_minutes} minutes."
        )
        risk_level = "high"
        recommended_decision = "Approve only if intake should stop right now."
    elif action == "add_employee":
        employee_name = str(details.get("name") or "this employee")
        title = "Add Team Member"
        summary = f"Add {employee_name} to the shop team."
        reason = f"Create a new employee record for {employee_name}."
        expected_impact = "The person will appear in team management and become eligible for shift assignment."
        risk_level = "medium"
        recommended_decision = "Approve if the hiring or onboarding decision is final."
    elif action == "remove_employee":
        employee_id = details.get("user_id")
        title = "Deactivate Team Member"
        summary = "Deactivate an employee from the shop team."
        reason = f"Remove employee access for user ID {employee_id}."
        expected_impact = "The employee will no longer appear as active for staffing and schedule workflows."
        risk_level = "high"
        recommended_decision = "Approve only if access should be removed immediately."
    elif action == "assign_shift":
        employee_id = details.get("user_id")
        date = details.get("date") or "the selected day"
        start_time = details.get("start_time") or "start time"
        end_time = details.get("end_time") or "end time"
        title = "Assign Employee Shift"
        summary = f"Assign employee {employee_id} to a shift on {date}."
        reason = f"Create a shift from {start_time} to {end_time} for employee {employee_id}."
        expected_impact = "The team's staffing schedule will change immediately once approved."
        risk_level = "medium"
        recommended_decision = "Approve if the employee should be scheduled for that shift now."
    elif action == "create_invoice":
        service_name = str(details.get("service_name") or "the requested service")
        unit_price = float(details.get("unit_price") or 0.0)
        quantity = int(details.get("quantity") or 1)
        title = "Create Invoice"
        summary = f"Create an invoice for {service_name}."
        reason = f"Create an invoice for {service_name} at ${unit_price:.2f} x {quantity}."
        expected_impact = "A new invoice will appear in the shop's financial records and become payable."
        risk_level = "medium"
        recommended_decision = "Approve if the invoice should be created now."
    elif action == "record_payment":
        amount = float(details.get("amount") or 0.0)
        method = str(details.get("method") or "cash")
        invoice_id = details.get("invoice_id")
        title = "Record Payment"
        summary = f"Record a {method} payment for ${amount:.2f}."
        reason = f"Apply the payment to invoice {invoice_id} and update the payment ledger." if invoice_id else f"Record a standalone {method} payment of ${amount:.2f}."
        expected_impact = "Payment records and invoice status will update immediately once approved."
        risk_level = "medium"
        recommended_decision = "Approve if that payment should be recorded now."
    elif action == "process_refund":
        payment_id = details.get("payment_id")
        refund_amount = details.get("refund_amount")
        reason_text = str(details.get("reason") or "No explicit reason was provided.")
        title = "Process Refund"
        if refund_amount in (None, ""):
            summary = f"Refund payment {payment_id}."
            reason = f"Refund payment {payment_id}. Reason: {reason_text}"
        else:
            summary = f"Refund ${float(refund_amount or 0.0):.2f} for payment {payment_id}."
            reason = f"Refund ${float(refund_amount or 0.0):.2f} for payment {payment_id}. Reason: {reason_text}"
        expected_impact = "The payment ledger and refund status will update immediately once approved."
        risk_level = "high"
        recommended_decision = "Approve only if the refund amount and reason are correct."

    return {
        **payload,
        "details": details,
        "title": title,
        "summary": summary,
        "reason": reason,
        "expected_impact": expected_impact,
        "risk_level": risk_level,
        "recommended_decision": recommended_decision,
    }


def build_owner_briefing(
    *,
    shop_id: int,
    shop_name: str,
    metrics: Dict[str, Any],
    active_services: int,
    active_employees: int,
    pending_count: int,
    today_revenue: float,
    today_transactions: int,
    weekly_revenue: float,
    alert_history: Optional[List[Dict[str, Any]]] = None,
    generated_at: Optional[str] = None,
    source: str = "live",
) -> Dict[str, Any]:
    queue_length = int(metrics.get("queue_length", 0) or 0)
    wait_minutes = int(metrics.get("estimated_wait_minutes", 0) or 0)
    serving_count = int(metrics.get("people_being_served", 0) or 0)
    alerts = build_briefing_alerts(metrics, pending_count, active_services)
    recommendations = build_briefing_recommendations(metrics, pending_count, active_services)
    actions = build_owner_briefing_actions(metrics, pending_count, active_services)

    return {
        "shop_id": shop_id,
        "shop_name": shop_name,
        "generated_at": generated_at or _utcnow_iso(),
        "source": source,
        "summary": (
            f"{shop_name} currently has {queue_length} people waiting, "
            f"{serving_count} being served, {active_employees} active staff detected, and "
            f"{pending_count} pending approval{'s' if pending_count != 1 else ''}."
        ),
        "metrics": {
            "queue_length": queue_length,
            "estimated_wait_minutes": wait_minutes,
            "people_being_served": serving_count,
            "active_employees": active_employees,
            "active_services": active_services,
            "pending_approvals": pending_count,
            "today_revenue": float(today_revenue or 0.0),
            "today_transactions": int(today_transactions or 0),
            "weekly_revenue": float(weekly_revenue or 0.0),
        },
        "alerts": alerts,
        "alert_history": alert_history or [],
        "recommendations": recommendations,
        "actions": actions,
    }


def _alert_fingerprint(alert: Dict[str, Any]) -> str:
    return f"{alert.get('severity', 'info')}::{alert.get('title', '')}::{alert.get('body', '')}"


def get_shop_alert_history(shop_id: int) -> List[Dict[str, Any]]:
    cached = redis_client.tenant_get(shop_id, BRIEFING_ALERT_HISTORY_KEY)
    if not isinstance(cached, list):
        return []
    return [_normalize_alert(item) for item in cached[:8]]


def _merge_alert_history(
    existing_history: List[Dict[str, Any]],
    current_alerts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for alert in current_alerts + existing_history:
        normalized = _normalize_alert(alert)
        fingerprint = _alert_fingerprint(normalized)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        merged.append(normalized)
    return merged[:8]


def get_cached_shop_briefing_snapshot(shop_id: int) -> Optional[Dict[str, Any]]:
    cached = redis_client.tenant_get(shop_id, BRIEFING_CACHE_KEY)
    if isinstance(cached, dict):
        return cached
    return None


def refresh_shop_briefing_cache(
    shop_id: int,
    shop_name: Optional[str] = None,
    *,
    db: Optional[DatabaseInterface] = None,
) -> Dict[str, Any]:
    db = db or DatabaseInterface()
    shop = db.get_shop_by_id(shop_id) if not shop_name else {"name": shop_name}
    resolved_shop_name = str((shop or {}).get("name") or shop_name or f"Shop {shop_id}")

    metrics = db.get_shop_live_wait_metrics(shop_id) or {}
    services = db.get_shop_services(shop_id, include_inactive=False) or []
    employees = db.get_shop_employees(shop_id, is_active=True) or []
    today_revenue = finance_tools.daily_revenue(shop_id)
    weekly_revenue = finance_tools.weekly_summary(shop_id)
    active_services = len(services)
    active_employees = int(metrics.get("active_employees", 0) or len(employees) or 0)

    existing_history = get_shop_alert_history(shop_id)
    briefing = build_owner_briefing(
        shop_id=shop_id,
        shop_name=resolved_shop_name,
        metrics=metrics,
        active_services=active_services,
        active_employees=active_employees,
        pending_count=0,
        today_revenue=float(today_revenue.get("total_revenue", 0.0) or 0.0),
        today_transactions=int(today_revenue.get("transaction_count", 0) or 0),
        weekly_revenue=float(weekly_revenue.get("total_revenue", 0.0) or 0.0),
        alert_history=existing_history,
        source="scheduled",
    )

    # Inject payroll alerts (remittance due, T4 month)
    payroll_alerts = _get_payroll_alerts(shop_id)
    if payroll_alerts:
        created_at = _utcnow_iso()
        normalized_payroll = [_normalize_alert(a, created_at=created_at) for a in payroll_alerts]
        # Prepend payroll alerts (they are time-sensitive); keep overall cap at 5
        briefing["alerts"] = (normalized_payroll + briefing.get("alerts", []))[:5]
        # Also inject a "Run Payroll" quick-action when a remittance is due soon
        if any(a.get("severity") == "warning" for a in payroll_alerts):
            payroll_action = {
                "label": "Run Payroll",
                "payload": "Show me the payroll remittance summary and help me run payroll for this period.",
                "description": "Review remittances and draft this period's payslips.",
            }
            existing_actions = briefing.get("actions", [])
            if not any(a.get("label") == "Run Payroll" for a in existing_actions):
                briefing["actions"] = [payroll_action] + existing_actions

    # Inject low stock alerts (inventory)
    low_stock_alerts = _get_low_stock_alerts(shop_id)
    if low_stock_alerts:
        created_at = _utcnow_iso()
        normalized_stock = [_normalize_alert(a, created_at=created_at) for a in low_stock_alerts]
        briefing["alerts"] = (briefing.get("alerts", []) + normalized_stock)[:5]
        existing_actions = briefing.get("actions", [])
        if not any(a.get("label") == "Restock inventory" for a in existing_actions):
            briefing["actions"] = existing_actions + [
                {
                    "label": "Restock inventory",
                    "payload": "Show me which supplies are running low and help me record restocks.",
                    "description": "Review low-stock items and log incoming supplies.",
                }
            ]

    alert_history = _merge_alert_history(existing_history, briefing.get("alerts", []))
    briefing["alert_history"] = alert_history

    redis_client.tenant_set(shop_id, BRIEFING_CACHE_KEY, briefing, ttl=BRIEFING_CACHE_TTL_SECONDS)
    redis_client.tenant_set(
        shop_id,
        BRIEFING_ALERT_HISTORY_KEY,
        alert_history,
        ttl=BRIEFING_ALERT_HISTORY_TTL_SECONDS,
    )
    return briefing


def refresh_all_shop_briefings() -> int:
    session = SessionLocal()
    refreshed = 0
    try:
        rows = session.query(Shop.id, Shop.name).filter(Shop.is_active == True).all()
        db = DatabaseInterface()
        for shop_id, shop_name in rows:
            try:
                refresh_shop_briefing_cache(int(shop_id), str(shop_name), db=db)
                refreshed += 1
            except Exception as exc:
                logger.warning("Operational briefing refresh failed for shop %s: %s", shop_id, exc)
        return refreshed
    finally:
        session.close()