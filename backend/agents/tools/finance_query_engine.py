"""Guarded dynamic SQL query engine for finance read questions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import json
import logging
import os
import re
import time
from typing import Any, Dict, Iterable, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from database import DATABASE_URL, SessionLocal
from agents.llm_factory import create_formatter_model, create_planner_model

logger = logging.getLogger(__name__)

MAX_ROWS = int(os.getenv("FINANCE_QUERY_MAX_ROWS", "100"))
STATEMENT_TIMEOUT_MS = int(os.getenv("FINANCE_QUERY_STATEMENT_TIMEOUT_MS", "5000"))
MAX_RETRIES = int(os.getenv("FINANCE_QUERY_MAX_RETRIES", "2"))
LLM_TIMEOUT_SECONDS = float(os.getenv("FINANCE_QUERY_LLM_TIMEOUT_SECONDS", "300"))

AI_DATABASE_URL = os.getenv("AI_DATABASE_URL") or os.getenv("FINANCE_AI_DATABASE_URL")

ALLOWED_VIEWS: frozenset[str] = frozenset(
    {
        "ai_daily_analytics",
        "ai_services",
        "ai_queue_visits",
        "ai_customers",
        "ai_appointments",
        "ai_invoices",
        "ai_invoice_line_items",
        "ai_payments",
        "ai_employees",
    }
)

DISALLOWED_KEYWORDS: frozenset[str] = frozenset(
    {
        "alter",
        "call",
        "copy",
        "create",
        "delete",
        "do",
        "drop",
        "execute",
        "grant",
        "insert",
        "merge",
        "reset",
        "revoke",
        "set",
        "truncate",
        "update",
        "vacuum",
    }
)

SCHEMA_CONTEXT = """\
You can answer finance and operations read questions with PostgreSQL SQL.
Use only these tenant-scoped views. They already filter to the current shop:

ai_daily_analytics(business_date, total_customers, completed_services, cancelled_services, total_revenue, avg_wait_time_minutes, avg_service_time_minutes, peak_hour_start, peak_hour_customers)
ai_services(service_id, name, duration_minutes, cost, currency, is_active, created_at)
ai_queue_visits(visit_id, queue_id, service_id, service_name, status, position, checked_in_at, service_started_at, completed_at, service_cost, assigned_employee_id)
ai_customers(customer_id, name, visit_count, last_visit, created_at)
ai_appointments(appointment_id, customer_id, service_id, service_name, employee_id, customer_name, scheduled_start, scheduled_end, actual_start, actual_end, status, service_cost, cancelled_at, created_at)
ai_invoices(invoice_id, customer_id, invoice_number, status, subtotal, tax_amount, discount_amount, tip_amount, total, currency, due_date, paid_at, created_at, updated_at)
ai_invoice_line_items(line_item_id, invoice_id, service_id, queue_item_id, appointment_id, description, quantity, unit_price, total, created_at)
ai_payments(payment_id, invoice_id, customer_id, amount, tip_amount, currency, method, status, processed_by, processed_at, refunded_at, refund_amount, created_at, updated_at)
ai_employees(employee_id, user_id, username, role, is_active, joined_at)

