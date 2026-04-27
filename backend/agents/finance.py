"""Finance specialist graph with explicit planner and executor nodes."""

from datetime import datetime, timedelta
import logging
import re
from typing import Any, Dict, Optional, Sequence

from langchain_core.messages import BaseMessage

from .specialist_graph import build_specialist_runnable
from .tools import finance_tools

logger = logging.getLogger(__name__)

OPERATION_ALIASES = {
    "analyze": "trend_summary",
    "analyse": "trend_summary",
    "review": "trend_summary",
    "revenue_trend_analysis": "trend_summary",
    "revenue_analysis": "trend_summary",
    "sales_analysis": "trend_summary",
}

SUPPORTED_OPERATIONS = [
    "daily_revenue",
    "weekly_summary",
    "trend_summary",
    "top_services",
    "customer_metrics",
    "export_report",
    "create_invoice",
    "record_payment",
    "process_refund",
    "list_invoices",
    "get_pos_summary",
    "get_inactive_clients",
    "get_top_clients",
    "get_visit_frequency_summary",
    "get_client_profile",
    "search_clients",
]

PLANNER_INSTRUCTIONS = """\
- daily_revenue: use for a single concrete date when you know the date.
- weekly_summary: use for a weekly summary when the owner asks about this week or a named week start.
- trend_summary: use for natural-language ranges like yesterday, last month, last 30 days, february, quarterly trends.
- top_services: use for best-selling or most popular services; arguments: limit(optional).
- customer_metrics: use for customer counts, repeat rate, new vs repeat.
- export_report: use when the owner asks for CSV or export; arguments: format(optional, usually csv).
- create_invoice: use when the owner asks to create an invoice; arguments: service_name, unit_price, quantity(optional), customer_id(optional), tax_rate(optional).
- record_payment: use when the owner asks to record a payment; arguments: amount, method(optional), invoice_id(optional).
- process_refund: use when the owner asks to refund a payment; arguments: payment_id, refund_amount(optional), reason(optional).
- list_invoices: use to list invoices; arguments: status(optional), limit(optional).
- get_pos_summary: use for cash/card breakdowns by date.
- get_inactive_clients: use for lapsed or inactive clients; arguments: days_threshold(optional).
- get_top_clients: use for best clients or most frequent clients; arguments: limit(optional).
- get_visit_frequency_summary: use for regulars, at-risk, and lapsed client mix.
- get_client_profile: use when a specific client id is already known.
- search_clients: use when the owner gives a client name rather than an id.
- Never output analyze, analyse, answer, respond, summarize, or review as the operation. Pick the closest supported operation instead.
"""


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def _recent_conversation_text(messages: Sequence[BaseMessage]) -> str:
    recent_messages = list(messages or [])[-6:]
    parts = []
    for message in recent_messages:
        parts.append(_flatten_text(getattr(message, "content", None)))
        additional_kwargs = getattr(message, "additional_kwargs", None)
        if additional_kwargs:
            parts.append(_flatten_text(additional_kwargs))
    return " ".join(part for part in parts if part).strip()


def _latest_user_text(messages: Sequence[BaseMessage]) -> str:
    for message in reversed(list(messages or [])):
        if getattr(message, "type", None) == "human":
            return _flatten_text(getattr(message, "content", None)).strip()
    return ""


def _humanize_window_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "the requested period"
    return text.replace("_", " ")


def _requests_finance_trend(text: str) -> bool:
    prompt = str(text or "").lower()
    if not prompt:
        return False

    trend_markers = (
        "trend",
        "graph",
        "chart",
        "over time",
        "for each day",
        "for each date",
        "by day",
        "daily breakdown",
        "line",
        "plot",
    )
    if any(marker in prompt for marker in trend_markers):
        return True

    return bool(
        re.search(r"\b(?:last|past|previous)\s+\d{1,3}\s+days?\b", prompt)
        or re.search(r"\b(?:last|past|previous)\s+\d{1,2}\s+weeks?\b", prompt)
        or re.search(r"\b(?:last|past|previous)\s+\d{1,2}\s+months?\b", prompt)
    )


