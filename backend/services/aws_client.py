"""aws_client.py — AWS SES (email) and SNS (SMS) notification senders.

Environment variables required (non-optional at send time):
    AWS_REGION              e.g. us-east-1
    AWS_ACCESS_KEY_ID       IAM user access key
    AWS_SECRET_ACCESS_KEY   IAM user secret
    AWS_SES_FROM_EMAIL      Verified sender address, e.g. notifications@zeroqwait.com

Optional:
    AWS_SNS_SMS_SENDER_ID   Alphanumeric sender name shown on SMS (max 11 chars, default "ZeroQwait")
                            Not supported in all countries (US does not support it).

IAM permissions required:
    ses:SendEmail           on arn:aws:ses:<region>:<account>:identity/*
    sns:Publish             on *  (for direct phone number publishing)
"""

import logging
import os
import re
from typing import Final

import boto3
from botocore.exceptions import ClientError
from observability.metrics import email_delivery_total, sms_delivery_total

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

_REGION = os.getenv("AWS_REGION", "us-east-1")
_FROM_EMAIL = os.getenv("AWS_SES_FROM_EMAIL", "")
_SMS_SENDER_ID = os.getenv("AWS_SNS_SMS_SENDER_ID", "ZeroQwait")[:11]
_EMAIL_TYPES: Final[set[str]] = {
    "direct",
    "queue_join",
    "youre_next",
    "appointment_confirmation",
    "password_reset",
    "morning_briefing",
    "commitment_reminder",
    "revenue_alert",
    "staff_absence",
    "agent_escalation",
    "sentiment_alert",
    "booking_confirmed",
    "reminder_24h",
    "reminder_1h",
    "receipt",
    "low_stock_alert",
}


def _email_type(value: str | None) -> str:
    candidate = re.sub(r"[^a-z0-9_]+", "_", (value or "direct").strip().lower()).strip("_")
    return candidate if candidate in _EMAIL_TYPES else "other"


def _record_email(email_type: str | None, sent: bool) -> None:
    email_delivery_total.labels(
        email_type=_email_type(email_type),
        status="sent" if sent else "failed",
    ).inc()


def _record_sms(sent: bool) -> None:
    sms_delivery_total.labels(status="sent" if sent else "failed").inc()


def is_ses_configured() -> bool:
    return bool(os.getenv("AWS_ACCESS_KEY_ID") and _FROM_EMAIL)


def is_sns_configured() -> bool:
    return bool(os.getenv("AWS_ACCESS_KEY_ID"))


# ── Clients (lazy, one per call to avoid stale credentials) ───────────────────

