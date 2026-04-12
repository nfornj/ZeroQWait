"""
Finance Sub-Agent - Handles revenue, analytics, and financial reporting.

Responsibilities:
- Daily/weekly/monthly revenue summaries
- Service breakdown (which services make the most)
- Customer metrics (total customers, repeat customers, LTV)
- Financial reports and exports
- Pricing analysis and recommendations

Phase 2: Placeholder implementation
Phase 3: Wire to FinanceMCP server

Tools called:
- daily_revenue(shop_id, date=None) → revenue amount
- weekly_summary(shop_id, week=None) → revenue + metrics
- top_services(shop_id, limit=5) → services by revenue
- customer_metrics(shop_id) → customer stats
- export_report(shop_id, format='csv') → file path

Data sources:
- daily_analytics table (pre-computed daily snapshots)
- queues table (transaction history)
- shop_services table (service definitions)
"""

from typing import List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import StateGraph, END

from .state import AgentState
from .tools import finance_tools


TIMEFRAME_HINTS = [
    "today", "yesterday", "day", "daily", "week", "weekly", "month", "monthly",
    "quarter", "year", "yearly", "last", "this", "trend", "30 days", "7 days",
]

FINANCE_HINTS = [
    "revenue", "sales", "income", "profit", "finance", "financial", "analytics", "transaction",
]


def _latest_user_text(state: AgentState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return ""
    latest = messages[-1]
    return str(latest.content) if isinstance(latest, BaseMessage) else str(latest)


def _has_time_or_finance_hints(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in TIMEFRAME_HINTS + FINANCE_HINTS)


def _is_followup_transform_request(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in [
        "csv", "excel", "export", "download", "file",
        "dates only", "date only", "list dates", "only dates",
        "only revenue", "revenue only", "just dates", "just revenue",
    ])


def _find_previous_finance_query(state: AgentState) -> Optional[str]:
    """Find latest prior user message that contains finance/timeframe intent."""
    messages = state.get("messages", [])
    if not messages:
        return None

    # Walk backwards, skip the latest message (current turn).
    for msg in reversed(messages[:-1]):
        if isinstance(msg, HumanMessage):
            content = str(msg.content)
            if _has_time_or_finance_hints(content):
                return content
    return None


def _resolve_finance_query(state: AgentState) -> str:
    """Resolve effective query for this turn, using prior context for follow-ups."""
    current = _latest_user_text(state)
    if _has_time_or_finance_hints(current):
        return current

    prev = _find_previous_finance_query(state)
    if prev:
        return prev
    return current


def _points_to_csv(points: List[dict]) -> str:
    lines = ["period,revenue,customers,completed_services"]
    for p in points:
        lines.append(
            f"{p.get('period')},{float(p.get('revenue', 0.0)):.2f},{int(p.get('customers', 0))},{int(p.get('completed_services', 0))}"
        )
    return "\n".join(lines)


def classify_entry(state: AgentState) -> dict:
    """No-op node so conditional routing can inspect state safely."""
    return {}


def finance_intent_classifier(state: AgentState) -> str:
    """
    Classify the finance request type.
    
    Returns: "daily_revenue", "weekly_summary", "services_breakdown", "customer_metrics", "export", "other"
    """
    
    messages = state.get("messages", [])
    if not messages:
        return "other"
    
    latest = messages[-1]
    if isinstance(latest, BaseMessage):
        content = str(latest.content).lower()
    else:
        content = str(latest).lower()
    
    # Follow-up transform requests should preserve previous finance context.
    if _is_followup_transform_request(content):
        return "export"

    # Keyword matching for Phase 2
    if any(word in content for word in ["today", "today's", "daily"]):
        return "daily_revenue"
    elif any(word in content for word in ["week", "weekly"]):
        return "weekly_summary"
    elif any(word in content for word in ["month", "monthly", "year", "yearly", "quarter", "trend", "forecast"]):
        return "trend_summary"
    elif any(word in content for word in ["service", "top", "which", "breakdown"]):
        return "services_breakdown"
    elif any(word in content for word in ["customer", "repeat", "ltv", "metrics", "growth"]):
        return "customer_metrics"
    elif any(word in content for word in ["export", "download", "report", "pdf", "csv"]):
        return "export"
    elif any(word in content for word in ["revenue", "sales", "income", "profit", "finance", "financial", "analytics"]):
        return "trend_summary"
    else:
        return "other"


def handle_trend_summary(state: AgentState) -> dict:
    """Answer dynamic daily/weekly/monthly/yearly trend queries from backend data."""

    shop_id = state["tenant_id"]
    query = _resolve_finance_query(state)

    result = finance_tools.trend_summary(shop_id, query)
    if result.get("error"):
        response = AIMessage(content=f"I couldn't load the requested trend right now: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    points = result.get("points", [])
    if not points:
        response = AIMessage(
            content=(
                f"I found no finance records for that time window ({result.get('range_start')} to {result.get('range_end')}). "
                "Try asking for a broader range like 'this year trend'."
            )
        )
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    preview = points[-5:] if len(points) > 5 else points
    trend_lines = [
        f"- {point.get('period')}: ${float(point.get('revenue', 0.0)):.2f} ({point.get('completed_services', 0)} services)"
        for point in preview
    ]

    response = AIMessage(
        content=(
            f"📉 Finance Trend ({result.get('window', 'custom').replace('_', ' ').title()}) - Shop {shop_id}:"
            f"\n- Date range: {result.get('range_start')} to {result.get('range_end')}"
            f"\n- Total revenue: ${float(result.get('total_revenue', 0.0)):.2f}"
            f"\n- Completed services: {result.get('completed_services', 0)}"
            f"\n- Total customers: {result.get('total_customers', 0)}"
            f"\n- Average transaction: ${float(result.get('average_transaction', 0.0)):.2f}"
            f"\n- Best period: {result.get('best_period') or 'n/a'}"
            f"\n\nRecent points:\n" + "\n".join(trend_lines)
        )
    )

    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result,
    }


def handle_daily_revenue(state: AgentState) -> dict:
    """Get today's revenue summary."""
    
    shop_id = state["tenant_id"]
    result = finance_tools.daily_revenue(shop_id)
    if result.get("error"):
        response = AIMessage(content=f"I couldn't load today's revenue summary: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=f"📊 Today's Revenue Summary (Shop {shop_id}):"
                f"\n- Total revenue: ${float(result.get('total_revenue', 0.0)):.2f}"
                f"\n- Transactions: {result.get('transaction_count', 0)}"
                f"\n- Completed services: {result.get('completed_services', 0)}"
                f"\n- Average per transaction: ${float(result.get('average_transaction', 0.0)):.2f}"
    )
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result
    }


