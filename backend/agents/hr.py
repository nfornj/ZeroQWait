"""
HR Sub-Agent - Handles employees, shifts, and scheduling.

Responsibilities:
- Employee management (add, remove, list)
- Shift scheduling and assignments
- Employee availability and clock in/out
- Shift coverage and gaps
- Employee performance metrics

Phase 2: Placeholder implementation
Phase 3: Wire to HRMCP server

Tools called:
- list_employees(shop_id) → employee list
- add_employee(shop_id, name, role, phone, wages) → employee_id
- remove_employee(shop_id, employee_id) → confirmation
- get_shifts(shop_id, date=None, employee_id=None) → shift list
- assign_shift(shop_id, employee_id, start_time, end_time, date) → confirmation
- clock_in_out(shop_id, employee_id, action='in'|'out') → timestamp

Data sources:
- shop_employees table
- employee_shifts table
- employee_clock_in_out table (if tracking time)
"""

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import StateGraph, END

from .state import AgentState
from .tools import hr_tools


def classify_entry(state: AgentState) -> dict:
    """No-op node so conditional routing can inspect state safely."""
    return {}


def hr_intent_classifier(state: AgentState) -> str:
    """
    Classify the HR request type.
    
    Returns: "list_employees", "add_employee", "shift_schedule", "clock_in_out", "availability", "other"
    """
    
    messages = state.get("messages", [])
    if not messages:
        return "other"
    
    latest = messages[-1]
    if isinstance(latest, BaseMessage):
        content = str(latest.content).lower()
    else:
        content = str(latest).lower()
    
    # Keyword matching for Phase 2
    if any(word in content for word in ["add", "new", "hire", "employee", "staff"]):
        if "add" in content or "new" in content or "hire" in content:
            return "add_employee"
        return "list_employees"
    elif any(word in content for word in ["shift", "schedule", "assign", "time"]):
        return "shift_schedule"
    elif any(word in content for word in ["clock", "in", "out", "arrived", "left"]):
        return "clock_in_out"
    elif any(word in content for word in ["available", "available", "availability", "who"]):
        return "availability"
    else:
        return "other"


def handle_list_employees(state: AgentState) -> dict:
    """List all employees for the shop."""
    
    shop_id = state["tenant_id"]
    result = hr_tools.list_employees(shop_id)
    if result.get("error"):
        response = AIMessage(content=f"I couldn't load the employee roster: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    employees = result.get("employees", [])
    if employees:
        lines = [
            f"{index}. {employee.get('user', {}).get('username', f'User {employee.get("user_id")}')} - {'Active' if employee.get('is_active') else 'Inactive'}"
            for index, employee in enumerate(employees, start=1)
        ]
        content = f"👥 Employees for Shop {shop_id}:\n" + "\n".join(lines) + f"\n\nTotal: {result.get('count', len(employees))} employees"
    else:
        content = "There are no employees configured for this shop yet."
    response = AIMessage(content=content)
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result
    }


def handle_add_employee(state: AgentState) -> dict:
    """Propose adding a new employee (high-impact action requiring approval)."""
    
    shop_id = state["tenant_id"]
    metadata = state.get("metadata") or {}
    employee_name = metadata.get("employee_name") or "New Employee"
    employee_email = metadata.get("employee_email") or f"employee_{shop_id}_{employee_name.lower().replace(' ', '_')}@zeroqwait.local"
    employee_phone = metadata.get("employee_phone")
    employee_role = metadata.get("employee_role") or "employee"
    return {
        "messages": list(state["messages"]) + [AIMessage(
            content=f"I can add {employee_name} as a {employee_role}. Please approve this action to continue."
        )],
        "pending_approval": {
            "action": "add_employee",
            "shop_id": shop_id,
            "details": {
                "name": employee_name,
                "email": employee_email,
                "phone": employee_phone,
                "role": employee_role,
                "impact": "Creates a new active employee account and links it to this shop",
            },
        },
        "needs_human_input": True,
        "tool_results": None,
    }


def handle_shift_schedule(state: AgentState) -> dict:
    """View or manage shift schedules."""
    
    shop_id = state["tenant_id"]
    result = hr_tools.get_shifts(shop_id)
    if result.get("error"):
        response = AIMessage(content=f"I couldn't load today's shifts: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    shifts = result.get("shifts", [])
    if shifts:
        lines = [
            f"- User {shift.get('user_id')}: {shift.get('clock_in')} to {shift.get('clock_out') or 'active'}"
            for shift in shifts[:8]
        ]
        content = f"📅 Today's Shift Schedule (Shop {shop_id}):\n" + "\n".join(lines)
    else:
        content = "No shifts are scheduled for today yet."
    response = AIMessage(content=content)
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result
    }


