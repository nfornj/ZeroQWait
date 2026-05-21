"""Temporal workflows and activities for the payroll, hiring, and tips subsystem.

Workflows
---------
HiringWorkflow            — onboard a new employee (create DB record + payroll profile)
PayrollRunWorkflow         — draft payslips for all active employees, await HITL approval
RemittanceReminderWorkflow — scan pending remittances and notify owner if due soon
TipPoolWorkflow            — pool tips, calculate splits, await HITL approval
AnnualPayrollResetWorkflow — reset YTD accumulators for all active shops (Jan 1)

Registration
------------
Register all workflows and activities in ``temporal_worker.py`` (Step 9).
Add ``ensure_payroll_schedules`` calls from ``temporal_schedules.py`` (Step 10).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    from agents.heartbeat_activities import list_active_shop_ids_activity

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Activities
# ──────────────────────────────────────────────────────────────────────────────


@activity.defn
async def hiring_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create base employee record + payroll profile, then notify owner."""
    from database import SessionLocal
    from modules.agent.models import RunStatus
    from modules.agent.work_repository import AgentWorkRepository
    from agents.tools.hr_tools import _local_add_employee_full

    shop_id = int(payload["shop_id"])
    session = SessionLocal()
    repo = AgentWorkRepository(session)
    run = None
    try:
        run = repo.create_run(
            shop_id=shop_id,
            run_type="payroll_hiring",
            trigger_source="temporal",
            execution_mode="workflow",
            input_payload=payload,
        )
        result = _local_add_employee_full(
            shop_id=shop_id,
            name=str(payload["name"]),
            pay_type=str(payload.get("pay_type") or "hourly"),
            hourly_rate=payload.get("hourly_rate"),
            annual_salary=payload.get("annual_salary"),
            pay_frequency=str(payload.get("pay_frequency") or "biweekly"),
            province=str(payload.get("province") or "ON"),
            email=payload.get("email"),
            phone=payload.get("phone"),
            role=str(payload.get("role") or "employee"),
            employee_code=payload.get("employee_code"),
            created_by=payload.get("created_by"),
            sin=payload.get("sin"),
        )
        if "error" in result:
            repo.update_run_status(run.id, RunStatus.FAILED, error_message=result["error"])
            return {"ok": False, **result}

        repo.create_notification(
            shop_id=shop_id,
            run_id=run.id,
            notification_type="employee_hired",
            title=f"{payload['name']} added to team",
            message=(
                f"{payload['name']} has been onboarded with a {payload.get('pay_frequency', 'biweekly')} "
                f"pay schedule ({payload.get('province', 'ON')} province). "
                "Review their payroll profile to confirm details."
            ),
            severity="info",
            payload=result,
        )
        repo.update_run_status(run.id, RunStatus.COMPLETED, output_payload=result)
        return {"ok": True, "shop_id": shop_id, **result}
    except Exception as exc:
        logger.exception("hiring_activity failed for shop %s", shop_id)
        if run is not None:
            repo.update_run_status(run.id, RunStatus.FAILED, error_message=str(exc))
        raise
    finally:
        session.close()


