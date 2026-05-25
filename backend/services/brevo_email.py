"""Brevo transactional email helpers for customer-facing notifications."""

from __future__ import annotations

import logging
from html import escape
from typing import Any

import httpx

from observability.metrics import email_delivery_total
from shared.secrets import getenv, load_infisical_secrets

logger = logging.getLogger(__name__)

load_infisical_secrets()

_BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"
_REQUEST_TIMEOUT_SECONDS = 10.0


def is_brevo_configured() -> bool:
    return bool(getenv("BREVO_API_KEY") and getenv("BREVO_SENDER_EMAIL"))


def _sender() -> dict[str, str]:
    return {
        "email": str(getenv("BREVO_SENDER_EMAIL", "") or ""),
        "name": str(getenv("BREVO_SENDER_NAME", "ZeroQwait") or "ZeroQwait"),
    }


def _record(email_type: str, sent: bool) -> None:
    email_delivery_total.labels(
        email_type=email_type,
        status="sent" if sent else "failed",
    ).inc()


def _format_amount(amount: float | int | str) -> str:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return str(amount)
    return f"${value:,.2f}"


def _detail_rows(details: dict[str, Any]) -> str:
    labels = {
        "shop_name": "Shop",
        "service_name": "Service",
        "scheduled_date": "Date",
        "scheduled_time": "Time",
        "scheduled_start": "When",
        "staff_name": "With",
        "location": "Location",
        "reminder_window": "Reminder",
    }
    rows: list[str] = []
    for key, label in labels.items():
        value = details.get(key)
        if value:
            rows.append(
                "<tr>"
                f"<td style='padding:8px 0;color:#667085;width:34%;'>{escape(label)}</td>"
                f"<td style='padding:8px 0;color:#101828;font-weight:600;'>{escape(str(value))}</td>"
                "</tr>"
            )
    return "".join(rows)


def _button(label: str, url: str | None) -> str:
    if not url:
        return ""
    safe_url = escape(url, quote=True)
    safe_label = escape(label)
    return (
        "<div style='margin:24px 0 4px;'>"
        f"<a href='{safe_url}' style='display:inline-block;background:#155EEF;color:#ffffff;"
        "text-decoration:none;border-radius:8px;padding:12px 18px;font-weight:700;'>"
        f"{safe_label}</a></div>"
    )