def _prefers_weekly_summary(text: str) -> bool:
    prompt = str(text or "").lower()
    return any(phrase in prompt for phrase in ("this week", "weekly", "week start", "week starting"))


def _prefers_structured_table(text: str) -> bool:
    prompt = str(text or "").lower()
    return any(
        phrase in prompt
        for phrase in (
            "as a list",
            "in a list",
            "show a list",
            "show me a list",
            "table",
            "tabular",
            "sortable",
            "for each day",
            "for each date",
            "by day",
            "by date",
            "daily breakdown",
        )
    )


def _looks_like_top_services_request(text: str) -> bool:
    prompt = str(text or "").lower()
    if not prompt:
        return False

    has_service_subject = any(keyword in prompt for keyword in ("service", "services"))
    has_ranking_language = any(
        phrase in prompt
        for phrase in (
            "top",
            "best-selling",
            "best selling",
            "most popular",
            "popular services",
        )
    )
    return has_service_subject and has_ranking_language


def _looks_like_customer_metrics_request(text: str) -> bool:
    prompt = str(text or "").lower()
    if not prompt:
        return False

    return any(
        phrase in prompt
        for phrase in (
            "customer metrics",
            "client metrics",
            "repeat rate",
            "new vs repeat",
            "repeat customer",
            "repeat customers",
            "top clients",
            "best clients",
            "inactive clients",
            "lapsed clients",
            "visit frequency",
            "client profile",
        )
    )


def _looks_like_weekly_revenue_breakdown_request(text: str) -> bool:
    prompt = str(text or "").lower()
    if not prompt or not _prefers_weekly_summary(prompt):
        return False

    has_revenue_subject = any(
        keyword in prompt for keyword in ("revenue", "sales", "average ticket", "avg ticket")
    )
    has_explicit_trend_language = any(
        keyword in prompt for keyword in ("trend", "graph", "chart", "plot", "line", "over time")
    )
    wants_breakdown = _prefers_structured_table(prompt) or any(
        keyword in prompt for keyword in ("average ticket", "avg ticket", "customers")
    )

    return has_revenue_subject and wants_breakdown and not has_explicit_trend_language


def _extract_requested_limit(text: str) -> Optional[int]:
    prompt = str(text or "").lower()
    if not prompt:
        return None

    match = re.search(r"\btop\s+(\d{1,2})\b", prompt)
    if not match:
        return None

    try:
        requested_limit = int(match.group(1))
    except (TypeError, ValueError):
        return None

    if requested_limit <= 0:
        return None
    return min(requested_limit, 25)


def _resolve_obvious_daily_date(text: str) -> Optional[str]:
    prompt = str(text or "").lower().strip()
    if not prompt:
        return None

    explicit_date = finance_tools.extract_requested_date(prompt)
    if explicit_date:
        return explicit_date

    now = datetime.now()
    if "yesterday" in prompt:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    if "today" in prompt:
        return now.strftime("%Y-%m-%d")

    return None


def _build_finance_fast_plan(messages: Sequence[BaseMessage]) -> Optional[Dict[str, Any]]:
    latest_user_text = _latest_user_text(messages)
    if not latest_user_text:
        return None

    prompt = latest_user_text.lower()
    if _looks_like_top_services_request(latest_user_text):
        return {
            "operation": "top_services",
            "arguments": {"limit": _extract_requested_limit(latest_user_text) or 5},
            "requires_clarification": False,
            "clarification_question": "",
            "rationale": "Finance fast-path matched an obvious service ranking request.",
        }

    revenue_subject_signals = any(
        keyword in prompt
        for keyword in ("revenue", "sales", "trend", "performance", "average ticket", "avg ticket")
    )

    if not revenue_subject_signals or _looks_like_customer_metrics_request(latest_user_text):
        return None

    if _looks_like_weekly_revenue_breakdown_request(latest_user_text):
        return {
            "operation": "weekly_summary",
            "arguments": {},
            "requires_clarification": False,
            "clarification_question": "",
            "rationale": "Finance fast-path matched a weekly revenue breakdown request.",
        }

    if _requests_finance_trend(latest_user_text):
        return {
            "operation": "trend_summary",
            "arguments": {"query": latest_user_text},
            "requires_clarification": False,
            "clarification_question": "",
            "rationale": "Finance fast-path matched an obvious trend request.",
        }

    specific_date = _resolve_obvious_daily_date(latest_user_text)
    if specific_date:
        return {
            "operation": "daily_revenue",
            "arguments": {"date": specific_date},
            "requires_clarification": False,
            "clarification_question": "",
            "rationale": "Finance fast-path matched an obvious single-day revenue request.",
        }

    if _prefers_weekly_summary(latest_user_text):
        return {
            "operation": "weekly_summary",
            "arguments": {},
            "requires_clarification": False,
            "clarification_question": "",
            "rationale": "Finance fast-path matched an obvious weekly summary request.",
        }

    return None