@activity.defn
async def draft_payroll_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Draft payslips for every active employee in the shop for the given period.
    Returns list of draft payslip IDs and a total_net_pay figure.
    Does NOT approve or update YTD — that happens after HITL.
    """
    from database import SessionLocal
    from modules.agent.models import RunStatus
    from modules.agent.work_repository import AgentWorkRepository
    from modules.shops.models import Shop
    from modules.employees.models import ShopEmployee
    from agents.tools.payroll_tools import draft_payslip

    shop_id = int(payload["shop_id"])
    period_start: str = payload["period_start"]
    period_end: str = payload["period_end"]
    pay_date: str = payload.get("pay_date") or period_end
    regular_hours: float = float(payload.get("regular_hours") or 80.0)
    overtime_hours: float = float(payload.get("overtime_hours") or 0.0)
    tips_amount: float = float(payload.get("tips_amount") or 0.0)

    session = SessionLocal()
    repo = AgentWorkRepository(session)
    run = None
    try:
        run = repo.create_run(
            shop_id=shop_id,
            run_type="payroll_draft",
            trigger_source="temporal",
            execution_mode="workflow",
            input_payload=payload,
        )

        employees = (
            session.query(ShopEmployee)
            .filter(
                ShopEmployee.shop_id == shop_id,
                ShopEmployee.is_active == True,
            )
            .all()
        )
        if not employees:
            repo.update_run_status(run.id, RunStatus.COMPLETED, output_payload={"skipped": "no active employees"})
            return {"ok": True, "payslips": [], "total_net_pay": 0.0, "employee_count": 0}

        drafted = []
        total_net = 0.0
        for emp in employees:
            if emp.payroll_profile is None:
                continue
            try:
                ps = draft_payslip(
                    shop_id=shop_id,
                    shop_employee_id=emp.id,
                    period_start=period_start,
                    period_end=period_end,
                    pay_date=pay_date,
                    regular_hours=regular_hours,
                    overtime_hours=overtime_hours,
                    tips_amount=tips_amount,
                )
                drafted.append(ps)
                total_net += float(ps.get("net_pay") or 0)
            except Exception as exc:  # noqa: BLE001
                drafted.append({"error": str(exc), "shop_employee_id": emp.id})

        result = {
            "ok": True,
            "shop_id": shop_id,
            "period_start": period_start,
            "period_end": period_end,
            "employee_count": len(drafted),
            "total_net_pay": round(total_net, 2),
            "payslips": drafted,
        }
        repo.update_run_status(run.id, RunStatus.COMPLETED, output_payload=result)
        return result
    except Exception as exc:
        logger.exception("draft_payroll_activity failed for shop %s", shop_id)
        if run is not None:
            repo.update_run_status(run.id, RunStatus.FAILED, error_message=str(exc))
        raise
    finally:
        session.close()


@activity.defn
async def approve_payroll_batch_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Approve a list of draft payslips and update YTD."""
    from agents.tools.payroll_tools import approve_payslip

    payslip_ids: List[int] = [int(pid) for pid in (payload.get("payslip_ids") or [])]
    approved_by: int = int(payload["approved_by"])

    approved = []
    failed = []
    for pid in payslip_ids:
        try:
            result = approve_payslip(pid, approved_by)
            if "error" in result:
                failed.append({"payslip_id": pid, "error": result["error"]})
            else:
                approved.append(pid)
        except Exception as exc:  # noqa: BLE001
            failed.append({"payslip_id": pid, "error": str(exc)})

    return {
        "ok": True,
        "approved_count": len(approved),
        "failed_count": len(failed),
        "approved": approved,
        "failed": failed,
    }


@activity.defn
async def remittance_reminder_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Check all active shops for remittances due within `days_ahead` days and create notifications."""
    from database import SessionLocal
    from modules.agent.work_repository import AgentWorkRepository
    from agents.tools.payroll_tools import remittance_due_soon

    days_ahead: int = int(payload.get("days_ahead") or 3)
    session = SessionLocal()
    repo = AgentWorkRepository(session)
    try:
        from modules.shops.models import Shop
        shops = session.query(Shop.id, Shop.name).filter(Shop.is_active == True).all()
        notified = 0
        for shop_id, shop_name in shops:
            due = remittance_due_soon(int(shop_id), days_ahead=days_ahead)
            if not due:
                continue
            for rem in due:
                repo.create_notification(
                    shop_id=int(shop_id),
                    run_id=None,
                    notification_type="remittance_due",
                    title=f"CRA remittance due {rem.get('due_date')}",
                    message=(
                        f"Remittance of ${float(rem.get('amount') or 0):,.2f} "
                        f"(period {rem.get('period_start')} – {rem.get('period_end')}) "
                        f"is due in ≤{days_ahead} days."
                    ),
                    severity="warning",
                    payload=rem,
                )
                notified += 1
        return {"ok": True, "notified": notified}
    finally:
        session.close()


@activity.defn
async def split_tip_pool_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate proportional tip splits by hours_worked and create pool splits + tip_log entries."""
    from agents.tools.payroll_tools import split_tip_pool

    tip_pool_id: int = int(payload["tip_pool_id"])
    splits: List[Dict[str, Any]] = payload["splits"]  # [{shop_employee_id, hours_worked}, ...]
    approved_by: int = int(payload["approved_by"])

    result = split_tip_pool(tip_pool_id, splits, approved_by)
    return result