def handle_clock_in_out(state: AgentState) -> dict:
    """Log employee clock in/out."""
    
    shop_id = state["tenant_id"]
    metadata = state.get("metadata") or {}
    user_id = metadata.get("employee_user_id")
    if not user_id:
        employees = hr_tools.list_employees(shop_id).get("employees", [])
        user_id = employees[0].get("user_id") if employees else None
    if not user_id:
        response = AIMessage(content="I couldn't find an employee to clock in or out.")
        return {"messages": list(state["messages"]) + [response], "tool_results": None}

    action = metadata.get("clock_action") or "in"
    result = hr_tools.clock_in_out(shop_id, int(user_id), action)
    if result.get("error"):
        response = AIMessage(content=f"I couldn't update the clock record: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    shift = result.get("shift", {})
    response = AIMessage(
        content=f"⏰ Clock Record:"
                f"\n- Employee User ID: {user_id}"
                f"\n- Action: Clocked {'In' if action == 'in' else 'Out'}"
                f"\n- Time: {shift.get('clock_in') if action == 'in' else shift.get('clock_out')}"
    )
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result
    }


def handle_availability(state: AgentState) -> dict:
    """Check employee availability for a time slot."""
    
    shop_id = state["tenant_id"]
    employees_result = hr_tools.list_employees(shop_id)
    shifts_result = hr_tools.get_shifts(shop_id)
    if employees_result.get("error"):
        response = AIMessage(content=f"I couldn't check availability: {employees_result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": employees_result}

    employees = employees_result.get("employees", [])
    active_shift_user_ids = {shift.get("user_id") for shift in shifts_result.get("shifts", [])}
    available = [
        employee.get("user", {}).get("username", f"User {employee.get('user_id')}")
        for employee in employees
        if employee.get("user_id") not in active_shift_user_ids
    ]
    unavailable = [
        employee.get("user", {}).get("username", f"User {employee.get('user_id')}")
        for employee in employees
        if employee.get("user_id") in active_shift_user_ids
    ]
    response = AIMessage(
        content=f"🗓️ Availability Check:"
                f"\n- Available: {', '.join(available) if available else 'No one currently free'}"
                f"\n- Unavailable: {', '.join(unavailable) if unavailable else 'No active shifts'}"
                f"\n\nWhich employee would you like to assign?"
    )
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": {
            "employees": employees_result,
            "shifts": shifts_result,
            "available": available,
            "unavailable": unavailable,
        }
    }


def handle_other(state: AgentState) -> dict:
    """Generic HR response."""
    
    response = AIMessage(
        content="I can help with:"
                "\n- List all employees"
                "\n- Add a new employee"
                "\n- View shift schedule"
                "\n- Employee clock in/out"
                "\n- Check availability"
                "\n\nWhat do you need help with?"
    )
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": None
    }


def build_hr_graph():
    """
    Build the LangGraph StateGraph for the HR sub-agent.
    
    Flow:
    1. classify - determine HR query type
    2. route to handler (list, add, schedule, clock, availability, other)
    3. END
    """
    
    graph = StateGraph(AgentState)
    
    # Nodes
    graph.add_node("classify", classify_entry)
    graph.add_node("list_employees", handle_list_employees)
    graph.add_node("add_employee", handle_add_employee)
    graph.add_node("shift_schedule", handle_shift_schedule)
    graph.add_node("clock_in_out", handle_clock_in_out)
    graph.add_node("availability", handle_availability)
    graph.add_node("other", handle_other)
    
    # Edges
    graph.add_conditional_edges(
        "classify",
        lambda state: hr_intent_classifier(state),
        {
            "list_employees": "list_employees",
            "add_employee": "add_employee",
            "shift_schedule": "shift_schedule",
            "clock_in_out": "clock_in_out",
            "availability": "availability",
            "other": "other"
        }
    )
    
    # All handlers end
    for node in ["list_employees", "add_employee", "shift_schedule", "clock_in_out", "availability", "other"]:
        graph.add_edge(node, END)
    
    # Entry point
    graph.set_entry_point("classify")
    
    return graph


def create_hr_runnable():
    """Compile the HR graph into an executable runnable."""
    graph = build_hr_graph()
    return graph.compile()


__all__ = [
    "build_hr_graph",
    "create_hr_runnable"
]