def _normalize_finance_operation(operation: str, plan: Dict[str, Any], messages: Sequence[BaseMessage]) -> str:
    normalized_operation = str(operation or "").strip().lower()
    if normalized_operation in OPERATION_ALIASES:
        normalized_operation = OPERATION_ALIASES[normalized_operation]

    plan_text = _flatten_text(plan).lower()
    conversation_text = _recent_conversation_text(messages).lower()
    latest_user_text = _latest_user_text(messages).lower()
    prompt_text = f"{conversation_text} {plan_text}".strip()
    combined_text = f"{normalized_operation} {prompt_text}".strip()
    generic_operations = {"answer", "respond", "summarize", "summary", "lookup", "analyze", "analyse", "review"}

    revenue_signals = any(
        keyword in prompt_text
        for keyword in ("revenue", "sales", "trend", "performance", "week", "month", "quarter", "year", "yesterday", "today")
    )
    customer_signals = any(
        keyword in prompt_text
        for keyword in ("customer", "customers", "client", "clients", "repeat rate", "new vs repeat")
    )
    user_revenue_signals = any(
        keyword in latest_user_text
        for keyword in ("revenue", "sales", "trend", "performance", "week", "month", "quarter", "year", "yesterday", "today")
    )
    user_customer_signals = any(
        keyword in latest_user_text
        for keyword in ("customer", "customers", "client", "clients", "repeat rate", "new vs repeat")
    )

    def _latest_user_operation() -> Optional[str]:
        if user_revenue_signals and not user_customer_signals:
            if _requests_finance_trend(latest_user_text):
                return "trend_summary"
            if finance_tools.extract_requested_date(latest_user_text):
                return "daily_revenue"
            if _prefers_weekly_summary(latest_user_text):
                return "weekly_summary"
            return "trend_summary"
        if user_customer_signals and not user_revenue_signals:
            return "customer_metrics"
        return None

    latest_user_operation = _latest_user_operation()

    if normalized_operation == "customer_metrics" and (
        (user_revenue_signals and not user_customer_signals) or (revenue_signals and not customer_signals)
    ):
        if _requests_finance_trend(combined_text):
            return "trend_summary"
        if finance_tools.extract_requested_date(combined_text):
            return "daily_revenue"
        if _prefers_weekly_summary(combined_text):
            return "weekly_summary"
        return "trend_summary"

    if normalized_operation == "daily_revenue" and _requests_finance_trend(combined_text):
        return "trend_summary"

    if normalized_operation == "weekly_summary" and _requests_finance_trend(combined_text):
        return "trend_summary"

    if normalized_operation in generic_operations or normalized_operation not in SUPPORTED_OPERATIONS:
        if any(keyword in combined_text for keyword in ("invoice", "invoices")):
            return "list_invoices"
        if latest_user_operation is not None:
            return latest_user_operation
        if any(keyword in combined_text for keyword in ("customer", "customers", "client", "clients", "repeat rate", "new vs repeat")):
            return "customer_metrics"
        if any(keyword in combined_text for keyword in ("service", "services", "best-selling", "most popular")):
            return "top_services"
        if any(keyword in combined_text for keyword in ("revenue", "sales", "trend", "performance", "week", "month", "quarter", "year", "yesterday", "today")):
            if _requests_finance_trend(combined_text):
                return "trend_summary"
            if finance_tools.extract_requested_date(combined_text):
                return "daily_revenue"
            if _prefers_weekly_summary(combined_text):
                return "weekly_summary"
            return "trend_summary"

    if normalized_operation == "trend_summary":
        if _requests_finance_trend(combined_text):
            return "trend_summary"
        if finance_tools.extract_requested_date(combined_text):
            return "daily_revenue"
        if _prefers_weekly_summary(combined_text):
            return "weekly_summary"

    return normalized_operation or str(operation or "").strip()


