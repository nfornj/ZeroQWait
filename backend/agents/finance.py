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

from typing import Any, Dict, List, Optional
import difflib
import json as _json
import os
import re
from datetime import datetime, timedelta

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END

from .state import AgentState
from .tools import finance_tools


TIMEFRAME_HINTS = [
    "today", "yesterday", "day", "daily", "week", "weekly", "month", "monthly",
    "quarter", "year", "yearly", "last", "this", "trend", "30 days", "7 days",
    "jan", "january", "feb", "february", "mar", "march", "apr", "april", "may",
    "jun", "june", "jul", "july", "aug", "august", "sep", "sept", "september",
    "oct", "october", "nov", "november", "dec", "december",
]

FINANCE_HINTS = [
    "revenue", "sales", "income", "profit", "finance", "financial", "analytics", "transaction",
]

NORMALIZATION_KEYWORDS = sorted(
    set(
        TIMEFRAME_HINTS
        + FINANCE_HINTS
        + [
            "export", "download", "csv", "excel", "report", "file",
            "each", "every", "all", "date", "day", "dates", "days",
            "largest", "highest", "maximum", "max", "best", "peak",
            "when", "which", "what", "tell", "past", "year", "month", "week",
        ]
    ),
    key=len,
    reverse=True,
)


def _tokenize_text(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _best_fuzzy_keyword(token: str) -> str:
    if not token:
        return token
    if token in NORMALIZATION_KEYWORDS:
        return token

    best_keyword = token
    best_ratio = 0.0
    for keyword in NORMALIZATION_KEYWORDS:
        if abs(len(token) - len(keyword)) > 2:
            continue
        ratio = difflib.SequenceMatcher(a=token, b=keyword).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_keyword = keyword

    if best_ratio >= 0.82:
        return best_keyword
    return token


def _normalize_for_matching(text: str) -> str:
    tokens = _tokenize_text(text)
    normalized = [_best_fuzzy_keyword(token) for token in tokens]
    return " ".join(normalized)


def _latest_user_text(state: AgentState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return ""
    latest = messages[-1]
    return str(latest.content) if isinstance(latest, BaseMessage) else str(latest)


def _has_time_or_finance_hints(text: str) -> bool:
    normalized = _normalize_for_matching(text)
    return any(token in normalized for token in TIMEFRAME_HINTS + FINANCE_HINTS)


def _is_followup_transform_request(text: str) -> bool:
    normalized = _normalize_for_matching(text)
    return any(token in normalized for token in [
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


def _wants_day_by_day_output(text: str) -> bool:
    normalized = _normalize_for_matching(text)
    return any(token in normalized for token in [
        "for each day",
        "each day",
        "for each date",
        "each date",
        "every date",
        "all dates",
        "date wise",
        "date-wise",
        "all 30 days",
        "every day",
        "day by day",
        "per day",
        "daily breakdown",
    ])


def _requested_specific_date(state: AgentState) -> Optional[str]:
    query = _resolve_finance_query(state)
    return finance_tools.extract_requested_date(query)


def _requested_week_start(state: AgentState) -> tuple[Optional[str], str]:
    """Resolve weekly window from query text; defaults to current week."""
    query = _resolve_finance_query(state)
    normalized = _normalize_for_matching(query)
    now = datetime.now()
    this_week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)

    if any(token in normalized for token in ["last week", "previous week"]):
        last_week_start = this_week_start - timedelta(days=7)
        return last_week_start.strftime("%Y-%m-%d"), "last week"

    if any(token in normalized for token in ["this week", "weekly", "week"]):
        return this_week_start.strftime("%Y-%m-%d"), "this week"

    return None, "this week"


def _ollama_base_url() -> str:
    base_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1").rstrip("/")
    if base_url.endswith("/v1"):
        return base_url[:-3]
    return base_url


def _llm_plan_finance_intent(query: str, today_str: str) -> dict:
    """
    Ask the LLM to parse the user's message and return a structured finance intent plan.

    Returns a dict with keys: intent, time_window, date, week_start, confidence.
    Returns {} on any LLM or parse failure (callers fall back to heuristics).
    """
    ollama_url = _ollama_base_url()
    model_name = os.getenv("MODEL_NAME", "gpt-oss:20b")
    llm = ChatOllama(model=model_name, base_url=ollama_url, temperature=0.0, format="json")

    system_prompt = (
        f"You are a finance query analyzer for a shop management system. Today is {today_str}.\n"
        "Analyze the user message and return ONLY this JSON (no explanation, no markdown):\n"
        '{\n'
        '  "intent": "<daily_revenue|weekly_summary|trend_summary|services_breakdown|customer_metrics|export|other>",\n'
        '  "time_window": "<today|yesterday|this_week|last_week|this_month|last_month|this_year|last_year|custom|null>",\n'
        '  "date": "<YYYY-MM-DD for a specific single-day query, otherwise null>",\n'
        '  "week_start": "<YYYY-MM-DD Monday of the target week for weekly queries, otherwise null>",\n'
        '  "confidence": <0.0 to 1.0>\n'
        '}\n\n'
        "Intent rules:\n"
        "- daily_revenue: single day revenue (today, yesterday, a specific date)\n"
        "- weekly_summary: total/summary for a full week period\n"
        "- trend_summary: trends, day-by-day, best day, peak revenue, monthly/yearly overview, forecasts\n"
        "- services_breakdown: which services generate the most revenue\n"
        "- customer_metrics: customer counts, repeat visits, lifetime value\n"
        "- export: export/download/CSV/PDF/report file\n"
        "- other: unclear or general\n\n"
        f"Date computation rules (today = {today_str}):\n"
        "- 'yesterday' → date = yesterday in YYYY-MM-DD\n"
        "- 'last week' / 'previous week' → week_start = Monday of the week before the current week\n"
        "- 'this week' / 'current week' → week_start = Monday of the current week\n"
        "- Named dates like 'April 10' → compute the closest past occurrence as YYYY-MM-DD\n"
        "- 'last 7 days', 'past 7 days' → time_window = custom, intent = trend_summary\n"
    )

    try:
        result = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ])
        raw = result.content if hasattr(result, "content") else str(result)
        if isinstance(raw, list):
            raw = " ".join(str(chunk) for chunk in raw)
        raw = str(raw)
        # Strip any accidental markdown fences
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
        plan = _json.loads(raw)
        if "intent" not in plan:
            return {}
        plan["confidence"] = float(plan.get("confidence", 0.5))
        return plan
    except Exception:
        return {}


def _asks_for_peak_revenue_period(text: str) -> bool:
    normalized = _normalize_for_matching(text)
    has_revenue = any(token in normalized for token in ["revenue", "sales", "income", "profit"])
    has_peak = any(token in normalized for token in ["largest", "highest", "max", "maximum", "best", "peak"])
    asks_for_period = any(token in normalized for token in [
        "when", "which day", "what day", "which date", "what date", "date", "day", "tell me",
    ])
    asks_for_window = any(token in normalized for token in [
        "this month", "last month", "this week", "last week", "this year", "last year", "quarter", "period",
        "month", "week", "year",
    ])
    return has_revenue and has_peak and (asks_for_period or asks_for_window)


def _wants_concise_period_summary(text: str) -> bool:
    normalized = _normalize_for_matching(text)
    asks_total_revenue = any(token in normalized for token in [
        "total revenue", "revenue", "sales", "income", "profit",
    ])
    asks_period = any(token in normalized for token in [
        "last", "past", "previous", "this", "month", "months", "year", "week", "quarter",
        "january", "february", "march", "april", "may", "june", "july", "august",
        "september", "october", "november", "december",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
    ])
    wants_detail = any(token in normalized for token in [
        "trend", "points", "breakdown", "day by day", "each day", "per day", "forecast", "chart",
    ])
    return asks_total_revenue and asks_period and not wants_detail


def _format_window_label(result: dict) -> str:
    window = str(result.get("window", "custom"))
    range_start = result.get("range_start")

    if window.startswith("month_") and range_start:
        try:
            return datetime.strptime(str(range_start), "%Y-%m-%d").strftime("%B %Y")
        except ValueError:
            return window.replace("_", " ")

    match = re.match(r"last_(\d+)_months", window)
    if match:
        return f"the last {int(match.group(1))} months"

    friendly = {
        "this_week": "this week",
        "last_week": "last week",
        "this_month": "this month",
        "last_month": "last month",
        "this_year": "this year",
        "last_year": "last year",
        "past_year": "the past year",
        "last_30_days": "the last 30 days",
        "specific_day": "that day",
    }
    return friendly.get(window, window.replace("_", " "))


def _points_to_csv(points: List[dict]) -> str:
    lines = ["period,revenue,customers,completed_services"]
    for p in points:
        lines.append(
            f"{p.get('period')},{float(p.get('revenue', 0.0)):.2f},{int(p.get('customers', 0))},{int(p.get('completed_services', 0))}"
        )
    return "\n".join(lines)


def _get_finance_writer_llm() -> ChatOllama:
    ollama_url = _ollama_base_url()
    model_name = os.getenv("MODEL_NAME", "gpt-oss:20b")
    return ChatOllama(
        model=model_name,
        base_url=ollama_url,
        temperature=0.2,
        top_p=0.9,
    )


def _prompt_facts_for_llm(result: Dict[str, Any]) -> Dict[str, Any]:
    facts = dict(result)
    points = facts.get("points")
    if isinstance(points, list) and len(points) > 12:
        facts["points_preview"] = points[:3] + points[-3:]
        facts["points_count"] = len(points)
        del facts["points"]
    return facts


def _generate_finance_response(
    state: AgentState,
    response_type: str,
    result: Dict[str, Any],
    *,
    extra_instructions: str = "",
) -> str:
    query = _latest_user_text(state)
    llm = _get_finance_writer_llm()
    prompt_facts = _prompt_facts_for_llm(result)
    wants_list = _wants_day_by_day_output(query) or any(
        token in query.lower()
        for token in ["list", "dates only", "date only", "revenue only", "breakdown", "top services", "csv", "export"]
    )
    style_rules = [
        "You are the finance manager for a shop owner.",
        "Write the final reply naturally, as if a person is answering from the business dashboard.",
        "Default to executive style: crisp, direct, and decision-ready.",
        "Use only the facts provided in the FACTS JSON. Never invent numbers, dates, trends, or causes.",
        "If information is missing, say that plainly instead of guessing.",
        "Answer the user's actual question first, in the first sentence.",
        "Do not mention internal field names, JSON, tools, routing, or shop_id unless the user asked for that.",
        "Do not use emojis.",
        "Do not use generic headings like 'Finance Trend' or 'Revenue Summary'.",
    ]
    if wants_list:
        style_rules.append("A list is allowed when the user asked for a list, breakdown, export, or date-by-date output.")
    else:
        style_rules.append("Prefer short prose over bullets unless bullets are clearly necessary.")
        style_rules.append("Target 2-4 sentences unless the user explicitly asks for full detail.")
    if extra_instructions:
        style_rules.append(extra_instructions)

    writer_prompt = (
        "\n".join(style_rules)
        + f"\n\nRESPONSE_TYPE: {response_type}"
        + f"\nUSER_QUESTION: {_json.dumps(query)}"
        + f"\nFACTS_JSON: {_json.dumps(prompt_facts, default=str)}"
        + "\n\nReturn only the owner-facing reply text."
    )

    try:
        response = llm.invoke([HumanMessage(content=writer_prompt)])
        content = response.content if hasattr(response, "content") else str(response)
        if isinstance(content, list):
            content = " ".join(str(chunk) for chunk in content)
        text = str(content).strip()
        text = re.sub(r"^```(?:text|markdown)?\s*", "", text).rstrip("`").strip()
        if text:
            return text
    except Exception:
        pass

    return "I have the finance data, but I couldn't turn it into a clean response right now."


def classify_entry(state: AgentState) -> dict:
    """
    LLM planning node — calls the LLM to produce a structured finance intent plan
    and stores it in tool_results['llm_plan'].  Handlers downstream read from this
    plan instead of re-parsing the query with heuristics.
    """
    query = _resolve_finance_query(state)
    today_str = datetime.now().strftime("%Y-%m-%d")
    plan = _llm_plan_finance_intent(query, today_str)
    existing = dict(state.get("tool_results") or {})
    existing["llm_plan"] = plan
    return {"tool_results": existing}


def _heuristic_intent_classifier(state: AgentState) -> str:
    """
    Keyword-based fallback classifier used when the LLM plan is missing or low-confidence.
    """
    
    messages = state.get("messages", [])
    if not messages:
        return "other"
    
    latest = messages[-1]
    if isinstance(latest, BaseMessage):
        content_raw = str(latest.content)
    else:
        content_raw = str(latest)
    content = _normalize_for_matching(content_raw)
    
    # Follow-up transform requests should preserve previous finance context.
    if _is_followup_transform_request(content):
        return "export"

    requested_date = finance_tools.extract_requested_date(content_raw)

    # Date-specific asks are usually a single-day revenue question.
    if requested_date and any(word in content for word in ["revenue", "sales", "income", "profit", "finance", "financial", "analytics"]):
        return "daily_revenue"

    # Keyword matching for Phase 2
    if any(word in content for word in ["today", "today's", "daily"]):
        return "daily_revenue"
    elif any(word in content for word in ["trend", "forecast"]):
        return "trend_summary"
    elif any(word in content for word in ["week", "weekly"]):
        return "weekly_summary"
    elif any(word in content for word in ["month", "monthly", "year", "yearly", "quarter"]):
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


def finance_route(state: AgentState) -> str:
    """
    Routing function for the classify conditional edge.

    Uses the LLM plan stored by classify_entry if present and confident (>= 0.5).
    Falls back to the heuristic classifier when the plan is absent or low-confidence.
    """
    plan = (state.get("tool_results") or {}).get("llm_plan", {})
    intent = plan.get("intent", "")
    confidence = float(plan.get("confidence", 0.0))

    valid_intents = {
        "daily_revenue", "weekly_summary", "trend_summary",
        "services_breakdown", "customer_metrics", "export", "other",
    }

    if intent in valid_intents and confidence >= 0.5:
        return intent

    # LLM was unavailable, returned garbage, or was not confident — fall back.
    return _heuristic_intent_classifier(state)


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

    query_lower = query.lower()
    if _asks_for_peak_revenue_period(query_lower):
        response = AIMessage(
            content=_generate_finance_response(
                state,
                "trend_peak_period",
                result,
                extra_instructions=(
                    "The user wants the strongest revenue period in the requested window. "
                    "State that period and the corresponding revenue directly."
                ),
            )
        )
        return {
            "messages": list(state["messages"]) + [response],
            "tool_results": result,
        }

    if _wants_concise_period_summary(query_lower):
        response = AIMessage(
            content=_generate_finance_response(
                state,
                "trend_concise_period_summary",
                result,
                extra_instructions=(
                    "The user wants a direct period summary. "
                    "Include the date range and total revenue in the first sentence. "
                    "Then mention only the most relevant supporting facts, usually completed services, average ticket, and strongest period."
                ),
            )
        )
        return {
            "messages": list(state["messages"]) + [response],
            "tool_results": result,
        }

    response = AIMessage(
        content=_generate_finance_response(
            state,
            "trend_detailed",
            result,
            extra_instructions=(
                "Summarize the requested trend in a natural way. "
                "If the user asked for daily or date-by-date detail, include a compact list based on the provided points. "
                "Otherwise keep it concise and mention the strongest period and any notable directional pattern only if it is directly supported by the facts."
            ),
        )
    )

    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result,
    }


