"""notification_templates.py — Telegram-formatted message templates for all 7 event types.

Each function returns a tuple: (text: str, buttons: list[list[dict]] | None)
  - text:    Markdown-formatted message body (Telegram flavour)
  - buttons: None for informational messages; list[list[dict]] for HITL escalations

Event types:
  1. morning_briefing        — daily summary (Temporal heartbeat, morning)
  2. commitment_reminder     — a promise the agent tracked is coming due
  3. appointment_confirmation — new booking was made
  4. revenue_alert           — Finance agent: unusual drop or spike
  5. staff_absence           — HR agent: no-show or uncovered shift
  6. agent_escalation        — HITL: agent cannot decide autonomously (with inline buttons)
  7. sentiment_alert         — CRM: frustrated repeat customer

Inline button format (for Telegram InlineKeyboardMarkup):
    [{"text": "<label>", "callback_data": "<payload>"}]

Payload convention for agent_escalation:
    approve:<action_id>   → approve the pending action
    decline:<action_id>   → decline/reject the pending action
    defer:<action_id>     → owner will handle it from the dashboard
"""

from typing import Any


# ── 1. Morning briefing ────────────────────────────────────────────────────────

def morning_briefing(data: dict[str, Any]) -> tuple[str, None]:
    """Daily business summary sent by the Temporal heartbeat each morning."""
    shop_name: str = data.get("shop_name", "your shop")
    appointments: int = data.get("appointments_today", 0)
    revenue_yesterday: float = data.get("revenue_yesterday", 0.0)
    overdue_commitments: int = data.get("overdue_commitments", 0)
    date_label: str = data.get("date_label", "today")

    overdue_line = ""
    if overdue_commitments:
        noun = "commitment" if overdue_commitments == 1 else "commitments"
        overdue_line = f"\n⚠️ *{overdue_commitments} overdue {noun}* — check the Agent Inbox"

    appt_noun = "appointment" if appointments == 1 else "appointments"
    text = (
        f"☀️ *Good morning — {date_label}*\n\n"
        f"📅 *{appointments}* {appt_noun} scheduled\n"
        f"💰 *${revenue_yesterday:.2f}* revenue yesterday"
        f"{overdue_line}\n\n"
        f"_Your AI team is on it — have a great day at {shop_name}!_"
    )
    return text, None


# ── 2. Commitment reminder ────────────────────────────────────────────────────

def commitment_reminder(data: dict[str, Any]) -> tuple[str, None]:
    """A promise the agent tracked is coming due soon."""
    customer: str = data.get("customer_name", "a customer")
    commitment: str = data.get("commitment_text", "a commitment")
    due: str = data.get("due_description", "soon")

    text = (
        f"📌 *Commitment Reminder*\n\n"
        f"You made a commitment to *{customer}*:\n"
        f"_{commitment}_\n\n"
        f"⏰ Due: *{due}*"
    )
    return text, None


# ── 3. Appointment confirmation ────────────────────────────────────────────────

def appointment_confirmation(data: dict[str, Any]) -> tuple[str, None]:
    """A new appointment was booked."""
    customer: str = data.get("customer_name", "Someone")
    service: str = data.get("service_name", "a service")
    scheduled_time: str = data.get("scheduled_time", "a scheduled time")
    shop_name: str = data.get("shop_name", "your shop")

    text = (
        f"📆 *New Appointment Booked*\n\n"
        f"*{customer}* has booked *{service}* at {shop_name}\n"
        f"🕐 *{scheduled_time}*"
    )
    return text, None


# ── 4. Revenue alert ───────────────────────────────────────────────────────────

def revenue_alert(data: dict[str, Any]) -> tuple[str, None]:
    """Finance agent detected an unusual revenue drop or spike."""
    alert_type: str = data.get("alert_type", "unusual")  # "spike" | "drop" | "unusual"
    amount: float = data.get("amount", 0.0)
    period: str = data.get("period", "today")
    comparison_text: str = data.get("comparison_text", "")

    icon = "📈" if alert_type == "spike" else "📉" if alert_type == "drop" else "💡"
    comparison_line = f"\n{comparison_text}" if comparison_text else ""

    text = (
        f"{icon} *Revenue Alert*\n\n"
        f"*${amount:.2f}* in revenue for {period}"
        f"{comparison_line}\n\n"
        f"_Your Finance AI is monitoring this closely._"
    )
    return text, None