def _build_finance_executor(shop_id: int):
    def executor(operation: str, arguments: Dict[str, Any], messages: Sequence[BaseMessage]) -> Dict[str, Any]:
        user_text = ""
        for message in reversed(list(messages)):
            if hasattr(message, "content"):
                user_text = str(message.content)
                break

        if operation == "daily_revenue":
            return finance_tools.daily_revenue(shop_id, _optional_str(arguments.get("date")))
        if operation == "weekly_summary":
            result = finance_tools.weekly_summary(shop_id, _optional_str(arguments.get("week_start")))
            if _prefers_structured_table(user_text):
                result = dict(result)
                result["preferred_presentation"] = "table"
            return result
        if operation == "trend_summary":
            query = _optional_str(arguments.get("query")) or user_text
            result = finance_tools.trend_summary(shop_id, query)
            if _prefers_structured_table(query):
                result = dict(result)
                result["preferred_presentation"] = "table"
            return result
        if operation == "top_services":
            result = finance_tools.top_services(shop_id, _to_int(arguments.get("limit")) or 5)
            if _prefers_structured_table(user_text):
                result = dict(result)
                result["preferred_presentation"] = "table"
            return result
        if operation == "customer_metrics":
            return finance_tools.customer_metrics(shop_id, _optional_str(arguments.get("query")) or user_text)
        if operation == "export_report":
            return finance_tools.export_report(shop_id, _optional_str(arguments.get("format")) or "csv")
        if operation == "create_invoice":
            service_name = _optional_str(arguments.get("service_name") or arguments.get("description"))
            unit_price = _to_float(arguments.get("unit_price") or arguments.get("amount"))
            if not service_name or unit_price is None:
                return {"error": "create_invoice requires service_name and unit_price"}
            quantity = _to_int(arguments.get("quantity")) or 1
            customer_id = _to_int(arguments.get("customer_id"))
            tax_rate = _to_float(arguments.get("tax_rate")) or 0.0
            notes = _optional_str(arguments.get("notes"))
            return {
                "requires_approval": True,
                "action": "create_invoice",
                "details": {
                    "service_name": service_name,
                    "unit_price": unit_price,
                    "quantity": quantity,
                    "customer_id": customer_id,
                    "tax_rate": tax_rate,
                    "notes": notes,
                },
                "message": f"Creating an invoice for {service_name} at ${unit_price:.2f} has been submitted for owner approval.",
            }
        if operation == "record_payment":
            amount = _to_float(arguments.get("amount"))
            if amount is None:
                return {"error": "record_payment requires amount"}
            method = _optional_str(arguments.get("method")) or "cash"
            invoice_id = _to_int(arguments.get("invoice_id"))
            notes = _optional_str(arguments.get("notes"))
            return {
                "requires_approval": True,
                "action": "record_payment",
                "details": {
                    "amount": amount,
                    "method": method,
                    "invoice_id": invoice_id,
                    "notes": notes,
                },
                "message": f"Recording a {method} payment of ${amount:.2f} has been submitted for owner approval.",
            }
        if operation == "process_refund":
            payment_id = _to_int(arguments.get("payment_id"))
            if payment_id is None:
                return {"error": "process_refund requires payment_id"}
            refund_amount = _to_float(arguments.get("refund_amount") or arguments.get("amount"))
            reason = _optional_str(arguments.get("reason") or arguments.get("notes"))
            message = f"Refunding payment {payment_id}"
            if refund_amount is not None:
                message += f" for ${refund_amount:.2f}"
            message += " has been submitted for owner approval."
            return {
                "requires_approval": True,
                "action": "process_refund",
                "details": {
                    "payment_id": payment_id,
                    "refund_amount": refund_amount,
                    "reason": reason,
                },
                "message": message,
            }
        if operation == "list_invoices":
            return finance_tools.list_invoices(
                shop_id,
                status=_optional_str(arguments.get("status")),
                limit=_to_int(arguments.get("limit")) or 20,
            )
        if operation == "get_pos_summary":
            return finance_tools.get_pos_summary(shop_id, _optional_str(arguments.get("date")))
        if operation == "get_inactive_clients":
            return finance_tools.get_inactive_clients(shop_id, _to_int(arguments.get("days_threshold")) or 45)
        if operation == "get_top_clients":
            return finance_tools.get_top_clients(shop_id, _to_int(arguments.get("limit")) or 10)
        if operation == "get_visit_frequency_summary":
            return finance_tools.get_visit_frequency_summary(shop_id)
        if operation == "get_client_profile":
            client_id = _to_int(arguments.get("client_id"))
            if client_id is None:
                return {"error": "get_client_profile requires client_id"}
            return finance_tools.get_client_profile(shop_id, client_id)
        if operation == "search_clients":
            name = _optional_str(arguments.get("name") or arguments.get("query"))
            if not name:
                return {"error": "search_clients requires a client name"}
            return finance_tools.search_clients(shop_id, name)
        return {"error": f"Unsupported finance operation: {operation}"}

    return executor