def handle_daily_revenue(state: AgentState) -> dict:
    """Get revenue summary for a requested date (defaults to today)."""

    shop_id = state["tenant_id"]
    # Prefer LLM-resolved date; fall back to heuristic extractor.
    plan = (state.get("tool_results") or {}).get("llm_plan", {})
    requested_date = plan.get("date") or _requested_specific_date(state)
    result = finance_tools.daily_revenue(shop_id, date=requested_date)
    if result.get("error"):
        response = AIMessage(content=f"I couldn't load the revenue summary: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=_generate_finance_response(
            state,
            "daily_revenue",
            result,
            extra_instructions=(
                "Answer as a single-day revenue summary. "
                "Include the target date and the revenue in the first sentence."
            ),
        )
    )
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result
    }


def handle_weekly_summary(state: AgentState) -> dict:
    """Get weekly revenue and metrics."""

    shop_id = state["tenant_id"]
    # Prefer LLM-resolved week_start and time_window label.
    plan = (state.get("tool_results") or {}).get("llm_plan", {})
    week_start = plan.get("week_start")
    week_label = (plan.get("time_window") or "this_week").replace("_", " ")
    if not week_start:
        # LLM plan absent or unusable — fall back to heuristic.
        week_start, week_label = _requested_week_start(state)
    result = finance_tools.weekly_summary(shop_id, week_start=week_start)
    if result.get("error"):
        response = AIMessage(content=f"I couldn't load the {week_label} summary: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    weekly_result = {**result, "week_label": week_label}
    response = AIMessage(
        content=_generate_finance_response(
            state,
            "weekly_summary",
            weekly_result,
            extra_instructions=(
                "Answer as a weekly business summary. "
                "Mention the week label, total revenue, and best day if available."
            ),
        )
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

    response = AIMessage(
        content=_generate_finance_response(
            state,
            "services_breakdown",
            result,
            extra_instructions=(
                "The user wants service-level revenue contribution. "
                "If service rows are available, name the strongest services in ranked order. "
                "If no services are available, say that plainly."
            ),
        )
    )
    
    return {
        "messages": list(state["messages"]) + [response],
        "tool_results": result
    }


def handle_customer_metrics(state: AgentState) -> dict:
    """Get customer analytics."""
    
    shop_id = state["tenant_id"]
    query = _resolve_finance_query(state)
    result = finance_tools.customer_metrics(shop_id, query=query)
    if result.get("error"):
        response = AIMessage(content=f"I couldn't load customer metrics: {result['error']}")
        return {"messages": list(state["messages"]) + [response], "tool_results": result}

    response = AIMessage(
        content=_generate_finance_response(
            state,
            "customer_metrics",
            result,
            extra_instructions=(
                "Summarize customer metrics naturally. "
                "Mention total customers, repeat customers or repeat rate, and average LTV when available."
                "If profile_signal_limited is true, do not infer new vs repeat behavior; state that repeat/new split is unavailable from profile data."
            ),
        )
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
        transformed = {**trend, "transform": "dates_only", "values": dates}
        response = AIMessage(
            content=_generate_finance_response(
                state,
                "export_dates_only",
                transformed,
                extra_instructions="Return the dates as a clean list, with no extra commentary beyond a brief lead-in.",
            )
        )
        return {
            "messages": list(state["messages"]) + [response],
            "tool_results": transformed,
        }

    if any(token in current_text for token in ["revenue only", "only revenue", "just revenue"]):
        transformed = {**trend, "transform": "revenue_only"}
        response = AIMessage(
            content=_generate_finance_response(
                state,
                "export_revenue_only",
                transformed,
                extra_instructions="Return the period-by-period revenue values as a clean list, with no extra commentary beyond a brief lead-in.",
            )
        )
        return {
            "messages": list(state["messages"]) + [response],
            "tool_results": transformed,
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
        content=_generate_finance_response(
            state,
            "export_csv",
            result,
            extra_instructions=(
                "Explain that a CSV-style export is prepared, include filename, row count, and date range, "
                "and briefly preview the contents if useful."
            ),
        )
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
    
    # Edges — conditional routing uses finance_route() which reads from the LLM plan
    graph.add_conditional_edges(
        "classify",
        lambda state: finance_route(state),
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
