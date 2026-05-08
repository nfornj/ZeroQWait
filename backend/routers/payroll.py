"""
routers/payroll.py — Payroll API endpoints.

Endpoints:
  GET  /api/payroll/shop/{shop_id}/payslips              — owner: list all payslips
  GET  /api/payroll/shop/{shop_id}/payslips/{id}/pdf     — owner: download payslip PDF
  GET  /api/payroll/shop/{shop_id}/expense-summary       — owner: payroll cost totals
  POST /api/payroll/shop/{shop_id}/draft-period          — owner: draft 15-day payroll run
  GET  /api/payroll/me/payslips                          — employee: own payslips
  GET  /api/payroll/me/payslips/{payslip_id}/pdf         — employee: own payslip PDF
"""

from __future__ import annotations

import io
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text

from database import SessionLocal, get_db
from db_interface import db_interface
from shared.auth_utils import get_current_user
from agents.tools import payroll_tools
from modules.employees.models import ShopEmployee, EmployeePayrollProfile
from services.payroll_pdf import generate_payslip_pdf, payslip_filename

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Request / Response schemas ───────────────────────────────────────────────

class DraftPeriodRequest(BaseModel):
    period_start: date
    period_end: Optional[date] = None   # defaults to period_start + 14 days
    pay_date: Optional[date] = None     # defaults to period_end + 3 days
    regular_hours_per_employee: float = 80.0  # default 2 weeks full-time


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _require_shop_owner(shop_id: int, current_user: dict) -> dict:
    """Raise 403 if current_user does not own shop_id. Returns shop dict."""
    shop = db_interface.get_shop_by_id(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    if shop["owner_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized for this shop")
    return shop


def _require_employee_of_shop(
    payslip_id: int,
    current_user: dict,
    session,
) -> dict:
    """Return payslip row only if it belongs to the calling employee (by user_id match)."""
    row = session.execute(
        text(
            "SELECT p.*, se.user_id "
            "FROM payslips p "
            "JOIN shop_employees se ON se.id = p.shop_employee_id "
            "WHERE p.id = :pid"
        ),
        {"pid": payslip_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Payslip not found")
    row_dict = dict(row._mapping)
    if row_dict["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this payslip")
    return row_dict


def _build_pdf_response(
    payslip: Dict[str, Any],
    employee_name: str,
    shop_name: str,
    sin_last4: Optional[str],
    province: str,
) -> StreamingResponse:
    pdf_bytes = generate_payslip_pdf(
        payslip=payslip,
        employee_name=employee_name,
        shop_name=shop_name,
        sin_last4=sin_last4,
        province=province,
    )
    filename = payslip_filename(shop_name, employee_name, payslip.get("period_start"))
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


def _employee_display_name(user_row) -> str:
    """Return full_name if present, else username."""
    if not user_row:
        return "Unknown"
    full = getattr(user_row, "full_name", None) or ""
    if full.strip():
        return full.strip()
    return getattr(user_row, "username", None) or "Unknown"


# ─── Owner endpoints ──────────────────────────────────────────────────────────

@router.get("/shop/{shop_id}/payslips")
def list_shop_payslips(
    shop_id: int,
    status: Optional[str] = Query(None, description="Filter by status: draft, approved, paid"),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """Return all payslips for the shop, enriched with employee name and province."""
    _require_shop_owner(shop_id, current_user)

    raw = payroll_tools.list_payslips(shop_id, status=status, limit=limit)

    with SessionLocal() as session:
        # Enrich with employee name + province + sin_last4
        enriched: List[Dict[str, Any]] = []
        for slip in raw:
            se_id = slip.get("shop_employee_id")
            emp_name = "Unknown"
            province = "—"
            sin_last4 = None
            if se_id:
                se = session.query(ShopEmployee).filter(ShopEmployee.id == se_id).first()
                if se:
                    emp_name = _employee_display_name(se.user)
                profile = (
                    session.query(EmployeePayrollProfile)
                    .filter(EmployeePayrollProfile.shop_employee_id == se_id)
                    .first()
                )
                if profile:
                    province = profile.province or "ON"
                    sin_last4 = profile.sin_last4
            enriched.append({
                **slip,
                "employee_name": emp_name,
                "province": province,
                "sin_last4": sin_last4,
            })
    return enriched


@router.get("/shop/{shop_id}/payslips/{payslip_id}/pdf")
def download_payslip_pdf_owner(
    shop_id: int,
    payslip_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Download a payslip as a PDF (owner view)."""
    shop = _require_shop_owner(shop_id, current_user)

    with SessionLocal() as session:
        row = session.execute(
            text("SELECT * FROM payslips WHERE id = :id AND shop_id = :s"),
            {"id": payslip_id, "s": shop_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Payslip not found")
        payslip = dict(row._mapping)

        se_id = payslip.get("shop_employee_id")
        emp_name = "Employee"
        sin_last4 = None
        province = "ON"
        if se_id:
            se = session.query(ShopEmployee).filter(ShopEmployee.id == se_id).first()
            if se:
                emp_name = _employee_display_name(se.user)
            profile = (
                session.query(EmployeePayrollProfile)
                .filter(EmployeePayrollProfile.shop_employee_id == se_id)
                .first()
            )
            if profile:
                province = profile.province or "ON"
                sin_last4 = profile.sin_last4

    return _build_pdf_response(
        payslip=payslip,
        employee_name=emp_name,
        shop_name=shop["name"],
        sin_last4=sin_last4,
        province=province,
    )


@router.get("/shop/{shop_id}/expense-summary")
def get_expense_summary(
    shop_id: int,
    months: int = Query(3, ge=1, le=24, description="Number of months to look back"),
    current_user: dict = Depends(get_current_user),
):
    """Return aggregated payroll expense totals and monthly breakdown for the shop."""
    _require_shop_owner(shop_id, current_user)

    period_start = date.today().replace(day=1) - timedelta(days=30 * (months - 1))
    period_start = period_start.replace(day=1)

    with SessionLocal() as session:
        totals_row = session.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(gross_pay), 0)        AS total_gross,
                    COALESCE(SUM(net_pay), 0)          AS total_net,
                    COALESCE(SUM(cpp_deduction), 0)    AS total_emp_cpp,
                    COALESCE(SUM(ei_deduction), 0)     AS total_emp_ei,
                    COALESCE(SUM(fed_tax), 0)          AS total_fed_tax,
                    COALESCE(SUM(prov_tax), 0)         AS total_prov_tax,
                    COALESCE(SUM(other_deductions), 0) AS total_other,
                    COALESCE(SUM(cpp_deduction), 0)    AS total_employer_cpp,
                    COALESCE(SUM(ei_deduction) * 1.4, 0) AS total_employer_ei,
                    COUNT(*) AS payslip_count
                FROM payslips
                WHERE shop_id = :s AND status = 'approved'
                  AND period_start >= :since
                """
            ),
            {"s": shop_id, "since": period_start},
        ).fetchone()

        monthly_rows = session.execute(
            text(
                """
                SELECT
                    TO_CHAR(period_start, 'YYYY-MM') AS month,
                    COALESCE(SUM(gross_pay), 0)      AS gross,
                    COALESCE(SUM(net_pay), 0)        AS net,
                    COALESCE(SUM(cpp_deduction + ei_deduction + fed_tax + prov_tax), 0) AS deductions,
                    COALESCE(SUM(cpp_deduction) + SUM(ei_deduction) * 1.4, 0) AS employer_obligations,
                    COUNT(*) AS payslip_count
                FROM payslips
                WHERE shop_id = :s AND status = 'approved'
                  AND period_start >= :since
                GROUP BY month
                ORDER BY month DESC
                """
            ),
            {"s": shop_id, "since": period_start},
        ).fetchall()

    t = dict(totals_row) if totals_row else {}
    employer_cpp = float(t.get("total_employer_cpp") or 0)
    employer_ei  = float(t.get("total_employer_ei") or 0)
    total_gross  = float(t.get("total_gross") or 0)
    total_remittance = (
        float(t.get("total_emp_cpp") or 0)
        + employer_cpp
        + float(t.get("total_emp_ei") or 0)
        + employer_ei
        + float(t.get("total_fed_tax") or 0)
        + float(t.get("total_prov_tax") or 0)
    )

    return {
        "period_start": period_start.isoformat(),
        "months": months,
        "summary": {
            "total_gross_pay":        total_gross,
            "total_net_pay":          float(t.get("total_net") or 0),
            "employee_cpp":           float(t.get("total_emp_cpp") or 0),
            "employee_ei":            float(t.get("total_emp_ei") or 0),
            "federal_tax":            float(t.get("total_fed_tax") or 0),
            "provincial_tax":         float(t.get("total_prov_tax") or 0),
            "other_deductions":       float(t.get("total_other") or 0),
            "employer_cpp":           employer_cpp,
            "employer_ei":            employer_ei,
            "total_cra_remittance":   total_remittance,
            "total_labour_cost":      total_gross + employer_cpp + employer_ei,
            "payslip_count":          int(t.get("payslip_count") or 0),
        },
        "monthly_breakdown": [
            {
                "month":               row.month,
                "gross":               float(row.gross),
                "net":                 float(row.net),
                "deductions":          float(row.deductions),
                "employer_obligations": float(row.employer_obligations),
                "payslip_count":       int(row.payslip_count),
            }
            for row in monthly_rows
        ],
    }


@router.post("/shop/{shop_id}/draft-period")
def draft_payroll_period(
    shop_id: int,
    body: DraftPeriodRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Draft payslips for all active employees with a payroll profile for a given period.
    Skips employees that already have a draft/approved payslip for the same period.
    """
    shop = _require_shop_owner(shop_id, current_user)

    period_start = body.period_start
    period_end   = body.period_end or (period_start + timedelta(days=14))
    pay_date     = body.pay_date   or (period_end + timedelta(days=3))

    created: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    errors:  List[Dict[str, Any]] = []

    with SessionLocal() as session:
        # Get all active employees with payroll profiles for this shop
        rows = (
            session.query(ShopEmployee, EmployeePayrollProfile)
            .join(
                EmployeePayrollProfile,
                EmployeePayrollProfile.shop_employee_id == ShopEmployee.id,
            )
            .filter(
                ShopEmployee.shop_id == shop_id,
                ShopEmployee.is_active == True,
            )
            .all()
        )

        if not rows:
            raise HTTPException(
                status_code=422,
                detail="No active employees with payroll profiles found. "
                       "Please set up payroll profiles for employees first.",
            )

        for se, profile in rows:
            emp_name = _employee_display_name(se.user)

            # Skip if a payslip already exists for this period
            existing = session.execute(
                text(
                    "SELECT id FROM payslips "
                    "WHERE shop_employee_id = :se_id "
                    "  AND period_start = :ps AND period_end = :pe "
                    "  AND status IN ('draft', 'approved', 'paid')"
                ),
                {"se_id": se.id, "ps": period_start, "pe": period_end},
            ).fetchone()
            if existing:
                skipped.append({"employee": emp_name, "reason": "payslip already exists"})
                continue

            try:
                slip = payroll_tools.draft_payslip(
                    shop_id=shop_id,
                    shop_employee_id=se.id,
                    period_start=period_start,
                    period_end=period_end,
                    pay_date=pay_date,
                    regular_hours=body.regular_hours_per_employee,
                )
                created.append({"employee": emp_name, "payslip_id": slip.get("id")})
            except Exception as exc:
                logger.warning("Failed to draft payslip for employee %s: %s", emp_name, exc)
                errors.append({"employee": emp_name, "error": str(exc)})

    return {
        "shop": shop["name"],
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "pay_date": pay_date.isoformat(),
        "created": created,
        "skipped": skipped,
        "errors": errors,
    }


# ─── Employee (self-service) endpoints ────────────────────────────────────────

@router.get("/me/payslips")
def get_my_payslips(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Return the calling employee's own payslips across all shops."""
    user_id = current_user["id"]

    with SessionLocal() as session:
        rows = session.execute(
            text(
                """
                SELECT p.*, se.shop_id, s.name AS shop_name,
                       epp.province, epp.sin_last4
                FROM payslips p
                JOIN shop_employees se ON se.id = p.shop_employee_id
                JOIN shops s           ON s.id  = se.shop_id
                LEFT JOIN employee_payroll_profiles epp ON epp.shop_employee_id = se.id
                WHERE se.user_id = :uid AND se.is_active = TRUE
                ORDER BY p.period_end DESC, p.id DESC
                LIMIT :lim
                """
            ),
            {"uid": user_id, "lim": limit},
        ).fetchall()

    return [dict(r._mapping) for r in rows]


@router.get("/me/payslips/{payslip_id}/pdf")
def download_my_payslip_pdf(
    payslip_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Download the employee's own payslip as a PDF."""
    with SessionLocal() as session:
        payslip = _require_employee_of_shop(payslip_id, current_user, session)

        # Fetch shop name
        shop_row = session.execute(
            text("SELECT name FROM shops WHERE id = :sid"),
            {"sid": payslip["shop_id"]},
        ).fetchone()
        shop_name = shop_row.name if shop_row else "Your Shop"

        # Fetch profile for province + sin_last4 + employee name
        se = (
            session.query(ShopEmployee)
            .filter(ShopEmployee.id == payslip["shop_employee_id"])
            .first()
        )
        emp_name = _employee_display_name(se.user) if se else "Employee"
        province = "ON"
        sin_last4 = None
        if se:
            profile = (
                session.query(EmployeePayrollProfile)
                .filter(EmployeePayrollProfile.shop_employee_id == se.id)
                .first()
            )
            if profile:
                province = profile.province or "ON"
                sin_last4 = profile.sin_last4

    return _build_pdf_response(
        payslip=payslip,
        employee_name=emp_name,
        shop_name=shop_name,
        sin_last4=sin_last4,
        province=province,
    )
