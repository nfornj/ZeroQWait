"""
seed_payroll_demo.py — One-shot script that creates demo payroll data for the first active shop.

Run from backend/:
    python scripts/seed_payroll_demo.py

Steps:
  1. Find the first active shop.
  2. For each active employee in that shop:
       a. Create a payroll profile if one doesn't exist (hourly rate $22, ON, semi_monthly).
       b. Draft a payslip for May 1-15, 2026 (80 regular hours).
       c. Approve the payslip.
  3. Print a summary table.
"""

from __future__ import annotations

import sys
import os
import decimal
from datetime import date

# Add backend/ to path so SQLAlchemy models resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from modules.employees.models import ShopEmployee, EmployeePayrollProfile
from sqlalchemy import text

PERIOD_START = date(2026, 5, 1)
PERIOD_END   = date(2026, 5, 15)
PAY_DATE     = date(2026, 5, 18)
REGULAR_HOURS = 80.0
HOURLY_RATE   = decimal.Decimal("22.00")
PROVINCE      = "ON"


def main():
    with SessionLocal() as session:
        # 1. Find first active shop
        shop_row = session.execute(
            text("SELECT id, name FROM shops WHERE is_active = TRUE ORDER BY id LIMIT 1")
        ).fetchone()
        if not shop_row:
            print("[ERROR] No active shops found. Please seed shop data first.")
            sys.exit(1)
        shop_id   = shop_row.id
        shop_name = shop_row.name
        print(f"[INFO] Using shop: {shop_name} (id={shop_id})")

        # 2. Find active employees
        employees = (
            session.query(ShopEmployee)
            .filter(ShopEmployee.shop_id == shop_id, ShopEmployee.is_active == True)
            .all()
        )
        if not employees:
            print("[ERROR] No active employees found. Please seed employee data first.")
            sys.exit(1)
        print(f"[INFO] Found {len(employees)} active employee(s).")

        results = []
        for se in employees:
            user_row = session.execute(
                text("SELECT username, full_name FROM users WHERE id = :uid"),
                {"uid": se.user_id},
            ).fetchone()
            name = (
                (user_row.full_name or "").strip() if user_row and user_row.full_name else ""
            ) or (user_row.username if user_row else f"Employee #{se.id}")

            # 2a. Ensure payroll profile exists
            profile = (
                session.query(EmployeePayrollProfile)
                .filter(EmployeePayrollProfile.shop_employee_id == se.id)
                .first()
            )
            if not profile:
                profile = EmployeePayrollProfile(
                    shop_employee_id=se.id,
                    shop_id=shop_id,
                    pay_type="hourly",
                    hourly_rate=HOURLY_RATE,
                    pay_frequency="semi_monthly",
                    province=PROVINCE,
                    sin_last4="0000",
                    hire_date=date(2025, 1, 1),
                )
                session.add(profile)
                session.flush()
                print(f"  [CREATE] Payroll profile for {name}")
            else:
                print(f"  [SKIP]   Payroll profile already exists for {name}")

            # 2b. Check if payslip already exists for this period
            existing = session.execute(
                text(
                    "SELECT id FROM payslips "
                    "WHERE shop_employee_id = :se_id "
                    "  AND period_start = :ps AND period_end = :pe"
                ),
                {"se_id": se.id, "ps": PERIOD_START, "pe": PERIOD_END},
            ).fetchone()
            if existing:
                print(f"  [SKIP]   Payslip already exists for {name} (id={existing.id})")
                results.append({"name": name, "payslip_id": existing.id, "action": "skipped"})
                continue

            # Draft payslip via the payroll_tools function
            from agents.tools import payroll_tools
            try:
                slip = payroll_tools.draft_payslip(
                    shop_id=shop_id,
                    shop_employee_id=se.id,
                    period_start=PERIOD_START,
                    period_end=PERIOD_END,
                    pay_date=PAY_DATE,
                    regular_hours=REGULAR_HOURS,
                )
                slip_id = slip["id"]
                print(f"  [DRAFT]  Payslip {slip_id} for {name}: "
                      f"gross=${float(slip.get('gross_pay', 0)):.2f} "
                      f"net=${float(slip.get('net_pay', 0)):.2f}")

                # 2c. Approve the payslip
                # Get the owner user_id for approved_by
                owner_row = session.execute(
                    text("SELECT owner_id FROM shops WHERE id = :sid"),
                    {"sid": shop_id},
                ).fetchone()
                approved_by = owner_row.owner_id if owner_row else 1

                approved = payroll_tools.approve_payslip(slip_id, approved_by_user_id=approved_by)
                print(f"  [APPROVE] Payslip {slip_id} approved → net=${float(approved.get('net_pay', 0)):.2f}")
                results.append({"name": name, "payslip_id": slip_id, "action": "created+approved",
                                 "gross": float(slip.get("gross_pay", 0)),
                                 "net": float(approved.get("net_pay", 0))})
            except Exception as exc:
                print(f"  [ERROR]  Failed for {name}: {exc}")
                results.append({"name": name, "payslip_id": None, "action": f"error: {exc}"})

        session.commit()

    # Print summary
    print("\n" + "=" * 60)
    print(f"{'Employee':<25} {'Payslip ID':>12} {'Action':<20}")
    print("-" * 60)
    for r in results:
        pid = str(r.get("payslip_id") or "—")
        print(f"{r['name']:<25} {pid:>12} {r['action']:<20}")
    print("=" * 60)
    print("Done. Visit /employees → Payroll tab to see payslips.")


if __name__ == "__main__":
    main()