def _format_finance_response(operation: str, result: Dict[str, Any]) -> str:
    if result.get("error"):
        return f"I couldn't complete that finance task: {result['error']}"
    if operation == "daily_revenue":
        completed_services = int(result.get('completed_services', 0) or 0)
        total_revenue = float(result.get('total_revenue', 0.0) or 0.0)
        if completed_services == 0 and total_revenue <= 0:
            return (
                f"I don't see any completed services or recorded revenue for {result.get('date')} yet. "
                "That usually means no services were closed out that day, or the shop data has not been backfilled yet."
            )
        return (
            f"Revenue for {result.get('date')} was ${total_revenue:.2f} "
            f"across {completed_services} completed services. "
            f"Average transaction was ${float(result.get('average_transaction', 0.0) or 0.0):.2f}."
        )
    if operation == "weekly_summary":
        completed_services = int(result.get('completed_services', 0) or 0)
        total_revenue = float(result.get('total_revenue', 0.0) or 0.0)
        total_customers = int(result.get('total_customers', 0) or 0)
        if completed_services == 0 and total_revenue <= 0:
            return (
                f"I don't see any completed services or recorded revenue for the week starting {result.get('week_start')} yet. "
                "That usually means this week's services have not been closed out yet, or daily analytics have not been populated for these dates."
            )
        if str(result.get("preferred_presentation") or "").lower() == "table":
            return f"Here is the day-by-day revenue table for the week starting {result.get('week_start')}."
        return (
            f"Week starting {result.get('week_start')} generated ${total_revenue:.2f} from {completed_services} completed services "
            f"and {total_customers} customer visit{'s' if total_customers != 1 else ''}. "
            f"Best day: {result.get('best_day') or 'not available'}. "
            f"Average ticket: ${float(result.get('average_transaction', 0.0) or 0.0):.2f}."
        )
    if operation == "trend_summary":
        completed_services = int(result.get('completed_services', 0) or 0)
        total_revenue = float(result.get('total_revenue', 0.0) or 0.0)
        window_label = _humanize_window_label(result.get('window_display') or result.get('window'))
        if completed_services == 0 and total_revenue <= 0:
            return (
                f"I don't see any completed services or recorded revenue for {window_label} yet. "
                "If you expected activity, the underlying analytics for that range may still need to be populated."
            )
        if str(result.get("preferred_presentation") or "").lower() == "table":
            return f"Here is the day-by-day revenue table for {window_label}."
        return (
            f"For {window_label}, total revenue was ${total_revenue:.2f} "
            f"from {completed_services} completed services. "
            f"Best period: {result.get('best_period') or 'not available'} at ${float(result.get('best_period_revenue', 0.0) or 0.0):.2f}."
        )
    if operation == "top_services":
        services = list(result.get("services") or [])
        if not services:
            return "I couldn't find any active services to rank right now."
        if str(result.get("preferred_presentation") or "").lower() == "table":
            return "Here is the service table I found for the current catalog."
        lines = []
        for service in services[:8]:
            lines.append(f"- {service.get('name')} — ${float(service.get('cost', 0.0) or 0.0):.2f}")
        return "Top services:\n" + "\n".join(lines)
    if operation == "customer_metrics":
        total_customers = int(result.get('total_customers', 0) or 0)
        new_customers = int(result.get('new_customers', 0) or 0)
        repeat_customers = int(result.get('repeat_customers', 0) or 0)
        window_label = _humanize_window_label(result.get('window_display') or result.get('window'))
        if total_customers == 0 and new_customers == 0 and repeat_customers == 0:
            return (
                f"I don't see any customer activity recorded for {window_label} yet. "
                "That usually means there were no completed visits in that window, or customer profiles have not been built up for this shop yet."
            )
        return (
            f"Customer metrics for {window_label}: {total_customers} total customers, "
            f"{new_customers} new, {repeat_customers} repeat. "
            f"Repeat rate: {round(float(result.get('repeat_rate', 0.0) or 0.0) * 100, 1)}%."
        )
    if operation in {"get_inactive_clients", "get_top_clients", "search_clients"}:
        clients = list(result.get("clients") or [])
        if not clients:
            return "I couldn't find any matching clients."
        lines = []
        for client in clients[:8]:
            lines.append(f"- #{client.get('id')}: {client.get('name')} — {client.get('visit_count', client.get('days_inactive', 'n/a'))}")
        return f"I found {len(clients)} client(s):\n" + "\n".join(lines)
    if operation == "get_visit_frequency_summary":
        return (
            f"Client mix: {int(result.get('total_clients', 0) or 0)} total clients, "
            f"{int((result.get('regulars') or {}).get('count', 0) or 0)} regulars, "
            f"{int((result.get('at_risk') or {}).get('count', 0) or 0)} at risk, and "
            f"{int((result.get('lapsed') or {}).get('count', 0) or 0)} lapsed."
        )
    if operation == "get_client_profile":
        return str(result.get("summary") or f"Client #{result.get('id')} profile loaded.")
    if operation == "get_pos_summary":
        return (
            f"POS summary for {result.get('date')}: ${float(result.get('total_amount', 0.0) or 0.0):.2f} "
            f"across {int(result.get('total_transactions', 0) or 0)} transactions."
        )
    if operation == "list_invoices":
        invoices = list(result.get("invoices") or [])
        if not invoices:
            return "There are no invoices matching that filter right now."
        return f"I found {len(invoices)} invoice(s)."
    if operation == "export_report":
        return f"Report prepared: {result.get('filename')} ({result.get('format')})."
    if result.get("message"):
        return str(result["message"])
    return f"The finance specialist completed {operation.replace('_', ' ')}."

def create_finance_runnable(shop_id: int | None = None):
    if not shop_id:
        raise ValueError("shop_id is required — cannot build the finance graph without it")

    return build_specialist_runnable(
        agent_name="finance",
        shop_id=shop_id,
        temperature=0.2,
        planner_instructions=PLANNER_INSTRUCTIONS,
        supported_operations=SUPPORTED_OPERATIONS,
        operation_aliases=OPERATION_ALIASES,
        operation_normalizer=_normalize_finance_operation,
        fast_plan_builder=_build_finance_fast_plan,
        executor=_build_finance_executor(shop_id),
        formatter=_format_finance_response,
    )


__all__ = ["create_finance_runnable"]
