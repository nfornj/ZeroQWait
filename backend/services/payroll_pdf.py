"""
payroll_pdf.py — Canadian-standard payslip PDF generator.

Uses reportlab to produce a professional payslip that matches CRA expectations:
- Header: shop name, province, "Statement of Earnings"
- Employee block: name, SIN (masked), pay period, pay date
- Earnings table: regular hrs×rate, overtime, tips → gross
- Deductions table: CPP (employee), EI (employee), Federal Tax, Provincial Tax, other
- Employer contributions section: employer CPP, employer EI, total remittance
- Net Pay (bold, highlighted)
- YTD totals
- Footer: "Computer-generated payslip — {Shop Name}"

Usage:
    from services.payroll_pdf import generate_payslip_pdf
    pdf_bytes = generate_payslip_pdf(payslip, employee_name, shop_name, sin_last4, province)
"""

from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any, Dict, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ─── Colour palette ────────────────────────────────────────────────────────────
_BRAND_DARK   = colors.HexColor("#1A237E")  # deep blue header
_BRAND_MED    = colors.HexColor("#3949AB")  # section headers
_ACCENT_GREEN = colors.HexColor("#1B5E20")  # net pay
_ROW_LIGHT    = colors.HexColor("#E8EAF6")  # alternating table rows
_ROW_DARK     = colors.HexColor("#C5CAE9")  # deductions header / alt rows
_TEXT_BODY    = colors.HexColor("#212121")


def _currency(value: Any) -> str:
    """Format a numeric value as a Canadian dollar string."""
    try:
        return f"${float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _fmt_date(value: Any) -> str:
    """Return a human-readable date string like May 1, 2026."""
    if isinstance(value, (date, datetime)):
        return value.strftime("%B %-d, %Y")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime("%B %-d, %Y")
        except ValueError:
            return str(value)
    return str(value or "")


