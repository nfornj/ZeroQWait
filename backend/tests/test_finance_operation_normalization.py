import unittest

from langchain_core.messages import HumanMessage

from agents import finance
from agents.finance import _normalize_finance_operation


class TestFinanceOperationNormalization(unittest.TestCase):
    def test_review_revenue_prompt_normalizes_to_trend_summary(self) -> None:
        operation = _normalize_finance_operation(
            "analyze",
            {"rationale": "Review revenue performance"},
            [HumanMessage(content="Show this week's revenue trend and any operational concerns I should know about.")],
        )

        self.assertEqual(operation, "trend_summary")

    def test_specific_date_analysis_normalizes_to_daily_revenue(self) -> None:
        operation = _normalize_finance_operation(
            "summarize",
            {"rationale": "Single-day revenue question"},
            [HumanMessage(content="Analyze revenue for 2026-04-01")],
        )

        self.assertEqual(operation, "daily_revenue")

    def test_customer_prompt_normalizes_to_customer_metrics(self) -> None:
        operation = _normalize_finance_operation(
            "answer",
            {"rationale": "Customer retention question"},
            [HumanMessage(content="Can you review our customer repeat rate this month?")],
        )

        self.assertEqual(operation, "customer_metrics")

    def test_service_customer_count_prompt_normalizes_to_service_customer_counts(self) -> None:
        operation = _normalize_finance_operation(
            "answer",
            {"rationale": "Customer count by service"},
            [HumanMessage(content="Can you show me number of customers attended for each services?")],
        )

        self.assertEqual(operation, "service_customer_counts")

    def test_revenue_trend_analysis_normalizes_to_trend_summary(self) -> None:
        operation = _normalize_finance_operation(
            "revenue_trend_analysis",
            {"rationale": "Revenue trend request"},
            [HumanMessage(content="Show this week's revenue trend and any operational concerns I should know about.")],
        )

        self.assertEqual(operation, "trend_summary")

    def test_customer_metrics_with_revenue_prompt_normalizes_to_trend_summary(self) -> None:
        operation = _normalize_finance_operation(
            "customer_metrics",
            {"rationale": "Weekly revenue request"},
            [HumanMessage(content="Show this week's revenue trend and any operational concerns I should know about.")],
        )

        self.assertEqual(operation, "trend_summary")

    def test_customer_metrics_with_customer_noise_still_normalizes_to_trend_summary(self) -> None:
        operation = _normalize_finance_operation(
            "customer_metrics",
            {"rationale": "Customer metrics and shop context"},
            [
                HumanMessage(content="How is customer retention looking this month?"),
                HumanMessage(content="Show this week's revenue trend and any operational concerns I should know about."),
            ],
        )

        self.assertEqual(operation, "trend_summary")

    def test_last_n_days_prompt_overrides_daily_revenue_to_trend_summary(self) -> None:
        operation = _normalize_finance_operation(
            "daily_revenue",
            {"rationale": "Revenue range request"},
            [HumanMessage(content="Show revenue for the last 7 days")],
        )

        self.assertEqual(operation, "trend_summary")

    def test_dynamic_read_success_returns_dynamic_answer(self) -> None:
        original_mode = finance._DYNAMIC_READS_MODE
        original_answer = finance.finance_tools.answer_finance_question
        try:
            finance._DYNAMIC_READS_MODE = "enabled"
            finance.finance_tools.answer_finance_question = lambda *args, **kwargs: {
                "answer": "Today had 12 completed visits.",
                "generated_sql": "SELECT count(*) FROM ai_queue_visits",
                "row_count": 1,
            }

            result = finance._with_dynamic_read_fallback(
                502,
                "customer_metrics",
                "how many customers today?",
                lambda: {"total_customers": 0},
            )
        finally:
            finance._DYNAMIC_READS_MODE = original_mode
            finance.finance_tools.answer_finance_question = original_answer

        self.assertEqual(result["dynamic_sql_answer"], "Today had 12 completed visits.")
        self.assertFalse(result["fallback_used"])

    def test_dynamic_read_failure_uses_deterministic_fallback(self) -> None:
        original_mode = finance._DYNAMIC_READS_MODE
        original_answer = finance.finance_tools.answer_finance_question
        try:
            finance._DYNAMIC_READS_MODE = "enabled"
            finance.finance_tools.answer_finance_question = lambda *args, **kwargs: {
                "error": "SQL rejected",
                "error_class": "ValidationError",
            }

            result = finance._with_dynamic_read_fallback(
                502,
                "customer_metrics",
                "show all users",
                lambda: {"total_customers": 8},
            )
        finally:
            finance._DYNAMIC_READS_MODE = original_mode
            finance.finance_tools.answer_finance_question = original_answer

        self.assertEqual(result["total_customers"], 8)
        self.assertTrue(result["dynamic_sql_fallback_used"])
        self.assertEqual(result["dynamic_sql_error_class"], "ValidationError")

    def test_dynamic_read_local_mode_is_enabled(self) -> None:
        original_mode = finance._DYNAMIC_READS_MODE
        try:
            finance._DYNAMIC_READS_MODE = "local"
            self.assertTrue(finance._dynamic_reads_enabled())
        finally:
            finance._DYNAMIC_READS_MODE = original_mode


if __name__ == "__main__":
    unittest.main()
