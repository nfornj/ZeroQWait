"""Finance specialist graph with explicit planner and executor nodes."""

import logging
from typing import Any, Dict, Optional, Sequence

from langchain_core.messages import BaseMessage

from .specialist_graph import build_specialist_runnable
from .tools import finance_tools

logger = logging.getLogger(__name__)

SUPPORTED_OPERATIONS = [
    "daily_revenue",
    "weekly_summary",
    "trend_summary",
    "top_services",
    "customer_metrics",
    "export_report",
    "create_invoice",
    "record_payment",
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
- list_invoices: use to list invoices; arguments: status(optional), limit(optional).
- get_pos_summary: use for cash/card breakdowns by date.
- get_inactive_clients: use for lapsed or inactive clients; arguments: days_threshold(optional).
- get_top_clients: use for best clients or most frequent clients; arguments: limit(optional).
- get_visit_frequency_summary: use for regulars, at-risk, and lapsed client mix.
- get_client_profile: use when a specific client id is already known.
- search_clients: use when the owner gives a client name rather than an id.
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
            return finance_tools.weekly_summary(shop_id, _optional_str(arguments.get("week_start")))
        if operation == "trend_summary":
            query = _optional_str(arguments.get("query")) or user_text
            return finance_tools.trend_summary(shop_id, query)
        if operation == "top_services":
            return finance_tools.top_services(shop_id, _to_int(arguments.get("limit")) or 5)
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
        return (
            f"Revenue for {result.get('date')} was ${float(result.get('total_revenue', 0.0) or 0.0):.2f} "
            f"across {int(result.get('completed_services', 0) or 0)} completed services. "
            f"Average transaction was ${float(result.get('average_transaction', 0.0) or 0.0):.2f}."
        )
    if operation == "weekly_summary":
        return (
            f"Week starting {result.get('week_start')} generated ${float(result.get('total_revenue', 0.0) or 0.0):.2f}. "
            f"Completed services: {int(result.get('completed_services', 0) or 0)}. "
            f"Best day: {result.get('best_day') or 'not available'}."
        )
    if operation == "trend_summary":
        return (
            f"For {result.get('window', 'the requested period')}, total revenue was ${float(result.get('total_revenue', 0.0) or 0.0):.2f} "
            f"from {int(result.get('completed_services', 0) or 0)} completed services. "
            f"Best period: {result.get('best_period') or 'not available'} at ${float(result.get('best_period_revenue', 0.0) or 0.0):.2f}."
        )
    if operation == "top_services":
        services = list(result.get("services") or [])
        if not services:
            return "I couldn't find any active services to rank right now."
        lines = []
        for service in services[:8]:
            lines.append(f"- {service.get('name')} — ${float(service.get('cost', 0.0) or 0.0):.2f}")
        return "Top services:\n" + "\n".join(lines)
    if operation == "customer_metrics":
        return (
            f"Customer metrics for {result.get('window', 'the requested period')}: {int(result.get('total_customers', 0) or 0)} total customers, "
            f"{int(result.get('new_customers', 0) or 0)} new, {int(result.get('repeat_customers', 0) or 0)} repeat. "
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
        executor=_build_finance_executor(shop_id),
        formatter=_format_finance_response,
    )


__all__ = ["create_finance_runnable"]
