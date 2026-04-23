import unittest

from langchain_core.messages import HumanMessage

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


if __name__ == "__main__":
    unittest.main()