Rules:
- Return exactly one SELECT query.
- Do not use raw tables.
- Do not include INSERT, UPDATE, DELETE, DDL, SET, comments, or multiple statements.
- Prefer current_date for relative dates such as today.
- For live/today revenue or simulator-backed questions, prefer ai_queue_visits with completed_at/check-in time and service_cost; ai_daily_analytics may lag and can be empty for today.
- For top services by revenue or customer count, prefer grouping ai_queue_visits by service_id/service_name instead of invoice line items unless the user specifically asks about invoices.
- Queue visit status values are normalized to lowercase strings such as 'completed', 'waiting', and 'cancelled'.
- For cancelled vs completed counts in ai_appointments, use: SELECT status, COUNT(*) AS count FROM ai_appointments WHERE scheduled_start >= <date> GROUP BY status. Never use 'completed' or 'cancelled' as column names — they are VALUES of the 'status' column.
- For employee questions (who handled most visits, top performers, etc.), JOIN ai_queue_visits.assigned_employee_id = ai_employees.employee_id to get the employee username.
- ai_daily_analytics does NOT have a service_id column. Never JOIN ai_daily_analytics on service_id. For average wait time per service type, query ai_queue_visits DIRECTLY without a subquery: SELECT service_name, AVG(EXTRACT(EPOCH FROM (service_started_at - checked_in_at)) / 60) AS avg_wait_time_minutes FROM ai_queue_visits WHERE service_started_at IS NOT NULL AND checked_in_at IS NOT NULL GROUP BY service_name ORDER BY avg_wait_time_minutes DESC. Do NOT wrap this in a subquery.
- business_date only exists in ai_daily_analytics. For day-of-week analysis on queue visits, use EXTRACT(DOW FROM completed_at) from ai_queue_visits, not ai_daily_analytics.business_date.
- For percentage or ratio calculations always wrap the denominator in NULLIF(expr, 0) to avoid division by zero.
- Add LIMIT when returning detail rows.
- ai_queue_visits has NO customer_id column. Never reference customer_id on ai_queue_visits. To count customers who visited in a period, use: SELECT COUNT(*) FROM ai_customers WHERE last_visit >= <date>. Do not JOIN ai_queue_visits to ai_customers.
- For the highest-spending customer or top customers by invoice total: SELECT customer_id, SUM(total) AS invoice_total FROM ai_invoices GROUP BY customer_id ORDER BY invoice_total DESC LIMIT 1.
- When using a subquery alias, only reference column names that are explicitly listed in the subquery SELECT clause. Never reference outer-table aliases inside an aggregate that lives outside the subquery.
- To link ai_payments to ai_queue_visits, join through ai_invoice_line_items: ai_payments.invoice_id = ai_invoice_line_items.invoice_id AND ai_invoice_line_items.queue_item_id = ai_queue_visits.visit_id. ai_payments has NO line_item_id column and ai_queue_visits has NO line_item_id column — never join them directly on line_item_id.
- For payment conversion rate (queue visits that became paid), use: SELECT COUNT(DISTINCT ili.queue_item_id) * 100.0 / NULLIF(COUNT(DISTINCT v.visit_id), 0) AS pct FROM ai_queue_visits v LEFT JOIN ai_invoice_line_items ili ON ili.queue_item_id = v.visit_id LEFT JOIN ai_payments p ON p.invoice_id = ili.invoice_id AND p.status = 'completed' WHERE v.checked_in_at >= <date>.
- For average revenue per visit broken down by service, use service_cost from ai_queue_visits directly without nesting aggregates: SELECT service_name, AVG(service_cost) AS avg_revenue_per_visit, COUNT(*) AS visit_count FROM ai_queue_visits WHERE service_cost IS NOT NULL GROUP BY service_name ORDER BY avg_revenue_per_visit DESC. Never nest aggregate functions like AVG(SUM(...)) — PostgreSQL does not allow nested aggregates.
"""


_RAW_SQL_RE = re.compile(
    r"^\s*(select|update|delete|insert|drop|alter|create|truncate|grant|revoke|with)\s",
    re.IGNORECASE,
)


def _is_raw_sql_input(question: str) -> bool:
    """Return True if the user input is itself a raw SQL statement, not a natural-language question."""
    return bool(_RAW_SQL_RE.match(question.strip()))


class SQLPlan(BaseModel):
    sql: str = Field(description="A single PostgreSQL SELECT query over the allowed AI views.")
    rationale: str = Field(default="", description="Short reason for the query.")


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    error: Optional[str] = None


_engine: Optional[Engine] = None
_llm_executor = ThreadPoolExecutor(max_workers=int(os.getenv("FINANCE_QUERY_LLM_WORKERS", "4")))


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(AI_DATABASE_URL or DATABASE_URL, pool_pre_ping=True)
    return _engine


def _with_timeout(label: str, func):
    future = _llm_executor.submit(func)
    try:
        return future.result(timeout=LLM_TIMEOUT_SECONDS)
    except FutureTimeoutError as exc:
        raise TimeoutError(f"{label} timed out after {LLM_TIMEOUT_SECONDS:.1f}s") from exc


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql or "", flags=re.DOTALL)
    sql = re.sub(r"--[^\n\r]*", " ", sql)
    return sql.strip()


def _statement_count(sql: str) -> int:
    return len([part for part in sql.split(";") if part.strip()])


def _normalized_table_name(raw: str) -> str:
    value = raw.strip().strip('"').lower()
    if "." in value:
        value = value.split(".")[-1].strip('"')
    return value


def _referenced_tables(sql: str) -> set[str]:
    # Mask EXTRACT(... FROM ...) so the FROM inside EXTRACT is not treated as a table reference.
    masked = re.sub(r"\bEXTRACT\s*\([^)]+\)", "__EXTRACT__", sql, flags=re.IGNORECASE)
    refs: set[str] = set()
    for match in re.finditer(
        r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)",
        masked,
        flags=re.IGNORECASE,
    ):
        refs.add(_normalized_table_name(match.group(1)))
    return refs


def _cte_names(sql: str) -> set[str]:
    if not re.match(r"^\s*with\b", sql, flags=re.IGNORECASE):
        return set()
    return {
        match.group(1).strip().lower()
        for match in re.finditer(r"(?:with|,)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+as\s*\(", sql, flags=re.IGNORECASE)
    }


def validate_sql(sql: str) -> ValidationResult:
    cleaned = _strip_sql_comments(sql)
    if not cleaned:
        return ValidationResult(False, "SQL is empty")

    if _statement_count(cleaned) != 1:
        return ValidationResult(False, "SQL must be a single statement")

    cleaned_no_semicolon = cleaned[:-1].strip() if cleaned.endswith(";") else cleaned
    if not re.match(r"^(select|with)\b", cleaned_no_semicolon, flags=re.IGNORECASE):
        return ValidationResult(False, "SQL must start with SELECT or WITH")

    tokens = {token.lower() for token in re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", cleaned_no_semicolon)}
    blocked = sorted(tokens.intersection(DISALLOWED_KEYWORDS))
    if blocked:
        return ValidationResult(False, f"SQL contains disallowed keyword: {blocked[0]}")

    refs = _referenced_tables(cleaned_no_semicolon)
    if not refs:
        return ValidationResult(False, "SQL must read from at least one AI view")

    allowed_refs = set(ALLOWED_VIEWS) | _cte_names(cleaned_no_semicolon)
    disallowed_refs = sorted(ref for ref in refs if ref not in allowed_refs)
    if disallowed_refs:
        return ValidationResult(False, f"SQL references a non-allowlisted relation: {disallowed_refs[0]}")

    return ValidationResult(True)


def _contextual_sql_error(sql: str, question: str) -> Optional[str]:
    normalized_question = " ".join(str(question or "").lower().split())
    normalized_sql = str(sql or "").lower()

    if re.search(r"\b(?:today|today's|todays)\b", normalized_question) and "current_date" in normalized_sql:
        return (
            "Do not use CURRENT_DATE for today because the database timezone may differ from the shop timezone. "
            "Use the shop-local UTC timestamp bounds provided in the prompt."
        )

    return None


def _limit_sql(sql: str) -> str:
    cleaned = _strip_sql_comments(sql)
    cleaned = cleaned[:-1].strip() if cleaned.endswith(";") else cleaned
    if re.search(r"\blimit\s+\d+\b", cleaned, flags=re.IGNORECASE):
        return cleaned
    return f"SELECT * FROM ({cleaned}) AS ai_limited_result LIMIT {MAX_ROWS}"


def _rows_to_dicts(rows: Iterable[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        mapping = dict(row._mapping)
        result.append(
            {
                key: (value.isoformat() if hasattr(value, "isoformat") else value)
                for key, value in mapping.items()
            }
        )
    return result


def _log_query(
    *,
    shop_id: int,
    question: str,
    generated_sql: Optional[str],
    validation_status: str,
    execution_status: str,
    latency_ms: int,
    row_count: int = 0,
    error_class: Optional[str] = None,
    error_message: Optional[str] = None,
    mode: str = "enabled",
    fallback_used: bool = False,
) -> None:
    try:
        with _get_engine().begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO ai_query_logs (
                        shop_id, question, generated_sql, validation_status, execution_status,
                        error_class, error_message, row_count, latency_ms, mode, fallback_used
                    )
                    VALUES (
                        :shop_id, :question, :generated_sql, :validation_status, :execution_status,
                        :error_class, :error_message, :row_count, :latency_ms, :mode, :fallback_used
                    )
                    """
                ),
                {
                    "shop_id": shop_id,
                    "question": question,
                    "generated_sql": generated_sql,
                    "validation_status": validation_status,
                    "execution_status": execution_status,
                    "error_class": error_class,
                    "error_message": (error_message or "")[:2000] or None,
                    "row_count": row_count,
                    "latency_ms": latency_ms,
                    "mode": mode,
                    "fallback_used": fallback_used,
                },
            )
    except Exception as exc:
        logger.warning("AI query log insert failed for shop %s: %s", shop_id, exc)