@activity.defn
async def annual_ytd_reset_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Reset YTD accumulators for a single shop at year-start."""
    from agents.tools.payroll_tools import reset_ytd_for_shop

    shop_id = int(payload["shop_id"])
    new_year: int = int(payload.get("new_year") or date.today().year)
    result = reset_ytd_for_shop(shop_id, new_year)
    return {"ok": True, "shop_id": shop_id, "new_year": new_year, "reset": result}


# ──────────────────────────────────────────────────────────────────────────────
# Workflows
# ──────────────────────────────────────────────────────────────────────────────


@workflow.defn
class HiringWorkflow:
    """
    Onboard a new employee with a payroll profile.

    Input payload keys:
        shop_id, name, pay_type, hourly_rate|annual_salary,
        pay_frequency, province, email, phone, role,
        employee_code, created_by, sin (optional)
    """

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await workflow.execute_activity(
            hiring_activity,
            payload,
            start_to_close_timeout=timedelta(minutes=5),
        )


@workflow.defn
class PayrollRunWorkflow:
    """
    Draft payslips for all active employees in a shop, then wait for HITL
    approval via ``approve_signal`` before finalizing.

    Input payload keys:
        shop_id, period_start, period_end, pay_date,
        regular_hours, overtime_hours, tips_amount
    """

    _approved: Optional[Dict[str, Any]] = None
    _rejected: bool = False

    @workflow.signal
    async def approve_signal(self, approval: Dict[str, Any]) -> None:
        self._approved = approval

    @workflow.signal
    async def reject_signal(self, reason: str = "") -> None:
        self._rejected = True

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from database import SessionLocal
        from modules.agent.work_repository import AgentWorkRepository

        shop_id = int(payload["shop_id"])

        # 1 — Draft all payslips
        draft_result = await workflow.execute_activity(
            draft_payroll_activity,
            payload,
            start_to_close_timeout=timedelta(minutes=10),
        )
        if not draft_result.get("ok"):
            return draft_result

        # 2 — Notify owner and wait for HITL approval (max 48 hours)
        session = SessionLocal()
        repo = AgentWorkRepository(session)
        try:
            payslip_ids = [ps["id"] for ps in draft_result.get("payslips", []) if "id" in ps]
            repo.create_notification(
                shop_id=shop_id,
                run_id=None,
                notification_type="payroll_approval_required",
                title="Payroll ready for approval",
                message=(
                    f"Draft payslips for {draft_result['employee_count']} employees "
                    f"({payload.get('period_start')} – {payload.get('period_end')}) "
                    f"total net pay ${draft_result['total_net_pay']:,.2f}. "
                    "Approve to mark as paid."
                ),
                severity="warning",
                payload={**draft_result, "payslip_ids": payslip_ids},
            )
        finally:
            session.close()

        await workflow.wait_condition(
            lambda: self._approved is not None or self._rejected,
            timeout=timedelta(hours=48),
        )

        if self._rejected or self._approved is None:
            return {
                "ok": False,
                "status": "rejected",
                "shop_id": shop_id,
                "draft": draft_result,
            }

        # 3 — Approve payslips
        payslip_ids = [ps["id"] for ps in draft_result.get("payslips", []) if "id" in ps]
        approve_result = await workflow.execute_activity(
            approve_payroll_batch_activity,
            {
                "payslip_ids": payslip_ids,
                "approved_by": self._approved.get("approved_by", 0),
            },
            start_to_close_timeout=timedelta(minutes=5),
        )
        return {
            "ok": True,
            "status": "approved",
            "shop_id": shop_id,
            "draft": draft_result,
            "approval": approve_result,
        }


@workflow.defn
class RemittanceReminderWorkflow:
    """
    Scan all active shops for remittances due soon and notify owners.
    Intended to run daily (or on demand).
    """

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await workflow.execute_activity(
            remittance_reminder_activity,
            payload,
            start_to_close_timeout=timedelta(minutes=10),
        )


@workflow.defn
class TipPoolWorkflow:
    """
    Split a tip pool proportionally by hours_worked, await HITL approval.

    Input payload keys:
        tip_pool_id, splits: [{shop_employee_id, hours_worked}, ...],
        approved_by (pre-set if auto-approved)
    The workflow creates the splits and logs individual tip entries.
    """

    _approved: Optional[Dict[str, Any]] = None
    _rejected: bool = False

    @workflow.signal
    async def approve_signal(self, approval: Dict[str, Any]) -> None:
        self._approved = approval

    @workflow.signal
    async def reject_signal(self, reason: str = "") -> None:
        self._rejected = True

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from database import SessionLocal
        from modules.agent.work_repository import AgentWorkRepository

        shop_id = int(payload.get("shop_id") or 0)

        # Notify owner for review
        if shop_id:
            session = SessionLocal()
            repo = AgentWorkRepository(session)
            try:
                repo.create_notification(
                    shop_id=shop_id,
                    run_id=None,
                    notification_type="tip_split_approval_required",
                    title="Tip pool split ready for approval",
                    message=(
                        f"Tip pool {payload.get('tip_pool_id')} is ready to be split "
                        f"among {len(payload.get('splits', []))} staff members. "
                        "Review and approve."
                    ),
                    severity="info",
                    payload=payload,
                )
            finally:
                session.close()

        await workflow.wait_condition(
            lambda: self._approved is not None or self._rejected,
            timeout=timedelta(hours=24),
        )

        if self._rejected or self._approved is None:
            return {"ok": False, "status": "rejected", "tip_pool_id": payload.get("tip_pool_id")}

        # Execute the split
        result = await workflow.execute_activity(
            split_tip_pool_activity,
            {
                "tip_pool_id": payload["tip_pool_id"],
                "splits": payload["splits"],
                "approved_by": self._approved.get("approved_by", 0),
            },
            start_to_close_timeout=timedelta(minutes=5),
        )
        return {"ok": True, "status": "approved", **result}


@workflow.defn
class AnnualPayrollResetWorkflow:
    """
    Reset YTD accumulators for all active shops at the start of a new year.
    Scheduled to run on Jan 1 via ``ensure_payroll_schedules``.
    """

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        new_year: int = int(payload.get("new_year") or date.today().year)

        shops: List[Dict[str, Any]] = await workflow.execute_activity(
            list_active_shop_ids_activity,
            start_to_close_timeout=timedelta(minutes=2),
        )
        if not shops:
            return {"ok": True, "reset": 0, "skipped": "no active shops"}

        results: List[Dict[str, Any]] = []
        for shop in shops:
            try:
                result = await workflow.execute_activity(
                    annual_ytd_reset_activity,
                    {"shop_id": shop["shop_id"], "new_year": new_year},
                    start_to_close_timeout=timedelta(minutes=5),
                )
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                results.append({"ok": False, "shop_id": shop["shop_id"], "error": str(exc)})

        return {
            "ok": True,
            "new_year": new_year,
            "shop_count": len(shops),
            "reset": sum(1 for r in results if r.get("ok")),
            "failed": sum(1 for r in results if not r.get("ok")),
            "results": results,
        }