def _ses():
    return boto3.client(
        "ses",
        region_name=_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def _sns():
    return boto3.client(
        "sns",
        region_name=_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


# ── Formatting helpers ─────────────────────────────────────────────────────────

def _strip_markdown(text: str) -> str:
    """Remove Telegram markdown so email/SMS read cleanly as plain text."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)   # **bold**
    text = re.sub(r"\*(.+?)\*", r"\1", text)         # *bold*
    text = re.sub(r"__(.+?)__", r"\1", text)          # __underline__
    text = re.sub(r"_(.+?)_", r"\1", text)            # _italic_
    text = re.sub(r"`(.+?)`", r"\1", text)             # `code`
    return text.strip()


def _to_html(markdown_text: str) -> str:
    """Convert Telegram markdown text to a simple responsive HTML email body."""
    body = markdown_text
    body = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Markdown links [text](url) — must run before bold so nested bold inside links works
    body = re.sub(r"\[(.+?)\]\((https?://[^\s)]+)\)", r'<a href="\2">\1</a>', body)
    body = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", body)
    body = re.sub(r"\*(.+?)\*", r"<strong>\1</strong>", body)
    body = re.sub(r"_(.+?)_", r"<em>\1</em>", body)
    body = re.sub(r"`(.+?)`", r"<code>\1</code>", body)
    # Markdown headers
    body = re.sub(r"^#{1,2}\s+(.+)$", r"<h3 style='margin:16px 0 8px;font-size:17px'>\1</h3>", body, flags=re.MULTILINE)
    # Horizontal rules
    body = re.sub(r"^---+$", r"<hr style='border:none;border-top:1px solid #e0e0e0;margin:16px 0'>", body, flags=re.MULTILINE)
    body = body.replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    body   {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
              background: #f5f5f5; margin: 0; padding: 24px; }}
    .card  {{ background: #ffffff; border-radius: 12px; max-width: 600px;
              margin: 0 auto; overflow: hidden;
              box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    .hdr   {{ background: #1565c0; color: #fff; padding: 20px 28px; }}
    .hdr h2{{ margin: 0; font-size: 20px; letter-spacing: 0.5px; }}
    .body  {{ padding: 24px 28px; color: #212121; line-height: 1.6; font-size: 15px; }}
    .footer{{ padding: 16px 28px; background: #fafafa; border-top: 1px solid #e0e0e0;
              color: #9e9e9e; font-size: 12px; }}
    a      {{ color: #1565c0; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="hdr"><h2>ZeroQwait</h2></div>
    <div class="body">{body}</div>
    <div class="footer">
      This notification was sent by your ZeroQwait AI agent team.<br>
      Manage notification preferences in your
      <a href="https://zeroqwait.com/dashboard">shop dashboard</a>.
    </div>
  </div>
</body>
</html>"""


# ── Public API ────────────────────────────────────────────────────────────────

async def send_email(
    to_address: str,
    subject: str,
    markdown_text: str,
    email_type: str = "direct",
) -> bool:
    """Send an HTML + plain-text email via AWS SES.

    Args:
        to_address:    Recipient email (must be verified if SES is in sandbox mode).
        subject:       Email subject line.
        markdown_text: Telegram-flavoured markdown text (will be auto-converted).

    Returns:
        True on success, False on any error (errors are logged, not raised).
    """
    if not is_ses_configured():
        logger.warning(
            "aws_client: SES not configured — set AWS_ACCESS_KEY_ID and AWS_SES_FROM_EMAIL"
        )
        _record_email(email_type, False)
        return False

    plain = _strip_markdown(markdown_text)
    html = _to_html(markdown_text)

    try:
        _ses().send_email(
            Source=_FROM_EMAIL,
            Destination={"ToAddresses": [to_address]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": plain, "Charset": "UTF-8"},
                    "Html":  {"Data": html,  "Charset": "UTF-8"},
                },
            },
        )
        logger.info("aws_client: email sent to %s (subject=%r)", to_address, subject)
        _record_email(email_type, True)
        return True

    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        msg  = exc.response["Error"]["Message"]
        logger.error("aws_client: SES error [%s]: %s", code, msg)
        _record_email(email_type, False)
        return False

    except Exception as exc:
        logger.error("aws_client: SES unexpected error: %s", exc)
        _record_email(email_type, False)
        return False


async def send_sms(phone_number: str, markdown_text: str) -> bool:
    """Send a transactional SMS via AWS SNS direct publish.

    Args:
        phone_number:  E.164 format, e.g. +14155552671 or +16137654321.
        markdown_text: Telegram-flavoured markdown (markdown stripped before sending).

    Returns:
        True on success, False on any error (errors are logged, not raised).

    Notes:
        - SNS SMS does not support sender ID in all regions/countries.
          US numbers never show a sender ID; they show a random short code.
        - Single SMS segment = 160 GSM chars. Messages over 400 chars are truncated.
        - For production use, move the AWS account out of the SNS SMS sandbox.
    """
    if not is_sns_configured():
        logger.warning(
            "aws_client: SNS not configured — set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
        )
        _record_sms(False)
        return False

    plain = _strip_markdown(markdown_text)
    if len(plain) > 400:
        plain = plain[:397] + "..."

    message_attributes: dict = {
        "AWS.SNS.SMS.SMSType": {
            "DataType": "String",
            "StringValue": "Transactional",
        },
    }
    # Sender ID not supported in US/Canada — only set it for non-NA numbers
    if not phone_number.startswith(("+1",)):
        message_attributes["AWS.SNS.SMS.SenderID"] = {
            "DataType": "String",
            "StringValue": _SMS_SENDER_ID,
        }

    try:
        _sns().publish(
            PhoneNumber=phone_number,
            Message=plain,
            MessageAttributes=message_attributes,
        )
        logger.info("aws_client: SMS sent to %s", phone_number)
        _record_sms(True)
        return True

    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        msg  = exc.response["Error"]["Message"]
        logger.error("aws_client: SNS error [%s]: %s", code, msg)
        _record_sms(False)
        return False

    except Exception as exc:
        logger.error("aws_client: SNS unexpected error: %s", exc)
        _record_sms(False)
        return False