def _generate_sql(shop_id: int, question: str, previous_error: Optional[str] = None) -> SQLPlan:
    today_hint = ""
    try:
        from agents.tools import finance_tools

        session = SessionLocal()
        try:
            shop_now = finance_tools._now_for_shop(shop_id, session)
            tz_name = finance_tools._resolve_shop_timezone_name(shop_id, session)
            start_utc, end_utc = finance_tools._shop_local_day_bounds_utc(shop_now.date(), tz_name)
            today_hint = (
                f"Shop local today is {shop_now.strftime('%Y-%m-%d')} in timezone {tz_name}. "
                "For questions about today, filter completed_at or checked_in_at with "
                f">= TIMESTAMP '{start_utc.strftime('%Y-%m-%d %H:%M:%S')}' "
                f"and < TIMESTAMP '{end_utc.strftime('%Y-%m-%d %H:%M:%S')}' instead of CURRENT_DATE.\n"
            )
        finally:
            session.close()
    except Exception as exc:
        logger.debug("Could not build shop-local SQL date hint for shop %s: %s", shop_id, exc)

    prompt = (
        f"{SCHEMA_CONTEXT}\n"
        f"Today is {datetime.now().strftime('%Y-%m-%d')}.\n"
        f"{today_hint}"
        f"Question: {question}\n"
    )
    if previous_error:
        prompt += f"The previous SQL failed with this error: {previous_error}\nRewrite the SQL to fix it.\n"

    llm = create_planner_model(shop_id, temperature=0.0)
    decision = _with_timeout(
        "Finance SQL generation",
        lambda: llm.with_structured_output(SQLPlan).invoke(
            [
                SystemMessage(content="/no_think Generate safe read-only SQL for ZeroQwait finance analytics."),
                HumanMessage(content=prompt),
            ]
        ),
    )
    return SQLPlan.model_validate(decision)