# ── 5. Staff absence ───────────────────────────────────────────────────────────

def staff_absence(data: dict[str, Any]) -> tuple[str, None]:
    """HR agent detected a no-show or uncovered shift."""
    employee: str = data.get("employee_name", "An employee")
    shift_time: str = data.get("shift_time", "their shift")
    reason: str = data.get("reason", "")

    reason_line = f"\n_Reason: {reason}_" if reason else ""

    text = (
        f"🚨 *Staff Absence Alert*\n\n"
        f"*{employee}* has not clocked in for {shift_time}."
        f"{reason_line}\n\n"
        f"Consider reassigning or covering the shift."
    )
    return text, None


# ── 6. Agent escalation (HITL) — includes inline keyboard buttons ──────────────

def agent_escalation(data: dict[str, Any]) -> tuple[str, list[list[dict[str, str]]]]:
    """The agent cannot decide autonomously — owner must choose.

    Returns a message with three inline buttons:
      [✅ Approve]  [❌ Decline]
      [📲 I'll Handle It]

    The callback_data payload is "action:action_id" — processed in telegram_webhook.py.
    """
    question: str = data.get("question", "The agent needs your input.")
    context: str = data.get("context", "")
    action_id: str = data.get("action_id", "")
    action_type: str = data.get("action_type", "decision")
    shop_name: str = data.get("shop_name", "")

    context_line = f"\n\n_{context}_" if context else ""
    shop_line = f" — *{shop_name}*" if shop_name else ""

    text = (
        f"🤖 *Approval Needed{shop_line}*\n\n"
        f"{question}"
        f"{context_line}"
    )

    buttons: list[list[dict[str, str]]] = [
        [
            {"text": "✅ Approve", "callback_data": f"approve:{action_id}"},
            {"text": "❌ Decline", "callback_data": f"decline:{action_id}"},
        ],
        [
            {"text": "📲 I'll Handle It", "callback_data": f"defer:{action_id}"},
        ],
    ]
    return text, buttons


# ── 7. Customer sentiment alert ────────────────────────────────────────────────

def sentiment_alert(data: dict[str, Any]) -> tuple[str, None]:
    """CRM agent flagged a frustrated repeat customer."""
    customer: str = data.get("customer_name", "A customer")
    visit_count: int = data.get("visit_count", 0)
    sentiment_summary: str = data.get("sentiment_summary", "expressed dissatisfaction")

    visits_line = f" ({visit_count} visits)" if visit_count else ""

    text = (
        f"😟 *Customer Sentiment Alert*\n\n"
        f"*{customer}*{visits_line} {sentiment_summary}.\n\n"
        f"Consider reaching out personally — a quick message can turn this around."
    )
    return text, None


# ── 8. Booking confirmed (customer-facing) ─────────────────────────────────────

def booking_confirmed(data: dict[str, Any]) -> tuple[str, None]:
    """Sent to customer when their online booking is confirmed."""
    customer: str = data.get("customer_name", "there")
    service: str = data.get("service_name", "your appointment")
    shop_name: str = data.get("shop_name", "the shop")
    scheduled_time: str = data.get("scheduled_time", "your scheduled time")
    cancel_url: str = data.get("cancel_url", "")

    cancel_line = f"\n\n🔗 Need to cancel? {cancel_url}" if cancel_url else ""

    text = (
        f"✅ *Booking Confirmed!*\n\n"
        f"Hi *{customer}*, your booking at *{shop_name}* is confirmed.\n\n"
        f"📋 *Service:* {service}\n"
        f"🕐 *Time:* {scheduled_time}"
        f"{cancel_line}\n\n"
        f"_We look forward to seeing you!_"
    )
    return text, None


# ── 9. Reminder — 24 hours before appointment ─────────────────────────────────