def handle_weekly_summary(state: AgentState) -> dict:
    """Get weekly revenue and metrics."""
    
    shop_id = state["tenant_id"]
    result = finance_tools.weekly_summary(shop_id)
    if result.get("error"):
        response = AIMessage(content=f"I couldn't load this week's summary: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=f"📈 Weekly Summary (Shop {shop_id}):"
                f"\n- Total revenue: ${float(result.get('total_revenue', 0.0)):.2f}"
                f"\n- Total transactions: {result.get('transaction_count', 0)}"
                f"\n- Completed services: {result.get('completed_services', 0)}"
                f"\n- Average transaction: ${float(result.get('average_transaction', 0.0)):.2f}"
                f"\n- Best day: {result.get('best_day') or 'No data yet'}"
    )
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result
    }


def handle_services_breakdown(state: AgentState) -> dict:
    """Show revenue breakdown by service."""
    
    shop_id = state["tenant_id"]
    result = finance_tools.top_services(shop_id)
    if result.get("error"):
        response = AIMessage(content=f"I couldn't load the service breakdown: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    services = result.get("services", [])
    if services:
        lines = [
            f"{index}. {service.get('name')} - ${float(service.get('revenue', 0.0)):.2f} ({service.get('count', 0)} services)"
            for index, service in enumerate(services, start=1)
        ]
        content = f"🎯 Top Services by Revenue (Shop {shop_id}):\n" + "\n".join(lines)
    else:
        content = "I don't have completed service revenue data yet."
    response = AIMessage(content=content)
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result
    }


def handle_customer_metrics(state: AgentState) -> dict:
    """Get customer analytics."""
    
    shop_id = state["tenant_id"]
    result = finance_tools.customer_metrics(shop_id)
    if result.get("error"):
        response = AIMessage(content=f"I couldn't load customer metrics: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=f"👥 Customer Metrics (Shop {shop_id}):"
                f"\n- Total customers: {result.get('total_customers', 0)}"
                f"\n- Repeat customers: {result.get('repeat_customers', 0)}"
                f"\n- Repeat rate: {float(result.get('repeat_rate', 0.0)) * 100:.0f}%"
                f"\n- Average customer LTV: ${float(result.get('average_ltv', 0.0)):.2f}"
    )
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result
    }