def _execute_sql(shop_id: int, sql: str) -> list[dict[str, Any]]:
    limited_sql = _limit_sql(sql)
    with _get_engine().begin() as conn:
        conn.execute(text("SET LOCAL TRANSACTION READ ONLY"))
        conn.execute(text("SELECT set_config('statement_timeout', :timeout_ms, true)"), {"timeout_ms": str(STATEMENT_TIMEOUT_MS)})
        conn.execute(text("SELECT set_config('app.current_shop_id', :shop_id, true)"), {"shop_id": str(shop_id)})
        rows = conn.execute(text(limited_sql)).fetchmany(MAX_ROWS)
    return _rows_to_dicts(rows)


def _format_rows_as_answer(question: str, rows: list[dict[str, Any]]) -> str:
    """Template-based fallback when LLM answer synthesis is unavailable."""
    if not rows:
        return "I could not find matching finance data for that question."
    row = rows[0]
    keys = list(row.keys())
    # Single-column single-row result (COUNT, SUM, etc.)
    if len(rows) == 1 and len(keys) == 1:
        val = row[keys[0]]
        col = keys[0].lower()
        if col in ("count", "count(*)") or col.startswith("count"):
            return f"The count for your query was {val}."
        if col in ("sum", "total", "revenue", "total_revenue") or col.startswith("sum"):
            try:
                return f"The total was ${float(val):,.2f}."
            except (TypeError, ValueError):
                pass
        return f"The result was: {val}."
    # Multi-row or multi-column: list up to 5 rows
    lines = [f"Here are the results for your query:"]
    for r in rows[:5]:
        lines.append("  " + ", ".join(f"{k}: {v}" for k, v in r.items()))
    if len(rows) > 5:
        lines.append(f"  ... and {len(rows) - 5} more rows.")
    return "\n".join(lines)