def reminder_24h(data: dict[str, Any]) -> tuple[str, None]:
    """Sent to customer 24 hours before their appointment."""
    customer: str = data.get("customer_name", "there")
    service: str = data.get("service_name", "your appointment")
    shop_name: str = data.get("shop_name", "the shop")
    scheduled_time: str = data.get("scheduled_time", "tomorrow")
    cancel_url: str = data.get("cancel_url", "")

    cancel_line = f"\n🔗 Need to cancel? {cancel_url}" if cancel_url else ""

    text = (
        f"⏰ *Appointment Reminder — Tomorrow*\n\n"
        f"Hi *{customer}*, just a reminder that you have *{service}* at *{shop_name}* tomorrow.\n\n"
        f"🕐 *{scheduled_time}*"
        f"{cancel_line}"
    )
    return text, None


# ── 10. Reminder — 1 hour before appointment ─────────────────────────────────

def reminder_1h(data: dict[str, Any]) -> tuple[str, None]:
    """Sent to customer 1 hour before their appointment."""
    customer: str = data.get("customer_name", "there")
    service: str = data.get("service_name", "your appointment")
    shop_name: str = data.get("shop_name", "the shop")
    scheduled_time: str = data.get("scheduled_time", "soon")

    text = (
        f"🔔 *Your appointment is in 1 hour!*\n\n"
        f"Hi *{customer}*, see you soon at *{shop_name}* for *{service}* at *{scheduled_time}*. 🙌"
    )
    return text, None


# ── 11. You're next in queue ───────────────────────────────────────────────────

def youre_next(data: dict[str, Any]) -> tuple[str, None]:
    """Sent to customer when they are about to be called from the queue."""
    customer: str = data.get("customer_name", "there")
    shop_name: str = data.get("shop_name", "the shop")
    service: str = data.get("service_name", "your service")

    text = (
        f"🎉 *You're next!*\n\n"
        f"Hi *{customer}*, you're next up at *{shop_name}* for *{service}*. Please make your way to the front!"
    )
    return text, None


# ── 12. Receipt / Checkout summary ────────────────────────────────────────────

def receipt(data: dict[str, Any]) -> tuple[str, None]:
    """Sent to customer after a POS checkout is completed."""
    customer: str = data.get("customer_name", "there")
    shop_name: str = data.get("shop_name", "the shop")
    subtotal: float = data.get("subtotal", 0.0)
    hst: float = data.get("hst", 0.0)
    tip: float = data.get("tip", 0.0)
    total: float = data.get("total", 0.0)
    payment_method: str = data.get("payment_method", "cash")
    items: list = data.get("items", [])

    item_lines = ""
    if items:
        item_lines = "\n" + "\n".join(f"  • {i}" for i in items[:10]) + "\n"

    text = (
        f"🧾 *Receipt from {shop_name}*\n\n"
        f"Hi *{customer}*, thank you for your visit!\n"
        f"{item_lines}\n"
        f"💰 Subtotal: ${subtotal:.2f}\n"
        + (f"🏛️ HST: ${hst:.2f}\n" if hst > 0 else "")
        + (f"💝 Tip: ${tip:.2f}\n" if tip > 0 else "")
        + f"✅ *Total: ${total:.2f}* ({payment_method})\n\n"
        f"_See you next time!_"
    )
    return text, None


# ── 13. Low stock alert (owner-facing) ────────────────────────────────────────

def low_stock_alert(data: dict[str, Any]) -> tuple[str, None]:
    """Sent to shop owner when inventory items fall below reorder threshold."""
    shop_name: str = data.get("shop_name", "your shop")
    alerts: list = data.get("alerts", [])

    if not alerts:
        return f"📦 *Inventory Check* — All items are well stocked at {shop_name}.", None

    lines = []
    for a in alerts[:10]:
        lines.append(f"• *{a.get('name', 'Item')}*: {a.get('current_stock', 0)} {a.get('unit', 'units')} remaining")

    text = (
        f"📦 *Low Stock Alert — {shop_name}*\n\n"
        f"The following {len(alerts)} item(s) need restocking:\n\n"
        + "\n".join(lines)
        + "\n\n_Order soon to avoid running out during busy periods._"
    )
    return text, None