def generate_payslip_pdf(
    payslip: Dict[str, Any],
    employee_name: str,
    shop_name: str,
    sin_last4: Optional[str],
    province: str,
    employee_address: Optional[str] = None,
    shop_address: Optional[str] = None,
) -> bytes:
    """
    Build a Canadian-standard payslip PDF and return raw bytes.

    Args:
        payslip:          Row dict from the ``payslips`` table.
        employee_name:    Full name of the employee.
        shop_name:        Name of the shop (used in header + filename).
        sin_last4:        Last 4 digits of SIN for partial masking, or None.
        province:         2-letter province code (e.g. "ON").
        employee_address: Optional street address line for the employee block.
        shop_address:     Optional shop address line for the header.
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=f"Payslip – {employee_name}",
        author=shop_name,
    )

    styles = getSampleStyleSheet()
    story = []

    # ─── Styles ────────────────────────────────────────────────────────────────
    h1 = ParagraphStyle(
        "H1",
        parent=styles["Normal"],
        fontSize=18,
        leading=22,
        fontName="Helvetica-Bold",
        textColor=_BRAND_DARK,
        alignment=TA_LEFT,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        fontName="Helvetica-Bold",
        textColor=_BRAND_MED,
        spaceAfter=2,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        fontName="Helvetica",
        textColor=_TEXT_BODY,
    )
    small = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        fontName="Helvetica",
        textColor=colors.grey,
    )
    net_style = ParagraphStyle(
        "NetPay",
        parent=styles["Normal"],
        fontSize=22,
        leading=26,
        fontName="Helvetica-Bold",
        textColor=_ACCENT_GREEN,
        alignment=TA_RIGHT,
    )

    page_width = LETTER[0] - 1.30 * inch  # usable width

    # ─── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph(shop_name, h1))
    if shop_address:
        story.append(Paragraph(shop_address, small))
    story.append(
        Paragraph(
            f"Province of Employment: <b>{province}</b>  |  "
            "Statement of Earnings",
            body,
        )
    )
    story.append(HRFlowable(width=page_width, thickness=2, color=_BRAND_DARK, spaceAfter=8))

    # ─── Employee Info Block ───────────────────────────────────────────────────
    period_start = _fmt_date(payslip.get("period_start"))
    period_end   = _fmt_date(payslip.get("period_end"))
    pay_date     = _fmt_date(payslip.get("pay_date"))
    sin_display  = f"***-***-{sin_last4}" if sin_last4 else "***-***-****"

    info_data = [
        ["Employee", employee_name, "Pay Period", f"{period_start} – {period_end}"],
        ["SIN (masked)", sin_display, "Pay Date", pay_date],
    ]
    if employee_address:
        info_data.append(["Address", employee_address, "Status", "Regular"])

    info_table = Table(
        info_data,
        colWidths=[1.2 * inch, (page_width / 2) - 1.2 * inch,
                   1.2 * inch, (page_width / 2) - 1.2 * inch],
    )
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TEXTCOLOR", (0, 0), (-1, -1), _TEXT_BODY),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 10))

    # ─── Helper: section header ────────────────────────────────────────────────
    def section_header(title: str) -> Paragraph:
        return Paragraph(title, h2)

    # ─── Earnings ─────────────────────────────────────────────────────────────
    story.append(section_header("EARNINGS"))

    regular_hours = float(payslip.get("regular_hours") or 0)
    overtime_hours = float(payslip.get("overtime_hours") or 0)
    gross_pay = float(payslip.get("gross_pay") or 0)
    tips = float(payslip.get("tips_included") or 0)

    # Derive hourly rate if possible
    reg_pay = gross_pay - tips
    if overtime_hours:
        # gross = reg_hours × rate + OT_hours × (rate × 1.5) + tips
        # Solve: rate = reg_pay / (reg_hours + OT_hours × 1.5)
        denom = regular_hours + overtime_hours * 1.5
        hourly_rate = reg_pay / denom if denom > 0 else 0
        reg_only = regular_hours * hourly_rate
        ot_only = overtime_hours * hourly_rate * 1.5
    else:
        hourly_rate = reg_pay / regular_hours if regular_hours > 0 else 0
        reg_only = reg_pay
        ot_only = 0.0

    earn_rows = [["Description", "Hours", "Rate", "Amount"]]
    earn_rows.append([
        "Regular Pay",
        f"{regular_hours:.2f}",
        _currency(hourly_rate),
        _currency(reg_only),
    ])
    if overtime_hours > 0:
        earn_rows.append([
            "Overtime Pay (1.5×)",
            f"{overtime_hours:.2f}",
            _currency(hourly_rate * 1.5),
            _currency(ot_only),
        ])
    if tips > 0:
        earn_rows.append(["Gratuities / Tips", "—", "—", _currency(tips)])
    earn_rows.append(["", "", "Gross Pay", _currency(gross_pay)])

    earn_col_widths = [
        page_width * 0.42,
        page_width * 0.14,
        page_width * 0.20,
        page_width * 0.24,
    ]
    earn_table = Table(earn_rows, colWidths=earn_col_widths)
    earn_style = [
        ("BACKGROUND", (0, 0), (-1, 0), _BRAND_MED),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]
    # Alternate row shading (skip header row 0 and last totals row)
    for i in range(1, len(earn_rows) - 1):
        if i % 2 == 0:
            earn_style.append(("BACKGROUND", (0, i), (-1, i), _ROW_LIGHT))
    # Bold last row (Gross Pay total)
    earn_style += [
        ("FONTNAME", (2, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), _ROW_DARK),
    ]
    earn_table.setStyle(TableStyle(earn_style))
    story.append(earn_table)
    story.append(Spacer(1, 10))

    # ─── Deductions ───────────────────────────────────────────────────────────
    story.append(section_header("DEDUCTIONS"))

    cpp_ded = float(payslip.get("cpp_deduction") or 0)
    ei_ded  = float(payslip.get("ei_deduction") or 0)
    fed_tax = float(payslip.get("fed_tax") or 0)
    prov_tax = float(payslip.get("prov_tax") or 0)
    other_ded = float(payslip.get("other_deductions") or 0)
    total_ded = float(payslip.get("total_deductions") or 0)

    ded_rows = [["Deduction", "Current Period"]]
    ded_rows.append(["CPP Contribution (Employee)", _currency(cpp_ded)])
    ded_rows.append(["EI Premium (Employee)", _currency(ei_ded)])
    ded_rows.append(["Federal Income Tax", _currency(fed_tax)])
    ded_rows.append([f"Provincial Income Tax ({province})", _currency(prov_tax)])
    if other_ded > 0:
        ded_rows.append(["Other Deductions", _currency(other_ded)])
    ded_rows.append(["Total Deductions", _currency(total_ded)])

    ded_col_widths = [page_width * 0.60, page_width * 0.40]
    ded_table = Table(ded_rows, colWidths=ded_col_widths)
    ded_style = [
        ("BACKGROUND", (0, 0), (-1, 0), _BRAND_MED),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), _ROW_DARK),
    ]
    for i in range(1, len(ded_rows) - 1):
        if i % 2 == 0:
            ded_style.append(("BACKGROUND", (0, i), (-1, i), _ROW_LIGHT))
    ded_table.setStyle(TableStyle(ded_style))
    story.append(ded_table)
    story.append(Spacer(1, 10))

    # ─── Employer Contributions (CRA remittance info) ─────────────────────────
    # Estimate employer CPP (same rate as employee) and employer EI (1.4× employee EI)
    employer_cpp_est = cpp_ded          # employer CPP ≈ employee CPP
    employer_ei_est  = ei_ded * 1.4    # employer EI = 1.4 × employee EI
    total_remittance = cpp_ded + employer_cpp_est + ei_ded + employer_ei_est + fed_tax + prov_tax

    story.append(section_header("EMPLOYER CONTRIBUTIONS (CRA REMITTANCE SUMMARY)"))
    emp_rows = [
        ["Item", "Amount"],
        ["Employer CPP Contribution", _currency(employer_cpp_est)],
        ["Employer EI Premium (1.4×)", _currency(employer_ei_est)],
        ["Total CRA Remittance (payroll source deductions)", _currency(total_remittance)],
    ]
    emp_col_widths = [page_width * 0.70, page_width * 0.30]
    emp_table = Table(emp_rows, colWidths=emp_col_widths)
    emp_style = [
        ("BACKGROUND", (0, 0), (-1, 0), _BRAND_MED),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), _ROW_DARK),
    ]
    emp_table.setStyle(TableStyle(emp_style))
    story.append(emp_table)
    story.append(Spacer(1, 12))

    # ─── Net Pay (large, green) ────────────────────────────────────────────────
    net_pay = float(payslip.get("net_pay") or 0)
    net_table = Table(
        [["NET PAY", _currency(net_pay)]],
        colWidths=[page_width * 0.70, page_width * 0.30],
    )
    net_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E8F5E9")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (0, 0), 14),
        ("FONTSIZE", (1, 0), (1, 0), 18),
        ("TEXTCOLOR", (0, 0), (-1, -1), _ACCENT_GREEN),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (0, 0), 8),
        ("RIGHTPADDING", (1, 0), (1, 0), 8),
        ("LINEABOVE", (0, 0), (-1, 0), 2, _ACCENT_GREEN),
        ("LINEBELOW", (0, -1), (-1, -1), 2, _ACCENT_GREEN),
    ]))
    story.append(net_table)
    story.append(Spacer(1, 14))

    # ─── YTD Totals ───────────────────────────────────────────────────────────
    story.append(section_header("YEAR-TO-DATE TOTALS"))

    # The payslip row may not have YTD fields directly; we show what's available
    ytd_gross   = payslip.get("ytd_gross")
    ytd_cpp     = payslip.get("ytd_cpp")
    ytd_ei      = payslip.get("ytd_ei")
    ytd_fed     = payslip.get("ytd_fed_tax")
    ytd_prov    = payslip.get("ytd_prov_tax")
    ytd_net     = payslip.get("ytd_net")

    # Fallback: if ytd fields are None, only current period is available
    ytd_rows = [["Description", "Year to Date"]]
    ytd_rows.append(["Gross Earnings", _currency(ytd_gross) if ytd_gross is not None else f"min. {_currency(gross_pay)}"])
    ytd_rows.append(["CPP Contributions", _currency(ytd_cpp) if ytd_cpp is not None else f"min. {_currency(cpp_ded)}"])
    ytd_rows.append(["EI Premiums", _currency(ytd_ei) if ytd_ei is not None else f"min. {_currency(ei_ded)}"])
    ytd_rows.append(["Federal Tax", _currency(ytd_fed) if ytd_fed is not None else f"min. {_currency(fed_tax)}"])
    ytd_rows.append([f"Provincial Tax ({province})", _currency(ytd_prov) if ytd_prov is not None else f"min. {_currency(prov_tax)}"])
    if ytd_net is not None:
        ytd_rows.append(["Net Pay", _currency(ytd_net)])

    ytd_col_widths = [page_width * 0.60, page_width * 0.40]
    ytd_table = Table(ytd_rows, colWidths=ytd_col_widths)
    ytd_style = [
        ("BACKGROUND", (0, 0), (-1, 0), _BRAND_MED),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]
    for i in range(1, len(ytd_rows)):
        if i % 2 == 0:
            ytd_style.append(("BACKGROUND", (0, i), (-1, i), _ROW_LIGHT))
    ytd_table.setStyle(TableStyle(ytd_style))
    story.append(ytd_table)
    story.append(Spacer(1, 18))

    # ─── Footer ───────────────────────────────────────────────────────────────
    story.append(HRFlowable(width=page_width, thickness=0.5, color=colors.lightgrey, spaceAfter=4))
    story.append(
        Paragraph(
            f"Computer-generated payslip — {shop_name} — "
            "This document is confidential. Please retain for your records.",
            small,
        )
    )
    story.append(
        Paragraph(
            "Source deductions remitted to the Canada Revenue Agency (CRA) as required under the "
            "Income Tax Act and the Canada Pension Plan Act.",
            small,
        )
    )

    doc.build(story)
    return buffer.getvalue()


def payslip_filename(shop_name: str, employee_name: str, period_start: Any) -> str:
    """
    Return a safe filename for the payslip PDF.
    e.g.  FreshCuts_John_Smith_payslip_2026-05-01.pdf
    """
    import re
    def _slug(text: str) -> str:
        return re.sub(r"[^a-zA-Z0-9]+", "_", str(text or "")).strip("_")

    ps = period_start
    if isinstance(ps, (date, datetime)):
        ps = ps.strftime("%Y-%m-%d")
    elif isinstance(ps, str):
        try:
            ps = datetime.fromisoformat(ps).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return f"{_slug(shop_name)}_{_slug(employee_name)}_payslip_{ps}.pdf"


def generate_payroll_history_pdf(
    shop_name: str,
    period_label: str,
    employee_summaries: list,
    all_payslips: list,
    generated_on: Optional[str] = None,
) -> bytes:
    """
    Build a Payroll History Report PDF and return raw bytes.

    Args:
        shop_name:          Name of the shop.
        period_label:       Human-readable period label, e.g. "May 2025 – May 2026".
        employee_summaries: List of dicts: {name, province, periods, total_gross, total_deductions, total_net}.
        all_payslips:       List of dicts: {employee_name, period_start, period_end, gross_pay,
                            cpp_deduction, ei_deduction, fed_tax, prov_tax, net_pay, status}.
        generated_on:       Optional ISO date string for "Generated on" footer.
    """
    import re

    def _slug(text: str) -> str:
        return re.sub(r"[^a-zA-Z0-9]+", "_", str(text or "")).strip("_")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=f"Payroll History – {shop_name}",
        author=shop_name,
    )

    styles = getSampleStyleSheet()
    page_width = LETTER[0] - 1.30 * inch

    title_style = ParagraphStyle(
        "Title",
        parent=styles["Normal"],
        fontSize=20,
        leading=24,
        fontName="Helvetica-Bold",
        textColor=_BRAND_DARK,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        fontName="Helvetica",
        textColor=_BRAND_MED,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        fontName="Helvetica-Bold",
        textColor=_BRAND_MED,
        spaceBefore=12,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        fontName="Helvetica",
        textColor=_TEXT_BODY,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        fontName="Helvetica",
        textColor=colors.grey,
    )
    emp_name_style = ParagraphStyle(
        "EmpName",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        fontName="Helvetica-Bold",
        textColor=_BRAND_DARK,
        spaceBefore=10,
        spaceAfter=2,
    )

    story = []

    # ── Cover / Header ─────────────────────────────────────────────────────────
    story.append(Paragraph(shop_name, title_style))
    story.append(Paragraph(f"Payroll History Report — {period_label}", subtitle_style))
    gen_date = generated_on or date.today().strftime("%B %-d, %Y")
    story.append(Paragraph(f"Generated: {gen_date}", small_style))
    story.append(HRFlowable(width=page_width, thickness=2, color=_BRAND_DARK, spaceAfter=10))

    # ── Employee Summary Table ─────────────────────────────────────────────────
    story.append(Paragraph("ANNUAL PAYROLL SUMMARY BY EMPLOYEE", section_style))

    sum_rows = [["Employee", "Province", "Pay Periods", "Total Gross", "Total Deductions", "Total Net"]]
    grand_gross = grand_ded = grand_net = 0.0
    for emp in employee_summaries:
        gross = float(emp.get("total_gross") or 0)
        ded   = float(emp.get("total_deductions") or 0)
        net   = float(emp.get("total_net") or 0)
        grand_gross += gross
        grand_ded   += ded
        grand_net   += net
        sum_rows.append([
            emp.get("name", "—"),
            emp.get("province", "ON"),
            str(emp.get("periods", 0)),
            _currency(gross),
            _currency(ded),
            _currency(net),
        ])
    # Totals row
    sum_rows.append(["TOTAL", "", "", _currency(grand_gross), _currency(grand_ded), _currency(grand_net)])

    col_w = [page_width * w for w in [0.24, 0.09, 0.10, 0.17, 0.20, 0.20]]
    sum_table = Table(sum_rows, colWidths=col_w)
    sum_style_list = [
        ("BACKGROUND", (0, 0), (-1, 0), _BRAND_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        # Totals row bold + highlighted
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), _ROW_DARK),
    ]
    for i in range(1, len(sum_rows) - 1):
        if i % 2 == 0:
            sum_style_list.append(("BACKGROUND", (0, i), (-1, i), _ROW_LIGHT))
    sum_table.setStyle(TableStyle(sum_style_list))
    story.append(sum_table)
    story.append(Spacer(1, 16))

    # ── Per-Employee Pay Period Detail ─────────────────────────────────────────
    # Group payslips by employee name
    emp_slips: Dict[str, list] = {}
    for slip in all_payslips:
        ename = slip.get("employee_name", "Unknown")
        emp_slips.setdefault(ename, []).append(slip)

    story.append(Paragraph("PAY PERIOD DETAIL BY EMPLOYEE", section_style))
    story.append(HRFlowable(width=page_width, thickness=0.5, color=_BRAND_MED, spaceAfter=6))

    for ename, slips in emp_slips.items():
        story.append(Paragraph(ename, emp_name_style))
        detail_rows = [["Pay Period", "Gross Pay", "CPP", "EI", "Fed Tax", "Prov Tax", "Net Pay", "Status"]]
        for slip in sorted(slips, key=lambda s: str(s.get("period_start", ""))):
            ps = str(slip.get("period_start", ""))[:10]
            pe = str(slip.get("period_end", ""))[:10]
            period_str = f"{ps} – {pe}"
            status = str(slip.get("status", "draft")).capitalize()
            detail_rows.append([
                period_str,
                _currency(slip.get("gross_pay")),
                _currency(slip.get("cpp_deduction")),
                _currency(slip.get("ei_deduction")),
                _currency(slip.get("fed_tax")),
                _currency(slip.get("prov_tax")),
                _currency(slip.get("net_pay")),
                status,
            ])
        # Employee subtotal
        emp_gross = sum(float(s.get("gross_pay") or 0) for s in slips)
        emp_net   = sum(float(s.get("net_pay") or 0) for s in slips)
        emp_cpp   = sum(float(s.get("cpp_deduction") or 0) for s in slips)
        emp_ei    = sum(float(s.get("ei_deduction") or 0) for s in slips)
        emp_fed   = sum(float(s.get("fed_tax") or 0) for s in slips)
        emp_prov  = sum(float(s.get("prov_tax") or 0) for s in slips)
        detail_rows.append([
            "SUBTOTAL",
            _currency(emp_gross),
            _currency(emp_cpp),
            _currency(emp_ei),
            _currency(emp_fed),
            _currency(emp_prov),
            _currency(emp_net),
            "",
        ])

        det_col_w = [page_width * w for w in [0.25, 0.12, 0.08, 0.08, 0.11, 0.11, 0.13, 0.12]]
        det_table = Table(detail_rows, colWidths=det_col_w)
        det_style_list = [
            ("BACKGROUND", (0, 0), (-1, 0), _BRAND_MED),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("LEADING", (0, 0), (-1, -1), 10),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), _ROW_DARK),
        ]
        for i in range(1, len(detail_rows) - 1):
            if i % 2 == 0:
                det_style_list.append(("BACKGROUND", (0, i), (-1, i), _ROW_LIGHT))
        det_table.setStyle(TableStyle(det_style_list))
        story.append(det_table)
        story.append(Spacer(1, 8))

    # ── Footer ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width=page_width, thickness=0.5, color=colors.lightgrey, spaceAfter=4))
    story.append(
        Paragraph(
            f"Computer-generated Payroll History Report — {shop_name} — Confidential. "
            "All figures in CAD. Source deductions remitted to CRA.",
            small_style,
        )
    )

    doc.build(story)
    return buffer.getvalue()