def _synthesize_answer(shop_id: int, question: str, sql: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "I could not find matching finance data for that question."

    llm = create_formatter_model(shop_id, temperature=0.2)
    prompt = (
        "Answer the shop owner's finance question using only these SQL results. "
        "Be concise, include numbers when present, and do not mention SQL unless the owner asks.\n\n"
        f"Question: {question}\n"
        f"SQL: {sql}\n"
        f"Rows JSON: {json.dumps(rows[:MAX_ROWS], default=str)}"
    )
    try:
        response = _with_timeout(
            "Finance SQL answer synthesis",
            lambda: llm.invoke([HumanMessage(content=prompt)]),
        )
        return str(getattr(response, "content", response)).strip() or "I found data, but could not summarize it cleanly."
    except TimeoutError:
        return _format_rows_as_answer(question, rows)


def answer_question(shop_id: int, question: str, *, mode: str = "enabled") -> Dict[str, Any]:
    started_at = time.perf_counter()
    generated_sql: Optional[str] = None
    previous_error: Optional[str] = None

    if _is_raw_sql_input(question):
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        _log_query(
            shop_id=shop_id,
            question=question,
            generated_sql=None,
            validation_status="rejected",
            execution_status="not_run",
            error_class="RawSQLInput",
            error_message="Direct SQL commands are not accepted",
            latency_ms=latency_ms,
            mode=mode,
            fallback_used=True,
        )
        return {
            "error": "Direct SQL commands are not accepted. Ask a natural language question.",
            "error_class": "RawSQLInput",
            "fallback_used": True,
            "shop_id": shop_id,
        }

    for attempt in range(MAX_RETRIES + 1):
        try:
            plan = _generate_sql(shop_id, question, previous_error=previous_error)
            generated_sql = plan.sql

            contextual_error = _contextual_sql_error(generated_sql, question)
            if contextual_error:
                previous_error = contextual_error
                if attempt < MAX_RETRIES:
                    continue

                latency_ms = int((time.perf_counter() - started_at) * 1000)
                _log_query(
                    shop_id=shop_id,
                    question=question,
                    generated_sql=generated_sql,
                    validation_status="rejected",
                    execution_status="not_run",
                    error_class="ValidationError",
                    error_message=contextual_error,
                    latency_ms=latency_ms,
                    mode=mode,
                    fallback_used=True,
                )
                return {
                    "error": contextual_error,
                    "error_class": "ValidationError",
                    "generated_sql": generated_sql,
                    "fallback_used": True,
                    "shop_id": shop_id,
                }

            validation = validate_sql(generated_sql)
            if not validation.ok:
                latency_ms = int((time.perf_counter() - started_at) * 1000)
                _log_query(
                    shop_id=shop_id,
                    question=question,
                    generated_sql=generated_sql,
                    validation_status="rejected",
                    execution_status="not_run",
                    error_class="ValidationError",
                    error_message=validation.error,
                    latency_ms=latency_ms,
                    mode=mode,
                    fallback_used=True,
                )
                return {
                    "error": validation.error,
                    "error_class": "ValidationError",
                    "generated_sql": generated_sql,
                    "fallback_used": True,
                    "shop_id": shop_id,
                }

            rows = _execute_sql(shop_id, generated_sql)
            answer = _synthesize_answer(shop_id, question, generated_sql, rows)
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            _log_query(
                shop_id=shop_id,
                question=question,
                generated_sql=generated_sql,
                validation_status="accepted",
                execution_status="succeeded",
                row_count=len(rows),
                latency_ms=latency_ms,
                mode=mode,
            )
            return {
                "answer": answer,
                "rows": rows,
                "row_count": len(rows),
                "generated_sql": generated_sql,
                "source": "dynamic_sql",
                "fallback_used": False,
                "shop_id": shop_id,
            }
        except SQLAlchemyError as exc:
            previous_error = str(exc)
            if attempt < MAX_RETRIES:
                continue
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            _log_query(
                shop_id=shop_id,
                question=question,
                generated_sql=generated_sql,
                validation_status="accepted" if generated_sql else "not_run",
                execution_status="failed",
                error_class=type(exc).__name__,
                error_message=str(exc),
                latency_ms=latency_ms,
                mode=mode,
                fallback_used=True,
            )
            return {
                "error": str(exc),
                "error_class": type(exc).__name__,
                "generated_sql": generated_sql,
                "fallback_used": True,
                "shop_id": shop_id,
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            _log_query(
                shop_id=shop_id,
                question=question,
                generated_sql=generated_sql,
                validation_status="not_run" if not generated_sql else "accepted",
                execution_status="failed",
                error_class=type(exc).__name__,
                error_message=str(exc),
                latency_ms=latency_ms,
                mode=mode,
                fallback_used=True,
            )
            return {
                "error": str(exc),
                "error_class": type(exc).__name__,
                "generated_sql": generated_sql,
                "fallback_used": True,
                "shop_id": shop_id,
            }

    return {"error": "Dynamic finance query failed", "fallback_used": True, "shop_id": shop_id}


__all__ = ["answer_question", "validate_sql", "ALLOWED_VIEWS", "DISALLOWED_KEYWORDS"]