def _layout(title: str, intro: str, body: str, cta_html: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{escape(title)}</title>
  </head>
  <body style="margin:0;background:#F5F7FA;font-family:Arial,Helvetica,sans-serif;color:#101828;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(intro)}</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#F5F7FA;padding:28px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #EAECF0;">
            <tr>
              <td style="padding:22px 28px;background:#101828;color:#ffffff;">
                <div style="font-size:18px;font-weight:700;letter-spacing:.2px;">ZeroQwait</div>
              </td>
            </tr>
            <tr>
              <td style="padding:28px;">
                <h1 style="margin:0 0 12px;font-size:24px;line-height:1.25;color:#101828;">{escape(title)}</h1>
                <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#475467;">{escape(intro)}</p>
                {body}
                {cta_html}
              </td>
            </tr>
            <tr>
              <td style="padding:18px 28px;background:#F9FAFB;color:#667085;font-size:12px;line-height:1.5;">
                This email was sent by ZeroQwait on behalf of the business you interacted with.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


async def send_transactional_email(
    to: str,
    subject: str,
    html_content: str,
    text_content: str,
    email_type: str,
    record_metrics: bool = True,
) -> bool:
    api_key = getenv("BREVO_API_KEY", "") or ""
    sender_email = getenv("BREVO_SENDER_EMAIL", "") or ""
    if not api_key or not sender_email:
        logger.warning("Brevo email is not configured; set BREVO_API_KEY and BREVO_SENDER_EMAIL")
        if record_metrics:
            _record(email_type, False)
        return False

    payload = {
        "sender": _sender(),
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html_content,
        "textContent": text_content,
    }
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(_BREVO_SEND_URL, headers=headers, json=payload)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("Brevo email failed status=%s body=%s", exc.response.status_code, exc.response.text[:300])
        if record_metrics:
            _record(email_type, False)
        return False
    except Exception as exc:
        logger.error("Brevo email unexpected error: %s", exc)
        if record_metrics:
            _record(email_type, False)
        return False

    logger.info("Brevo email sent to %s subject=%r", to, subject)
    if record_metrics:
        _record(email_type, True)
    return True


async def sendBookingConfirmation(to: str, clientName: str, bookingDetails: dict[str, Any]) -> bool:
    shop_name = bookingDetails.get("shop_name") or "your appointment"
    rows = _detail_rows(bookingDetails)
    status_url = bookingDetails.get("status_url") or bookingDetails.get("cancel_url")
    body = (
        f"<p style='margin:0 0 18px;font-size:15px;line-height:1.6;'>Hi {escape(clientName or 'there')},</p>"
        "<p style='margin:0 0 18px;font-size:15px;line-height:1.6;color:#475467;'>Your booking is confirmed. Here are the details:</p>"
        f"<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='border-top:1px solid #EAECF0;border-bottom:1px solid #EAECF0;margin:8px 0 18px;'>{rows}</table>"
    )
    html_content = _layout(
        "Booking confirmed",
        f"Your booking at {shop_name} is confirmed.",
        body,
        _button("View booking", str(status_url) if status_url else None),
    )
    text_content = f"Hi {clientName or 'there'}, your booking at {shop_name} is confirmed."
    return await send_transactional_email(
        to=to,
        subject=f"Booking confirmed - {shop_name}",
        html_content=html_content,
        text_content=text_content,
        email_type="booking_confirmed",
    )


async def sendBookingReminder(to: str, clientName: str, bookingDetails: dict[str, Any]) -> bool:
    shop_name = bookingDetails.get("shop_name") or "your appointment"
    rows = _detail_rows(bookingDetails)
    status_url = bookingDetails.get("status_url") or bookingDetails.get("cancel_url")
    reminder_window = bookingDetails.get("reminder_window") or "soon"
    body = (
        f"<p style='margin:0 0 18px;font-size:15px;line-height:1.6;'>Hi {escape(clientName or 'there')},</p>"
        f"<p style='margin:0 0 18px;font-size:15px;line-height:1.6;color:#475467;'>This is a reminder that your booking is {escape(str(reminder_window))}.</p>"
        f"<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='border-top:1px solid #EAECF0;border-bottom:1px solid #EAECF0;margin:8px 0 18px;'>{rows}</table>"
    )
    html_content = _layout(
        "Booking reminder",
        f"Reminder for your booking at {shop_name}.",
        body,
        _button("View booking", str(status_url) if status_url else None),
    )
    text_content = f"Hi {clientName or 'there'}, reminder: your booking at {shop_name} is {reminder_window}."
    return await send_transactional_email(
        to=to,
        subject=f"Booking reminder - {shop_name}",
        html_content=html_content,
        text_content=text_content,
        email_type="reminder_24h" if "24" in str(reminder_window) else "reminder_1h",
    )


async def sendPaymentReceipt(to: str, clientName: str, amount: float | int | str, invoiceUrl: str) -> bool:
    amount_display = _format_amount(amount)
    body = (
        f"<p style='margin:0 0 18px;font-size:15px;line-height:1.6;'>Hi {escape(clientName or 'there')},</p>"
        "<p style='margin:0 0 18px;font-size:15px;line-height:1.6;color:#475467;'>Thanks for your visit. Your payment was received successfully.</p>"
        "<div style='background:#F9FAFB;border:1px solid #EAECF0;border-radius:10px;padding:18px;margin:8px 0 18px;'>"
        "<div style='font-size:13px;color:#667085;margin-bottom:4px;'>Amount paid</div>"
        f"<div style='font-size:28px;font-weight:700;color:#101828;'>{escape(amount_display)}</div>"
        "</div>"
    )
    html_content = _layout(
        "Payment receipt",
        f"Your payment receipt for {amount_display}.",
        body,
        _button("View receipt", invoiceUrl or None),
    )
    text_content = f"Hi {clientName or 'there'}, your payment of {amount_display} was received."
    return await send_transactional_email(
        to=to,
        subject=f"Your ZeroQwait receipt - {amount_display}",
        html_content=html_content,
        text_content=text_content,
        email_type="receipt",
    )


send_booking_confirmation = sendBookingConfirmation
send_booking_reminder = sendBookingReminder
send_payment_receipt = sendPaymentReceipt