def handle_export_report(state: AgentState) -> dict:
    """Prepare contextual finance export/transform (CSV, dates-only, revenue-only)."""

    shop_id = state["tenant_id"]
    current_text = _latest_user_text(state).lower()
    query = _resolve_finance_query(state)

    # Reuse the same dynamic backend query path as trend requests.
    trend = finance_tools.trend_summary(shop_id, query)
    if trend.get("error"):
        response = AIMessage(content=f"I couldn't prepare the export right now: {trend['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": trend}

    points = trend.get("points", [])
    if not points:
        response = AIMessage(
            content=(
                f"I found no records to export for {trend.get('range_start')} to {trend.get('range_end')}. "
                "Try a broader time range first."
            )
        )
        return {"messages": list(state["messages"]) + [response], "tool_results": trend}

    # Transform output based on follow-up instruction.
    if any(token in current_text for token in ["dates only", "date only", "list dates", "only dates", "just dates"]):
        dates = [str(p.get("period")) for p in points]
        response = AIMessage(
            content=(
                f"📅 Dates only ({trend.get('range_start')} to {trend.get('range_end')}):\n"
                + "\n".join(f"- {d}" for d in dates)
            )
        )
        return {
            "messages": list(state["messages"]) + [response],
            "tool_results": {**trend, "transform": "dates_only", "values": dates},
        }

    if any(token in current_text for token in ["revenue only", "only revenue", "just revenue"]):
        lines = [f"- {p.get('period')}: ${float(p.get('revenue', 0.0)):.2f}" for p in points]
        response = AIMessage(
            content=(
                f"💰 Revenue only ({trend.get('range_start')} to {trend.get('range_end')}):\n" + "\n".join(lines)
            )
        )
        return {
            "messages": list(state["messages"]) + [response],
            "tool_results": {**trend, "transform": "revenue_only"},
        }

    csv_content = _points_to_csv(points)
    filename = f"finance_trend_{shop_id}_{trend.get('window', 'custom')}.csv"
    result = {
        **trend,
        "format": "csv",
        "filename": filename,
        "row_count": len(points),
        "csv_content": csv_content,
    }

    if result.get("error"):
        response = AIMessage(content=f"I couldn't prepare the export: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=f"📁 Report Export:"
                f"\n- Format: CSV"
                f"\n- Filename: {result.get('filename', 'report.csv')}"
                f"\n- Rows: {result.get('row_count', 0)}"
                f"\n- Date range: {result.get('range_start')} to {result.get('range_end')}"
                f"\n\nCSV Preview:"
                f"\n{chr(10).join(result.get('csv_content', '').splitlines()[:6])}"
    )
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result
    }


def handle_other(state: AgentState) -> dict:
    """Generic finance response."""
    
    # Fallback to dynamic trend query instead of generic canned response.
    return handle_trend_summary(state)


def build_finance_graph():
    """
    Build the LangGraph StateGraph for the Finance sub-agent.
    
    Flow:
    1. classify - determine finance query type
    2. route to handler (daily, weekly, services, customers, export, other)
    3. END
    """
    
    graph = StateGraph(AgentState)
    
    # Nodes
    graph.add_node("classify", classify_entry)
    graph.add_node("daily_revenue", handle_daily_revenue)
    graph.add_node("weekly_summary", handle_weekly_summary)
    graph.add_node("trend_summary", handle_trend_summary)
    graph.add_node("services_breakdown", handle_services_breakdown)
    graph.add_node("customer_metrics", handle_customer_metrics)
    graph.add_node("export", handle_export_report)
    graph.add_node("other", handle_other)
    
    # Edges
    graph.add_conditional_edges(
        "classify",
        lambda state: finance_intent_classifier(state),
        {
            "daily_revenue": "daily_revenue",
            "weekly_summary": "weekly_summary",
            "trend_summary": "trend_summary",
            "services_breakdown": "services_breakdown",
            "customer_metrics": "customer_metrics",
            "export": "export",
            "other": "other"
        }
    )
    
    # All handlers end
    for node in ["daily_revenue", "weekly_summary", "trend_summary", "services_breakdown", "customer_metrics", "export", "other"]:
        graph.add_edge(node, END)
    
    # Entry point
    graph.set_entry_point("classify")
    
    return graph


def create_finance_runnable():
    """Compile the Finance graph into an executable runnable."""
    graph = build_finance_graph()
    return graph.compile()


__all__ = [
    "build_finance_graph",
    "create_finance_runnable"
]
