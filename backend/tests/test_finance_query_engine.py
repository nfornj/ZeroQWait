import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.tools import finance_query_engine
from agents.tools.finance_query_engine import SQLPlan, validate_sql


def test_validate_sql_accepts_select_from_ai_view():
    result = validate_sql("SELECT count(*) AS visits FROM ai_queue_visits WHERE status = 'completed'")

    assert result.ok


def test_validate_sql_accepts_cte_over_ai_view():
    result = validate_sql(
        """
        WITH paid AS (
            SELECT amount, method FROM ai_payments WHERE status = 'completed'
        )
        SELECT method, sum(amount) AS total FROM paid GROUP BY method
        """
    )

    assert result.ok


def test_validate_sql_rejects_multiple_statements():
    result = validate_sql("SELECT * FROM ai_payments; SELECT * FROM ai_customers;")

    assert not result.ok
    assert "single statement" in result.error


def test_validate_sql_rejects_writes():
    result = validate_sql("DELETE FROM ai_payments WHERE payment_id = 1")

    assert not result.ok
    assert "SELECT or WITH" in result.error


def test_validate_sql_rejects_ddl_inside_select():
    result = validate_sql("SELECT * FROM ai_payments WHERE method = 'cash'; DROP TABLE payments;")

    assert not result.ok


def test_validate_sql_rejects_raw_tables():
    result = validate_sql("SELECT * FROM payments")

    assert not result.ok
    assert "non-allowlisted" in result.error


def test_validate_sql_rejects_sensitive_tables():
    result = validate_sql("SELECT id, email FROM users")

    assert not result.ok
    assert "non-allowlisted" in result.error


def test_today_questions_reject_current_date_contextually(monkeypatch):
    monkeypatch.setattr(finance_query_engine, "_log_query", lambda **kwargs: None)
    monkeypatch.setattr(
        finance_query_engine,
        "_generate_sql",
        lambda shop_id, question, previous_error=None: SQLPlan(
            sql="SELECT sum(service_cost) FROM ai_queue_visits WHERE completed_at >= CURRENT_DATE"
        ),
    )

    result = finance_query_engine.answer_question(502, "how much revenue today?")

    assert result["fallback_used"] is True
    assert result["error_class"] == "ValidationError"
    assert "CURRENT_DATE" in result["error"]


def test_ai_views_are_tenant_scoped_in_migration():
    migration = Path(__file__).resolve().parents[1] / "migrations" / "006_ai_finance_query_agent.sql"
    text = migration.read_text()

    assert "app.current_shop_id" in text
    for view_name in finance_query_engine.ALLOWED_VIEWS:
        assert f"VIEW {view_name}" in text


def test_answer_question_returns_validation_error_without_execution(monkeypatch):
    monkeypatch.setattr(finance_query_engine, "_log_query", lambda **kwargs: None)
    monkeypatch.setattr(
        finance_query_engine,
        "_generate_sql",
        lambda shop_id, question, previous_error=None: SQLPlan(sql="SELECT * FROM users"),
    )

    result = finance_query_engine.answer_question(502, "show all users")

    assert result["fallback_used"] is True
    assert result["error_class"] == "ValidationError"
    assert "non-allowlisted" in result["error"]


def test_answer_question_retries_sql_execution_errors(monkeypatch):
    calls = {"count": 0}

    monkeypatch.setattr(finance_query_engine, "_log_query", lambda **kwargs: None)
    monkeypatch.setattr(
        finance_query_engine,
        "_generate_sql",
        lambda shop_id, question, previous_error=None: SQLPlan(sql="SELECT count(*) FROM ai_payments"),
    )

    def fail_execute(shop_id, sql):
        calls["count"] += 1
        raise finance_query_engine.SQLAlchemyError("missing column")

    monkeypatch.setattr(finance_query_engine, "_execute_sql", fail_execute)

    result = finance_query_engine.answer_question(502, "payment count")

    assert result["fallback_used"] is True
    assert calls["count"] == finance_query_engine.MAX_RETRIES + 1
