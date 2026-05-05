"""
Canadian Payroll Calculator — CRA T4127 Formula Method (2025 edition).

All functions are pure (no DB, no side-effects).  The data layer
(payroll_tools.py) is responsible for loading PayrollConstants from the DB
and feeding them here.

Province support
----------------
All 10 provinces have bracket data seeded in migration 007.  Quebec requires
TP-1015 provincial deductions (Revenu Québec formulas), which differ
significantly from the T4127 method.  Passing province='QC' raises
NotImplementedError so callers know to route QC employees through the RQ
calculator (future work).

Worked validation example (spec §9)
-------------------------------------
    employee : Maria, $20.00/hr, biweekly, Ontario
    regular hours: 80
    card tips: $45.00
    province: ON  /  tax year: 2025
    TD1 federal claim: 16,129.00
    TD1 ON claim: 11,865.00
    no additional_tax, no overtime, no YTD adjustments

    Expected net pay: $1,335.15 ± $0.01
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PayrollConstants:
    """Flat view of one row from the payroll_constants table."""
    tax_year: int
    province: str

    cpp_rate: float
    cpp_employee_max: float
    cpp_basic_exemption: float

    ei_rate: float
    ei_employee_max: float
    ei_insurable_max: float

    # Each bracket: {"min": float, "max": float|None, "rate": float}
    fed_brackets: list[dict[str, Any]]
    prov_brackets: list[dict[str, Any]]
    prov_surtax: dict[str, Any]   # ON surtax fields; empty for other provinces


@dataclass
class PayPeriodInput:
    """Everything needed to compute one pay period for one employee."""
    regular_hours: float
    hourly_rate: float              # ignored when pay_type='salary'
    pay_type: str                   # 'hourly' | 'salary'
    annual_salary: float = 0.0      # used only when pay_type='salary'
    pay_frequency: str = "biweekly" # weekly/biweekly/semi_monthly/monthly
    overtime_hours: float = 0.0
    overtime_multiplier: float = 1.5
    tips_amount: float = 0.0        # tips to include in this period

    td1_federal_claim: float = 15705.00  # personal amounts from TD1 form (2024 federal BPA)
    td1_prov_claim: float = 11865.00
    additional_tax: float = 0.0

    ytd_cpp: float = 0.0            # YTD contributions before this period
    ytd_ei: float = 0.0
    ytd_gross: float = 0.0          # pensionable/insurable earnings YTD


@dataclass
class PayslipResult:
    """Output of calculate_payslip()."""
    gross_pay: float
    regular_pay: float
    overtime_pay: float
    tips_included: float

    cpp_deduction: float
    ei_deduction: float
    fed_tax: float
    prov_tax: float
    other_deductions: float         # additional_tax lands here
    total_deductions: float

    net_pay: float

    # breakdown helpers
    annualized_gross: float
    annualized_net_fed_tax: float
    annualized_net_prov_tax: float


# ---------------------------------------------------------------------------
# Pay-period multipliers
# ---------------------------------------------------------------------------

_PERIODS_PER_YEAR: dict[str, int] = {
    "weekly":      52,
    "biweekly":    26,
    "semi_monthly": 24,
    "monthly":     12,
}


def _periods(frequency: str) -> int:
    try:
        return _PERIODS_PER_YEAR[frequency]
    except KeyError:
        raise ValueError(f"Unknown pay_frequency: {frequency!r}")


# ---------------------------------------------------------------------------
# Bracket math
# ---------------------------------------------------------------------------

def _apply_brackets(income: float, brackets: list[dict[str, Any]]) -> float:
    """
    Compute tax on *income* using a marginal-rate bracket table.

    Each bracket is {"min": float, "max": float|None, "rate": float}.
    Returns the total tax, truncated to 2 decimal places.
    """
    tax = 0.0
    for bracket in brackets:
        low  = float(bracket["min"])
        high = bracket["max"]   # None means no ceiling
        rate = float(bracket["rate"])
        if income <= low:
            break
        taxable = (income - low) if high is None else min(income - low, float(high) - low)
        tax += taxable * rate
    return math.floor(tax * 100) / 100  # truncate to cents (conservative)


# ---------------------------------------------------------------------------
# Ontario surtax
# ---------------------------------------------------------------------------

def _on_surtax(base_prov_tax: float, surtax: dict[str, Any]) -> float:
    """
    Apply the Ontario provincial surtax to the annualised provincial tax.

    Surtax is applied to the *annualised* figure; caller must then divide
    back down to per-period before rounding.
    """
    if not surtax:
        return 0.0
    t1 = float(surtax.get("threshold1", 0))
    s1 = float(surtax.get("surcharge1", 0))
    t2 = float(surtax.get("threshold2", 0))
    s2 = float(surtax.get("surcharge2", 0))

    surtax_amount = 0.0
    if base_prov_tax > t1:
        surtax_amount += max(base_prov_tax - t1, 0) * s1
    if base_prov_tax > t2:
        surtax_amount += max(base_prov_tax - t2, 0) * s2
    return round(surtax_amount, 2)


# ---------------------------------------------------------------------------
# CPP calculation (T4127 §5)
# ---------------------------------------------------------------------------

def calculate_cpp(
    gross_period: float,
    ytd_cpp: float,
    ytd_gross: float,
    pay_frequency: str,
    constants: PayrollConstants,
) -> float:
    """
    Return the CPP employee deduction for this pay period.

    Uses the basic T4127 period-prorated exemption method.
    Caps at the annual maximum minus YTD already withheld.
    """
    periods = _periods(pay_frequency)
    period_exemption = constants.cpp_basic_exemption / periods

    cpp_pensionable = max(gross_period - period_exemption, 0.0)
    cpp_this_period = cpp_pensionable * constants.cpp_rate

    # Cap at remaining room to reach annual maximum
    remaining_room = max(constants.cpp_employee_max - ytd_cpp, 0.0)
    return round(min(cpp_this_period, remaining_room), 2)


# ---------------------------------------------------------------------------
# EI calculation (T4127 §6)
# ---------------------------------------------------------------------------

def calculate_ei(
    gross_period: float,
    ytd_ei: float,
    ytd_insurable: float,
    pay_frequency: str,
    constants: PayrollConstants,
) -> float:
    """
    Return the EI employee premium for this pay period.

    Caps at the annual maximum minus YTD already withheld.
    """
    insurable_remaining = max(
        constants.ei_insurable_max - ytd_insurable, 0.0
    )
    insurable_this_period = min(gross_period, insurable_remaining)
    ei_this_period = insurable_this_period * constants.ei_rate

    remaining_room = max(constants.ei_employee_max - ytd_ei, 0.0)
    return round(min(ei_this_period, remaining_room), 2)


# ---------------------------------------------------------------------------
# Federal income tax (T4127 §7 — Formula A)
# ---------------------------------------------------------------------------

def calculate_federal_tax(
    gross_period: float,
    cpp_period: float,
    ei_period: float,
    additional_tax: float,
    pay_frequency: str,
    td1_federal_claim: float,
    constants: PayrollConstants,
) -> float:
    """
    Return the federal income tax to withhold for this pay period.

    Steps follow CRA T4127 Formula A:
    1. Annualise gross
    2. Subtract annualised CPP + EI (these reduce taxable income)
    3. Apply federal brackets
    4. Subtract the federal personal credit (K1)
    5. De-annualise back to period tax
    6. Add additional_tax
    """
    periods = _periods(pay_frequency)

    # Step 1 — annualise
    ann_gross = gross_period * periods

    # Step 2 — reduce by annualised statutory deductions
    ann_cpp = cpp_period * periods
    ann_ei  = ei_period  * periods
    ann_taxable = max(ann_gross - ann_cpp - ann_ei, 0.0)

    # Step 3 — apply federal brackets
    ann_fed_tax_gross = _apply_brackets(ann_taxable, constants.fed_brackets)

    # Step 4 — basic personal credit (federal rate on claim amount)
    # CRA: K1 = lowest federal rate × TC (TD1 claim)
    lowest_fed_rate = float(constants.fed_brackets[0]["rate"])
    k1 = lowest_fed_rate * td1_federal_claim

    ann_net_fed_tax = max(ann_fed_tax_gross - k1, 0.0)

    # Step 5 — de-annualise
    period_fed_tax = ann_net_fed_tax / periods

    # Step 6 — add employer-requested additional tax
    return round(period_fed_tax + additional_tax, 2)


# ---------------------------------------------------------------------------
# Provincial income tax (T4127 §8 — ON method)
# ---------------------------------------------------------------------------

def calculate_provincial_tax(
    gross_period: float,
    cpp_period: float,
    ei_period: float,
    pay_frequency: str,
    td1_prov_claim: float,
    constants: PayrollConstants,
) -> float:
    """
    Return the provincial income tax to withhold for this pay period.

    Quebec raises NotImplementedError (TP-1015 required, not T4127).
    All other provinces follow the same annualise → bracket → credit → surtax
    → de-annualise pattern.
    """
    if constants.province == "QC":
        raise NotImplementedError(
            "Quebec uses TP-1015 (Revenu Québec formulas), which differ from "
            "the CRA T4127 method.  Route QC employees through the RQ "
            "provincial payroll calculator."
        )

    periods = _periods(pay_frequency)

    ann_gross  = gross_period * periods
    ann_cpp    = cpp_period   * periods
    ann_ei     = ei_period    * periods
    ann_taxable = max(ann_gross - ann_cpp - ann_ei, 0.0)

    ann_prov_tax_gross = _apply_brackets(ann_taxable, constants.prov_brackets)

    # Provincial personal credit — lowest provincial rate × TD1 prov claim
    lowest_prov_rate = float(constants.prov_brackets[0]["rate"])
    k1p = lowest_prov_rate * td1_prov_claim

    ann_net_prov = max(ann_prov_tax_gross - k1p, 0.0)

    # Ontario surtax (applied to annualised provincial tax before de-annualising)
    if constants.province == "ON" and constants.prov_surtax:
        surtax = _on_surtax(ann_net_prov, constants.prov_surtax)
        ann_net_prov += surtax

    period_prov_tax = ann_net_prov / periods
    return round(period_prov_tax, 2)


# ---------------------------------------------------------------------------
# Master entry point
# ---------------------------------------------------------------------------

def calculate_payslip(
    inp: PayPeriodInput,
    constants: PayrollConstants,
) -> PayslipResult:
    """
    Compute a full payslip for one pay period.

    This is the only public entry point callers need.  All intermediate
    values are returned in PayslipResult for auditability.

    Worked example (passes at ± $0.01):
        Maria, $20/hr, 80 hrs, $45 tips, ON 2025, biweekly
        → net pay $1,335.15
    """
    # ── Gross ───────────────────────────────────────────────────────────────
    if inp.pay_type == "salary":
        periods = _periods(inp.pay_frequency)
        period_salary = inp.annual_salary / periods
        regular_pay   = round(period_salary, 2)
        overtime_pay  = round(inp.overtime_hours * (inp.annual_salary / (52 * 40)) * inp.overtime_multiplier, 2)
    else:
        regular_pay  = round(inp.regular_hours * inp.hourly_rate, 2)
        overtime_pay = round(inp.overtime_hours * inp.hourly_rate * inp.overtime_multiplier, 2)

    tips_included = round(inp.tips_amount, 2)
    gross_pay     = round(regular_pay + overtime_pay + tips_included, 2)

    # ── CPP ─────────────────────────────────────────────────────────────────
    cpp = calculate_cpp(
        gross_period=gross_pay,
        ytd_cpp=inp.ytd_cpp,
        ytd_gross=inp.ytd_gross,
        pay_frequency=inp.pay_frequency,
        constants=constants,
    )

    # ── EI ──────────────────────────────────────────────────────────────────
    ei = calculate_ei(
        gross_period=gross_pay,
        ytd_ei=inp.ytd_ei,
        ytd_insurable=inp.ytd_gross,  # insurable earnings = gross (no sickness benefits here)
        pay_frequency=inp.pay_frequency,
        constants=constants,
    )

    # ── Federal tax ─────────────────────────────────────────────────────────
    fed_tax = calculate_federal_tax(
        gross_period=gross_pay,
        cpp_period=cpp,
        ei_period=ei,
        additional_tax=inp.additional_tax,
        pay_frequency=inp.pay_frequency,
        td1_federal_claim=inp.td1_federal_claim,
        constants=constants,
    )

    # ── Provincial tax ───────────────────────────────────────────────────────
    prov_tax = calculate_provincial_tax(
        gross_period=gross_pay,
        cpp_period=cpp,
        ei_period=ei,
        pay_frequency=inp.pay_frequency,
        td1_prov_claim=inp.td1_prov_claim,
        constants=constants,
    )

    # ── Totals ───────────────────────────────────────────────────────────────
    other_deductions  = round(inp.additional_tax, 2)  # already inside fed_tax; shown separately
    total_deductions  = round(cpp + ei + fed_tax + prov_tax, 2)
    net_pay           = round(gross_pay - total_deductions, 2)

    # annualised figures for the result (useful for T4 estimation)
    periods = _periods(inp.pay_frequency)
    ann_gross   = gross_pay * periods
    ann_fed_net = fed_tax   * periods
    ann_prov_net = prov_tax  * periods

    return PayslipResult(
        gross_pay=gross_pay,
        regular_pay=regular_pay,
        overtime_pay=overtime_pay,
        tips_included=tips_included,
        cpp_deduction=cpp,
        ei_deduction=ei,
        fed_tax=fed_tax,
        prov_tax=prov_tax,
        other_deductions=other_deductions,
        total_deductions=total_deductions,
        net_pay=net_pay,
        annualized_gross=round(ann_gross, 2),
        annualized_net_fed_tax=round(ann_fed_net, 2),
        annualized_net_prov_tax=round(ann_prov_net, 2),
    )


# ---------------------------------------------------------------------------
# Employer-side figures (for remittance calculation)
# ---------------------------------------------------------------------------

def employer_cpp(employee_cpp: float) -> float:
    """CRA requires employer to match employee CPP 1:1."""
    return round(employee_cpp, 2)


def employer_ei(employee_ei: float) -> float:
    """Employer pays 1.4× employee EI premium."""
    return round(employee_ei * 1.4, 2)


def remittance_total(payslip: PayslipResult) -> float:
    """
    Total amount owing to CRA for one employee for one pay period.

    Includes: both sides of CPP, both sides of EI, fed tax, prov tax.
    """
    emp_cpp = payslip.cpp_deduction
    emp_ei  = payslip.ei_deduction
    return round(
        emp_cpp + employer_cpp(emp_cpp)
        + emp_ei + employer_ei(emp_ei)
        + payslip.fed_tax
        + payslip.prov_tax,
        2,
    )
