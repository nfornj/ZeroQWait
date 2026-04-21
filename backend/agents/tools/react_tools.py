"""
ReAct-compatible tool factories for LangGraph sub-agents.

Each ``make_*_tools(shop_id)`` function returns a list of @tool-decorated
functions with ``shop_id`` captured via closure so the LLM never needs to
guess tenant IDs.
"""

from typing import Dict, Any, List, Optional
from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# Receptionist / Booking tools
# ---------------------------------------------------------------------------

def make_receptionist_tools(shop_id: int) -> list:
    """Create tenant-scoped booking + appointment tools for the Receptionist agent."""
    from . import booking_tools, appointment_tools

    @tool
    def list_queue() -> Dict[str, Any]:
        """Get the current queue status — all waiting customers, positions, and live wait-time metrics."""
        return booking_tools.list_queue(shop_id)

    @tool
    def join_queue(customer_name: str, phone: str = "") -> Dict[str, Any]:
        """Add a customer to the queue by name and optional phone number."""
        return booking_tools.join_queue(shop_id, customer_name, phone or None)

    @tool
    def call_next(employee_id: Optional[int] = None) -> Dict[str, Any]:
        """Call the next waiting customer from the queue to be served."""
        return booking_tools.call_next(shop_id, employee_id)

    @tool
    def get_wait_time() -> Dict[str, Any]:
        """Get the estimated wait time and current queue length."""
        return booking_tools.get_wait_time(shop_id)

    @tool
    def close_queue(reason: str = "Owner requested closure") -> Dict[str, Any]:
        """Propose closing the active queue. HIGH IMPACT — does NOT execute immediately; requires owner approval first."""
        return {
            "requires_approval": True,
            "action": "close_queue",
            "details": {"reason": reason},
            "message": f"Queue closure has been submitted for owner approval. Reason: {reason}",
        }

    @tool
    def search_services(query: str = "") -> Dict[str, Any]:
        """List available services. Optionally filter by name keyword."""
        return booking_tools.search_services(shop_id, query or None)

    @tool
    def create_service(name: str, cost: float, duration_minutes: int = 30, currency: str = "USD") -> Dict[str, Any]:
        """Create a new service for the shop with name, price, and duration."""
        return booking_tools.create_service(shop_id, name, cost, duration_minutes, currency=currency)

    @tool
    def update_service(service_id: int, name: Optional[str] = None, cost: Optional[float] = None, duration_minutes: Optional[int] = None) -> Dict[str, Any]:
        """Update an existing service's name, price, or duration. Pass the service_id from search_services."""
        return booking_tools.update_service(shop_id, service_id, name=name, cost=cost, duration_minutes=duration_minutes)

    @tool
    def delete_service(service_id: int) -> Dict[str, Any]:
        """Deactivate a service by ID. Use search_services first to find the ID."""
        return booking_tools.delete_service(shop_id, service_id)

    @tool
    def book_appointment(service_id: int, scheduled_start: str, customer_name: str, customer_phone: str = "", employee_id: Optional[int] = None) -> Dict[str, Any]:
        """Book an appointment. scheduled_start must be ISO-8601 format (e.g. 2026-04-20T14:00)."""
        return appointment_tools.book_appointment(
            shop_id, service_id, scheduled_start, customer_name,
            customer_phone=customer_phone or None, employee_id=employee_id,
        )

    @tool
    def list_appointments(date: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        """List appointments, optionally filtered by date (YYYY-MM-DD) and status."""
        return appointment_tools.list_appointments(shop_id, date=date, status=status)

    @tool
    def cancel_appointment(appointment_id: int, reason: str = "") -> Dict[str, Any]:
        """Cancel an appointment by ID."""
        return appointment_tools.cancel_appointment(shop_id, appointment_id, reason=reason or None)

    @tool
    def get_available_slots(service_id: int, date: str) -> Dict[str, Any]:
        """Get available appointment slots for a service on a given date (YYYY-MM-DD)."""
        return appointment_tools.get_available_slots(shop_id, service_id, date)

    return [
        list_queue, join_queue, call_next, get_wait_time, close_queue,
        search_services, create_service, update_service, delete_service,
        book_appointment, list_appointments, cancel_appointment, get_available_slots,
    ]


# ---------------------------------------------------------------------------
# Finance tools
# ---------------------------------------------------------------------------

def make_finance_tools(shop_id: int) -> list:
    """Create tenant-scoped finance + client-insight tools for the Finance agent."""
    from . import finance_tools, client_insights_tools, payment_tools

    @tool
    def daily_revenue(date: Optional[str] = None) -> Dict[str, Any]:
        """Get revenue summary for a specific date (YYYY-MM-DD). Defaults to today."""
        return finance_tools.daily_revenue(shop_id, date)

    @tool
    def weekly_summary(week_start: Optional[str] = None) -> Dict[str, Any]:
        """Get weekly revenue summary. Optionally pass the Monday date (YYYY-MM-DD)."""
        return finance_tools.weekly_summary(shop_id, week_start)

    @tool
    def trend_summary(query: str) -> Dict[str, Any]:
        """Get revenue/customer trends for a time range described in natural language (e.g. 'last 30 days', 'february')."""
        return finance_tools.trend_summary(shop_id, query)

    @tool
    def top_services(limit: int = 5) -> Dict[str, Any]:
        """Get the most popular services ranked by number of completions."""
        return finance_tools.top_services(shop_id, limit)

    @tool
    def customer_metrics(query: str = "") -> Dict[str, Any]:
        """Get customer visit metrics — total, new, repeat rate, etc. Pass the owner's query for context."""
        return finance_tools.customer_metrics(shop_id, query or None)

    @tool
    def get_pos_summary(date: Optional[str] = None) -> Dict[str, Any]:
        """Get point-of-sale summary (cash/card breakdown) for a date. Defaults to today."""
        return finance_tools.get_pos_summary(shop_id, date)

    @tool
    def list_invoices(status: Optional[str] = None) -> Dict[str, Any]:
        """List invoices, optionally filtered by status (paid, unpaid, overdue)."""
        return finance_tools.list_invoices(shop_id, status)

    @tool
    def create_invoice(description: str, quantity: int, unit_price: float, customer_id: Optional[int] = None, tax_rate: float = 0.0) -> Dict[str, Any]:
        """Create a single-line invoice. Example: create_invoice(description="Haircut", quantity=1, unit_price=35.00)."""
        line_items = [{"description": description, "quantity": quantity, "unit_price": unit_price}]
        return payment_tools.create_invoice(shop_id, line_items, customer_id=customer_id, tax_rate=tax_rate)

    @tool
    def record_payment(amount: float, method: str = "cash", invoice_id: Optional[int] = None, tip_amount: float = 0.0) -> Dict[str, Any]:
        """Record a payment — method: cash, card, online, other."""
        return payment_tools.record_payment(shop_id, amount, method, invoice_id=invoice_id, tip_amount=tip_amount)

    @tool
    def get_inactive_clients(days_threshold: int = 45) -> List[Dict[str, Any]]:
        """Get clients who haven't visited in the specified number of days."""
        return client_insights_tools.get_inactive_clients(shop_id, days_threshold)

    @tool
    def get_top_clients(limit: int = 10) -> List[Dict[str, Any]]:
        """Get most frequent clients ranked by visit count."""
        return client_insights_tools.get_top_clients(shop_id, limit)

    @tool
    def get_visit_frequency_summary() -> Dict[str, Any]:
        """Get overall visit frequency stats — average visits, frequency brackets, etc."""
        return client_insights_tools.get_visit_frequency_summary(shop_id)

    @tool
    def get_client_profile(client_id: int) -> Dict[str, Any]:
        """Get detailed profile of a specific client by ID."""
        return client_insights_tools.get_client_profile(shop_id, client_id)

    @tool
    def search_clients(name: str) -> List[Dict[str, Any]]:
        """Search for clients by name (partial match)."""
        return client_insights_tools.get_client_search(shop_id, name)

    return [
        daily_revenue, weekly_summary, trend_summary, top_services,
        customer_metrics, get_pos_summary, list_invoices,
        create_invoice, record_payment,
        get_inactive_clients, get_top_clients, get_visit_frequency_summary,
        get_client_profile, search_clients,
    ]


# ---------------------------------------------------------------------------
# HR tools
# ---------------------------------------------------------------------------

def make_hr_tools(shop_id: int) -> list:
    """Create tenant-scoped HR tools for the HR agent."""
    from . import hr_tools

    @tool
    def list_employees(include_inactive: bool = False) -> Dict[str, Any]:
        """List all employees. Set include_inactive=True to include deactivated ones."""
        return hr_tools.list_employees(shop_id, include_inactive)

    @tool
    def add_employee(name: str, email: str, phone: str = "", role: str = "employee") -> Dict[str, Any]:
        """Propose adding a new employee. HIGH IMPACT — does NOT execute immediately; requires owner approval first."""
        return {
            "requires_approval": True,
            "action": "add_employee",
            "details": {"name": name, "email": email, "phone": phone or None, "role": role},
            "message": f"Adding employee '{name}' has been submitted for owner approval.",
        }

    @tool
    def remove_employee(user_id: int) -> Dict[str, Any]:
        """Propose deactivating an employee by user ID. HIGH IMPACT — does NOT execute immediately; requires owner approval first. Use list_employees to find the ID."""
        return {
            "requires_approval": True,
            "action": "remove_employee",
            "details": {"user_id": user_id},
            "message": f"Removing employee (user_id={user_id}) has been submitted for owner approval.",
        }

    @tool
    def get_shifts(date: Optional[str] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get shift schedule. Optionally filter by date (YYYY-MM-DD) or employee user_id."""
        return hr_tools.get_shifts(shop_id, date, user_id)

    @tool
    def assign_shift(user_id: int, start_time: str, end_time: str, date: str) -> Dict[str, Any]:
        """Propose assigning a shift. HIGH IMPACT — does NOT execute immediately; requires owner approval first."""
        return {
            "requires_approval": True,
            "action": "assign_shift",
            "details": {
                "user_id": user_id,
                "start_time": start_time,
                "end_time": end_time,
                "date": date,
            },
            "message": (
                f"Assigning a shift for employee {user_id} on {date} from {start_time} to {end_time} "
                "has been submitted for owner approval."
            ),
        }

    @tool
    def clock_in_out(user_id: int, action: str) -> Dict[str, Any]:
        """Clock an employee in or out. action='clock_in' or 'clock_out'."""
        return hr_tools.clock_in_out(shop_id, user_id, action)

    return [list_employees, add_employee, remove_employee, get_shifts, assign_shift, clock_in_out]
