"""
payroll_tools.py — Data-access layer for the payroll system.

All functions use the SessionLocal() direct-DB pattern (same as _local_*
functions in hr_tools.py). No MCP calls. No business logic — only DB read/write.

Consumed by:
  - payroll_workflows.py (Temporal activities)
  - hr.py (HR agent operations)
  - briefings.py (morning payroll alerts)
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from agents.payroll_calculator import (
    PayPeriodInput,
    PayrollConstants,
    PayslipResult,
    calculate_payslip,
    employer_cpp,
    employer_ei,
    remittance_total,
)
from database import SessionLocal
from modules.employees.models import EmployeePayrollProfile, ShopEmployee

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> Dict[str, Any]:
    """Convert a SQLAlchemy row to a plain dict (coerce Decimal → float / date → str)."""
    d = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        if hasattr(val, "__float__"):          # Numeric/Decimal
            val = float(val)
        elif isinstance(val, (date, datetime)):
            val = val.isoformat()
        d[col.name] = val
    return d


def _load_constants(session: Session, tax_year: int, province: str) -> PayrollConstants:
    """
    Load one row from payroll_constants and map it to PayrollConstants.
    Raises ValueError if the row is not found.
    """
    result = session.execute(
        text("SELECT * FROM payroll_constants WHERE tax_year = :y AND province = :p"),
        {"y": tax_year, "p": province},
    ).fetchone()
    if result is None:
        raise ValueError(f"No payroll constants for year={tax_year} province={province}")

    row = dict(result)
    fed_brackets  = row["fed_brackets"]  if isinstance(row["fed_brackets"],  list) else json.loads(row["fed_brackets"])
    prov_brackets = row["prov_brackets"] if isinstance(row["prov_brackets"], list) else json.loads(row["prov_brackets"])
    prov_surtax   = row["prov_surtax"]   if isinstance(row["prov_surtax"],   dict) else json.loads(row["prov_surtax"])

    return PayrollConstants(
        tax_year=row["tax_year"],
        province=row["province"],
        cpp_rate=float(row["cpp_rate"]),
        cpp_employee_max=float(row["cpp_employee_max"]),
        cpp_basic_exemption=float(row["cpp_basic_exemption"]),
        ei_rate=float(row["ei_rate"]),
        ei_employee_max=float(row["ei_employee_max"]),
        ei_insurable_max=float(row["ei_insurable_max"]),
        fed_brackets=fed_brackets,
        prov_brackets=prov_brackets,
        prov_surtax=prov_surtax,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Profile CRUD
# ──────────────────────────────────────────────────────────────────────────────

def get_payroll_profile(shop_employee_id: int) -> Optional[Dict[str, Any]]:
    """Return the payroll profile for a shop_employee, or None."""
    with SessionLocal() as session:
        row = (
            session.query(EmployeePayrollProfile)
            .filter(EmployeePayrollProfile.shop_employee_id == shop_employee_id)
            .first()
        )
        if row is None:
            return None
        return _row_to_dict(row)


def get_payroll_profile_by_name(shop_id: int, employee_name: str) -> Optional[Dict[str, Any]]:
    """Resolve an employee name to their payroll profile."""
    with SessionLocal() as session:
        se = (
            session.query(ShopEmployee)
            .join(ShopEmployee.user)
            .filter(
                ShopEmployee.shop_id == shop_id,
                ShopEmployee.is_active == True,
            )
            .all()
        )
        target = None
        name_lower = employee_name.strip().lower()
        for emp in se:
            full_name = (getattr(emp.user, "full_name", None) or "").lower()
            uname = (getattr(emp.user, "username", None) or "").lower()
            if name_lower in full_name or name_lower in uname:
                target = emp
                break
        if target is None:
            return None
        row = (
            session.query(EmployeePayrollProfile)
            .filter(EmployeePayrollProfile.shop_employee_id == target.id)
            .first()
        )
        return _row_to_dict(row) if row else None


def create_payroll_profile(
    shop_employee_id: int,
    shop_id: int,
    pay_type: str = "hourly",
    hourly_rate: Optional[float] = None,
    annual_salary: Optional[float] = None,
    pay_frequency: str = "biweekly",
    province: str = "ON",
    hire_date: Optional[date] = None,
    sin_encrypted: Optional[str] = None,
    sin_last4: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new EmployeePayrollProfile row."""
    with SessionLocal() as session:
        profile = EmployeePayrollProfile(
            shop_employee_id=shop_employee_id,
            shop_id=shop_id,
            pay_type=pay_type,
            hourly_rate=hourly_rate,
            annual_salary=annual_salary,
            pay_frequency=pay_frequency,
            province=province,
            hire_date=hire_date or date.today(),
            sin_encrypted=sin_encrypted,
            sin_last4=sin_last4,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return _row_to_dict(profile)


def update_payroll_profile_field(
    shop_employee_id: int, field: str, value: Any
) -> Dict[str, Any]:
    """Update a single field on an EmployeePayrollProfile."""
    _ALLOWED = {
        "pay_type", "hourly_rate", "annual_salary", "pay_frequency",
        "province", "td1_federal_claim", "td1_prov_claim", "additional_tax",
        "termination_date", "sin_encrypted", "sin_last4",
    }
    if field not in _ALLOWED:
        raise ValueError(f"Field {field!r} is not updatable via this function.")
    with SessionLocal() as session:
        row = (
            session.query(EmployeePayrollProfile)
            .filter(EmployeePayrollProfile.shop_employee_id == shop_employee_id)
            .first()
        )
        if row is None:
            raise ValueError(f"No payroll profile for shop_employee_id={shop_employee_id}")
        setattr(row, field, value)
        row.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return _row_to_dict(row)


def set_termination_date(shop_employee_id: int, termination_date: date) -> Dict[str, Any]:
    """Record a termination date on the payroll profile."""
    return update_payroll_profile_field(shop_employee_id, "termination_date", termination_date)


# ──────────────────────────────────────────────────────────────────────────────
# Payslip generation
# ──────────────────────────────────────────────────────────────────────────────

def draft_payslip(
    shop_id: int,
    shop_employee_id: int,
    period_start: date,
    period_end: date,
    pay_date: date,
    regular_hours: float,
    overtime_hours: float = 0.0,
    tips_amount: float = 0.0,
) -> Dict[str, Any]:
    """
    Compute and INSERT a draft payslip row.

    Uses the employee's payroll profile + the payroll_constants for their
    province and the current tax year.  Returns the inserted row as a dict.
    """
    with SessionLocal() as session:
        profile = (
            session.query(EmployeePayrollProfile)
            .filter(EmployeePayrollProfile.shop_employee_id == shop_employee_id)
            .first()
        )
        if profile is None:
            raise ValueError(
                f"No payroll profile for shop_employee_id={shop_employee_id}. "
                "Run onboarding first."
            )

        constants = _load_constants(session, period_start.year, profile.province)

        inp = PayPeriodInput(
            regular_hours=regular_hours,
            hourly_rate=float(profile.hourly_rate or 0),
            pay_type=profile.pay_type,
            annual_salary=float(profile.annual_salary or 0),
            pay_frequency=profile.pay_frequency,
            overtime_hours=overtime_hours,
            tips_amount=tips_amount,
            td1_federal_claim=float(profile.td1_federal_claim),
            td1_prov_claim=float(profile.td1_prov_claim),
            additional_tax=float(profile.additional_tax),
            ytd_cpp=float(profile.ytd_cpp),
            ytd_ei=float(profile.ytd_ei),
            ytd_gross=float(profile.ytd_gross),
        )

        result: PayslipResult = calculate_payslip(inp, constants)

        session.execute(
            text("""
            INSERT INTO payslips (
                shop_id, shop_employee_id,
                period_start, period_end, pay_date,
                regular_hours, overtime_hours, gross_pay, tips_included,
                cpp_deduction, ei_deduction, fed_tax, prov_tax,
                other_deductions, total_deductions, net_pay,
                status, created_at, updated_at
            ) VALUES (
                :shop_id, :shop_employee_id,
                :period_start, :period_end, :pay_date,
                :regular_hours, :overtime_hours, :gross_pay, :tips_included,
                :cpp, :ei, :fed_tax, :prov_tax,
                :other_ded, :total_ded, :net_pay,
                'draft', NOW(), NOW()
            )
            """),
            {
                "shop_id": shop_id,
                "shop_employee_id": shop_employee_id,
                "period_start": period_start,
                "period_end": period_end,
                "pay_date": pay_date,
                "regular_hours": regular_hours,
                "overtime_hours": overtime_hours,
                "gross_pay": result.gross_pay,
                "tips_included": result.tips_included,
                "cpp": result.cpp_deduction,
                "ei": result.ei_deduction,
                "fed_tax": result.fed_tax,
                "prov_tax": result.prov_tax,
                "other_ded": result.other_deductions,
                "total_ded": result.total_deductions,
                "net_pay": result.net_pay,
            },
        )
        session.commit()

        row = session.execute(
            text("SELECT * FROM payslips WHERE shop_employee_id=:id ORDER BY id DESC LIMIT 1"),
            {"id": shop_employee_id},
        ).fetchone()
        return dict(row)


def list_payslips(
    shop_id: int,
    employee_name: Optional[str] = None,
    period: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Retrieve payslips for a shop.  Supports filtering by employee name,
    period ("last pay period", "YYYY-MM-DD:YYYY-MM-DD"), or status.
    """
    with SessionLocal() as session:
        # Resolve employee name → shop_employee_id
        se_id_filter = None
        if employee_name:
            se = (
                session.query(ShopEmployee)
                .join(ShopEmployee.user)
                .filter(ShopEmployee.shop_id == shop_id, ShopEmployee.is_active == True)
                .all()
            )
            name_lower = employee_name.strip().lower()
            for emp in se:
                full = (getattr(emp.user, "full_name", None) or "").lower()
                uname = (getattr(emp.user, "username", None) or "").lower()
                if name_lower in full or name_lower in uname:
                    se_id_filter = emp.id
                    break

        # Parse period
        date_filter = {}
        if period:
            p_lower = period.lower().strip()
            if p_lower in ("last pay period", "last period", "last payroll"):
                row = session.execute(
                    text("SELECT MAX(period_end) FROM payslips WHERE shop_id=:s"),
                    {"s": shop_id},
                ).fetchone()
                last_end = row[0] if row and row[0] else None
                if last_end:
                    date_filter["end"] = last_end
                    # assume biweekly — approximate
                    date_filter["start"] = last_end - timedelta(days=14)
            elif ":" in period:
                parts = period.split(":", 1)
                try:
                    date_filter["start"] = date.fromisoformat(parts[0].strip())
                    date_filter["end"]   = date.fromisoformat(parts[1].strip())
                except ValueError:
                    pass  # ignore parse error, return unfiltered by date

        # Build query
        q = "SELECT * FROM payslips WHERE shop_id=:s"
        params: Dict[str, Any] = {"s": shop_id}
        if se_id_filter:
            q += " AND shop_employee_id=:se_id"
            params["se_id"] = se_id_filter
        if "start" in date_filter:
            q += " AND period_end >= :pstart"
            params["pstart"] = date_filter["start"]
        if "end" in date_filter:
            q += " AND period_end <= :pend"
            params["pend"] = date_filter["end"]
        if status:
            q += " AND status=:status"
            params["status"] = status
        q += " ORDER BY period_end DESC, id DESC LIMIT :lim"
        params["lim"] = limit

        rows = session.execute(text(q), params).fetchall()
        return [dict(r) for r in rows]


def approve_payslip(payslip_id: int, approved_by_user_id: int) -> Dict[str, Any]:
    """
    Mark a draft payslip as 'approved' and update YTD accumulators on the
    payroll profile.
    """
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT * FROM payslips WHERE id=:id"), {"id": payslip_id}
        ).fetchone()
        if row is None:
            raise ValueError(f"Payslip id={payslip_id} not found.")
        if dict(row)["status"] != "draft":
            raise ValueError(f"Payslip id={payslip_id} is not in 'draft' status.")

        session.execute(
            text("""UPDATE payslips SET status='approved', approved_by=:u, approved_at=NOW(), updated_at=NOW()
               WHERE id=:id"""),
            {"u": approved_by_user_id, "id": payslip_id},
        )

        # Update YTD accumulators
        d = dict(row)
        session.execute(
            text("""UPDATE employee_payroll_profiles SET
                ytd_gross    = ytd_gross + :gross,
                ytd_cpp      = ytd_cpp   + :cpp,
                ytd_ei       = ytd_ei    + :ei,
                ytd_fed_tax  = ytd_fed_tax + :fed,
                ytd_prov_tax = ytd_prov_tax + :prov,
                ytd_tips     = ytd_tips  + :tips,
                updated_at   = NOW()
               WHERE shop_employee_id = :se_id"""),
            {
                "gross": d["gross_pay"],
                "cpp": d["cpp_deduction"],
                "ei": d["ei_deduction"],
                "fed": d["fed_tax"],
                "prov": d["prov_tax"],
                "tips": d["tips_included"],
                "se_id": d["shop_employee_id"],
            },
        )
        session.commit()
        updated = session.execute(text("SELECT * FROM payslips WHERE id=:id"), {"id": payslip_id}).fetchone()
        return dict(updated)


# ──────────────────────────────────────────────────────────────────────────────
# Tips
# ──────────────────────────────────────────────────────────────────────────────

def log_tip(
    shop_id: int,
    employee_name: str,
    amount: float,
    tip_type: str = "card",
    note: Optional[str] = None,
    tip_date: Optional[date] = None,
    queue_item_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Insert a tip_log entry for a named employee.
    Resolves employee_name → shop_employee_id.
    """
    if amount <= 0:
        raise ValueError("Tip amount must be positive.")
    with SessionLocal() as session:
        se = (
            session.query(ShopEmployee)
            .join(ShopEmployee.user)
            .filter(ShopEmployee.shop_id == shop_id, ShopEmployee.is_active == True)
            .all()
        )
        target = None
        name_lower = employee_name.strip().lower()
        for emp in se:
            full = (getattr(emp.user, "full_name", None) or "").lower()
            uname = (getattr(emp.user, "username", None) or "").lower()
            if name_lower in full or name_lower in uname:
                target = emp
                break
        if target is None:
            raise ValueError(f"No active employee named '{employee_name}' in shop {shop_id}.")

        session.execute(
            text("""INSERT INTO tips_log (shop_id, shop_employee_id, queue_item_id, amount, tip_type, note, tip_date)
               VALUES (:shop_id, :se_id, :qi_id, :amt, :ttype, :note, :tdate)"""),
            {
                "shop_id": shop_id,
                "se_id": target.id,
                "qi_id": queue_item_id,
                "amt": amount,
                "ttype": tip_type,
                "note": note,
                "tdate": tip_date or date.today(),
            },
        )
        session.commit()
        row = session.execute(
            text("SELECT * FROM tips_log WHERE shop_id=:s ORDER BY id DESC LIMIT 1"),
            {"s": shop_id},
        ).fetchone()
        return dict(row)


def get_tips_summary(
    shop_id: int,
    employee_name: Optional[str] = None,
    since: Optional[date] = None,
) -> Dict[str, Any]:
    """Return aggregated tips for a shop (optionally filtered by employee and date range)."""
    with SessionLocal() as session:
        se_id_filter = None
        if employee_name:
            se = (
                session.query(ShopEmployee)
                .join(ShopEmployee.user)
                .filter(ShopEmployee.shop_id == shop_id, ShopEmployee.is_active == True)
                .all()
            )
            name_lower = employee_name.strip().lower()
            for emp in se:
                full = (getattr(emp.user, "full_name", None) or "").lower()
                uname = (getattr(emp.user, "username", None) or "").lower()
                if name_lower in full or name_lower in uname:
                    se_id_filter = emp.id
                    break

        q = "SELECT SUM(amount) AS total, COUNT(*) AS count FROM tips_log WHERE shop_id=:s"
        params: Dict[str, Any] = {"s": shop_id}
        if se_id_filter:
            q += " AND shop_employee_id=:se_id"
            params["se_id"] = se_id_filter
        if since:
            q += " AND tip_date >= :since"
            params["since"] = since
        row = session.execute(text(q), params).fetchone()
        return {
            "total": float(row[0] or 0),
            "count": int(row[1] or 0),
            "since": since.isoformat() if since else None,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Tip pooling
# ──────────────────────────────────────────────────────────────────────────────

def create_tip_pool(
    shop_id: int,
    pool_date: date,
    total_amount: float,
    split_method: str = "hours_worked",
) -> Dict[str, Any]:
    """Create a new tip pool row (status='open')."""
    with SessionLocal() as session:
        session.execute(
            text("""INSERT INTO tip_pools (shop_id, pool_date, total_amount, split_method)
               VALUES (:s, :d, :a, :m)"""),
            {"s": shop_id, "d": pool_date, "a": total_amount, "m": split_method},
        )
        session.commit()
        row = session.execute(
            text("SELECT * FROM tip_pools WHERE shop_id=:s ORDER BY id DESC LIMIT 1"),
            {"s": shop_id},
        ).fetchone()
        return dict(row)


def split_tip_pool(
    tip_pool_id: int,
    splits: List[Dict[str, Any]],  # [{"shop_employee_id": int, "hours_worked": float, "split_amount": float}]
    approved_by_user_id: int,
) -> Dict[str, Any]:
    """
    Insert tip_pool_split rows and mark the pool as 'split'.
    Also inserts 'pooled' tips_log entries for each employee.
    """
    with SessionLocal() as session:
        pool = session.execute(
            text("SELECT * FROM tip_pools WHERE id=:id"), {"id": tip_pool_id}
        ).fetchone()
        if pool is None:
            raise ValueError(f"Tip pool id={tip_pool_id} not found.")
        pool_dict = dict(pool)
        if pool_dict["status"] not in ("open", "splitting"):
            raise ValueError(f"Tip pool {tip_pool_id} is already {pool_dict['status']}.")

        for s in splits:
            session.execute(
                text("""INSERT INTO tip_pool_splits (tip_pool_id, shop_employee_id, hours_worked, split_amount)
                   VALUES (:pid, :se_id, :hrs, :amt)"""),
                {"pid": tip_pool_id, "se_id": s["shop_employee_id"], "hrs": s.get("hours_worked", 0), "amt": s["split_amount"]},
            )
            # Log each split as a 'pooled' tip
            session.execute(
                text("""INSERT INTO tips_log (shop_id, shop_employee_id, amount, tip_type, note, tip_date)
                   VALUES (:shop_id, :se_id, :amt, 'pooled', :note, :d)"""),
                {
                    "shop_id": pool_dict["shop_id"],
                    "se_id": s["shop_employee_id"],
                    "amt": s["split_amount"],
                    "note": f"Pool #{tip_pool_id} split",
                    "d": pool_dict["pool_date"],
                },
            )

        session.execute(
            text("""UPDATE tip_pools SET status='split', approved_by=:u, approved_at=NOW(), updated_at=NOW()
               WHERE id=:id"""),
            {"u": approved_by_user_id, "id": tip_pool_id},
        )
        session.commit()
        updated = session.execute(text("SELECT * FROM tip_pools WHERE id=:id"), {"id": tip_pool_id}).fetchone()
        return dict(updated)


# ──────────────────────────────────────────────────────────────────────────────
# Remittances
# ──────────────────────────────────────────────────────────────────────────────

def upsert_remittance(
    shop_id: int,
    period_start: date,
    period_end: date,
    due_date: date,
    cpp_employee: float,
    cpp_employer: float,
    ei_employee: float,
    ei_employer: float,
    fed_tax: float,
    prov_tax: float,
) -> Dict[str, Any]:
    """
    Insert or update a remittance record for a pay period.
    Returns the upserted row.
    """
    total = round(cpp_employee + cpp_employer + ei_employee + ei_employer + fed_tax + prov_tax, 2)
    with SessionLocal() as session:
        existing = session.execute(
            text("SELECT id FROM remittances WHERE shop_id=:s AND period_start=:ps AND period_end=:pe"),
            {"s": shop_id, "ps": period_start, "pe": period_end},
        ).fetchone()
        if existing:
            session.execute(
                text("""UPDATE remittances SET
                    cpp_employee=:ce, cpp_employer=:cr, ei_employee=:ee, ei_employer=:er,
                    fed_tax=:ft, prov_tax=:pt, total_owing=:tot, due_date=:dd, updated_at=NOW()
                   WHERE id=:id"""),
                {
                    "ce": cpp_employee, "cr": cpp_employer,
                    "ee": ei_employee, "er": ei_employer,
                    "ft": fed_tax, "pt": prov_tax,
                    "tot": total, "dd": due_date, "id": existing[0],
                },
            )
            rid = existing[0]
        else:
            session.execute(
                text("""INSERT INTO remittances
                   (shop_id, period_start, period_end, due_date,
                    cpp_employee, cpp_employer, ei_employee, ei_employer,
                    fed_tax, prov_tax, total_owing)
                   VALUES (:s, :ps, :pe, :dd, :ce, :cr, :ee, :er, :ft, :pt, :tot)"""),
                {
                    "s": shop_id, "ps": period_start, "pe": period_end, "dd": due_date,
                    "ce": cpp_employee, "cr": cpp_employer,
                    "ee": ei_employee,  "er": ei_employer,
                    "ft": fed_tax, "pt": prov_tax, "tot": total,
                },
            )
            rid = session.execute(
                text("SELECT id FROM remittances WHERE shop_id=:s ORDER BY id DESC LIMIT 1"),
                {"s": shop_id},
            ).fetchone()[0]
        session.commit()
        row = session.execute(text("SELECT * FROM remittances WHERE id=:id"), {"id": rid}).fetchone()
        return dict(row)


def get_pending_remittances(shop_id: int) -> List[Dict[str, Any]]:
    """Return all pending/overdue remittances ordered by due_date ascending."""
    with SessionLocal() as session:
        rows = session.execute(
            text("""SELECT * FROM remittances WHERE shop_id=:s AND status IN ('pending','overdue')
               ORDER BY due_date ASC"""),
            {"s": shop_id},
        ).fetchall()
        return [dict(r) for r in rows]


def remittance_due_soon(shop_id: int, days_ahead: int = 3) -> List[Dict[str, Any]]:
    """Return pending remittances due within the next N days."""
    with SessionLocal() as session:
        cutoff = date.today() + timedelta(days=days_ahead)
        rows = session.execute(
            text("""SELECT * FROM remittances
               WHERE shop_id=:s AND status='pending' AND due_date <= :cutoff
               ORDER BY due_date ASC"""),
            {"s": shop_id, "cutoff": cutoff},
        ).fetchall()
        return [dict(r) for r in rows]


def mark_remittance_paid(remittance_id: int) -> Dict[str, Any]:
    """Mark a remittance record as paid."""
    with SessionLocal() as session:
        session.execute(
            text("UPDATE remittances SET status='paid', paid_at=NOW(), updated_at=NOW() WHERE id=:id"),
            {"id": remittance_id},
        )
        session.commit()
        row = session.execute(text("SELECT * FROM remittances WHERE id=:id"), {"id": remittance_id}).fetchone()
        return dict(row)


# ──────────────────────────────────────────────────────────────────────────────
# T4 records
# ──────────────────────────────────────────────────────────────────────────────

def draft_t4(shop_id: int, shop_employee_id: int, tax_year: int) -> Dict[str, Any]:
    """
    Build a draft T4 from the YTD accumulators on the payroll profile.
    Inserts (or replaces) the t4_records row.
    """
    with SessionLocal() as session:
        profile = (
            session.query(EmployeePayrollProfile)
            .filter(EmployeePayrollProfile.shop_employee_id == shop_employee_id)
            .first()
        )
        if profile is None:
            raise ValueError(f"No payroll profile for shop_employee_id={shop_employee_id}")

        # Use current YTD if year matches, else sum payslips for that year
        if int(profile.ytd_year) == tax_year:
            emp_income = float(profile.ytd_gross)
            cpp_contr  = float(profile.ytd_cpp)
            ei_prem    = float(profile.ytd_ei)
            fed_tax    = float(profile.ytd_fed_tax)
            prov_tax   = float(profile.ytd_prov_tax)
            tips       = float(profile.ytd_tips)
        else:
            rows = session.execute(
                text("""SELECT SUM(gross_pay), SUM(cpp_deduction), SUM(ei_deduction),
                          SUM(fed_tax), SUM(prov_tax), SUM(tips_included)
                   FROM payslips
                   WHERE shop_employee_id=:se_id AND status='approved'
                     AND EXTRACT(YEAR FROM period_start)=:y"""),
                {"se_id": shop_employee_id, "y": tax_year},
            ).fetchone()
            emp_income = float(rows[0] or 0)
            cpp_contr  = float(rows[1] or 0)
            ei_prem    = float(rows[2] or 0)
            fed_tax    = float(rows[3] or 0)
            prov_tax   = float(rows[4] or 0)
            tips       = float(rows[5] or 0)

        existing = session.execute(
            text("SELECT id FROM t4_records WHERE shop_employee_id=:se AND tax_year=:y"),
            {"se": shop_employee_id, "y": tax_year},
        ).fetchone()

        values = {
            "emp_income": emp_income,
            "cpp": cpp_contr,
            "ei": ei_prem,
            "fed_tax": fed_tax + prov_tax,
            "ei_insurable": emp_income,
            "cpp_pensionable": emp_income,
            "tips": tips,
            "prov": profile.province,
            "shop_id": shop_id,
            "se_id": shop_employee_id,
            "yr": tax_year,
        }

        if existing:
            session.execute(
                text("""UPDATE t4_records SET
                    box_14_employment_income=:emp_income,
                    box_16_cpp_contributions=:cpp,
                    box_18_ei_premiums=:ei,
                    box_22_income_tax_deducted=:fed_tax,
                    box_24_ei_insurable_earnings=:ei_insurable,
                    box_26_cpp_pensionable_earnings=:cpp_pensionable,
                    box_40_tips_gratuities=:tips,
                    province=:prov,
                    updated_at=NOW()
                   WHERE shop_employee_id=:se_id AND tax_year=:yr"""),
                values,
            )
            rid = existing[0]
        else:
            session.execute(
                text("""INSERT INTO t4_records
                   (shop_id, shop_employee_id, tax_year,
                    box_14_employment_income, box_16_cpp_contributions,
                    box_18_ei_premiums, box_22_income_tax_deducted,
                    box_24_ei_insurable_earnings, box_26_cpp_pensionable_earnings,
                    box_40_tips_gratuities, province)
                   VALUES (:shop_id,:se_id,:yr,:emp_income,:cpp,:ei,:fed_tax,
                           :ei_insurable,:cpp_pensionable,:tips,:prov)"""),
                values,
            )
            rid = session.execute(
                text("SELECT id FROM t4_records WHERE shop_employee_id=:se AND tax_year=:yr"),
                {"se": shop_employee_id, "yr": tax_year},
            ).fetchone()[0]

        session.commit()
        row = session.execute(text("SELECT * FROM t4_records WHERE id=:id"), {"id": rid}).fetchone()
        return dict(row)


def list_t4_records(shop_id: int, tax_year: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return T4 records for a shop, optionally filtered by year."""
    with SessionLocal() as session:
        q = "SELECT * FROM t4_records WHERE shop_id=:s"
        params: Dict[str, Any] = {"s": shop_id}
        if tax_year:
            q += " AND tax_year=:yr"
            params["yr"] = tax_year
        q += " ORDER BY tax_year DESC, shop_employee_id ASC"
        rows = session.execute(text(q), params).fetchall()
        return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────────────────────
# Annual YTD reset (called by Temporal AnnualPayrollResetWorkflow on Jan 1)
# ──────────────────────────────────────────────────────────────────────────────

def reset_ytd_for_shop(shop_id: int, new_year: int) -> int:
    """
    Zero out YTD accumulators for all active employees of a shop.
    Returns the number of rows updated.
    """
    with SessionLocal() as session:
        result = session.execute(
            text("""UPDATE employee_payroll_profiles SET
                ytd_gross=0, ytd_cpp=0, ytd_ei=0,
                ytd_fed_tax=0, ytd_prov_tax=0, ytd_tips=0,
                ytd_year=:yr, updated_at=NOW()
               WHERE shop_id=:s"""),
            {"yr": new_year, "s": shop_id},
        )
        session.commit()
        return result.rowcount
