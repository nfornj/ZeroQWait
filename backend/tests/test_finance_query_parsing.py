import os
import sys
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage

# Add backend directory to import path when executed directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import finance
from agents import supervisor
from agents.tools import finance_tools
from agents.state import AgentState


class TestFinanceQueryParsing(unittest.TestCase):
    def test_extract_requested_date_month_name(self):
        year = datetime.now().year
        extracted = finance_tools.extract_requested_date("what was the total revenue on april 1")
        self.assertEqual(extracted, f"{year}-04-01")

    def test_extract_requested_date_iso(self):
        extracted = finance_tools.extract_requested_date("show revenue for 2025-12-31")
        self.assertEqual(extracted, "2025-12-31")

    def test_finance_fast_plan_routes_trend_request_without_llm(self):
        plan = finance._build_finance_fast_plan(
            [HumanMessage(content="show this week's revenue trend")]
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan["operation"], "trend_summary")
        self.assertEqual(plan["arguments"]["query"], "show this week's revenue trend")

    def test_finance_fast_plan_routes_yesterday_to_daily_revenue(self):
        plan = finance._build_finance_fast_plan(
            [HumanMessage(content="what was yesterday's revenue")]
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan["operation"], "daily_revenue")
        self.assertEqual(
            plan["arguments"]["date"],
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        )

    def test_finance_fast_plan_routes_this_week_to_weekly_summary(self):
        plan = finance._build_finance_fast_plan(
            [HumanMessage(content="what was revenue this week")]
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan["operation"], "weekly_summary")
        self.assertEqual(plan["arguments"], {})

    def test_finance_fast_plan_routes_weekly_revenue_table_with_customers(self):
        plan = finance._build_finance_fast_plan(
            [HumanMessage(content="Show this week's revenue in a table by day with average ticket and customers.")]
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan["operation"], "weekly_summary")
        self.assertEqual(plan["arguments"], {})

    def test_finance_fast_plan_skips_customer_metrics_prompt(self):
        plan = finance._build_finance_fast_plan(
            [HumanMessage(content="show repeat customer metrics for this month")]
        )

        self.assertIsNone(plan)

    def test_normalize_finance_operation_routes_specific_date_to_daily(self):
        operation = finance._normalize_finance_operation(
            "summary",
            {"operation": "summary"},
            [HumanMessage(content="what was total revenue on april 1")],
        )

        self.assertEqual(operation, "daily_revenue")

    def test_normalize_finance_operation_routes_revenue_trend_to_trend_summary(self):
        operation = finance._normalize_finance_operation(
            "review",
            {"operation": "review"},
            [HumanMessage(content="show this week's revenue trend")],
        )

        self.assertEqual(operation, "trend_summary")

    def test_normalize_finance_operation_preserves_customer_metrics_for_client_query(self):
        operation = finance._normalize_finance_operation(
            "summary",
            {"operation": "summary"},
            [HumanMessage(content="show repeat customer metrics for this month")],
        )

        self.assertEqual(operation, "customer_metrics")

    @patch("agents.supervisor.get_llm", side_effect=AssertionError("LLM should not be used for finance fast-path prompts"))
    def test_supervisor_fastpath_routes_obvious_finance_prompt_without_llm(self, _mock_get_llm):
        state: AgentState = {
            "messages": [HumanMessage(content="show this week's revenue trend")],
            "tenant_id": 41,
            "user_id": 1,
            "current_agent": "supervisor",
            "pending_approval": None,
            "tool_results": None,
            "needs_human_input": False,
            "metadata": {},
        }

        command = supervisor.classify_intent(state)

        self.assertEqual(command.goto, "plan_execution")
        self.assertEqual(command.update["current_agent"], "finance")
        self.assertEqual(command.update["metadata"]["classification_source"], "fastpath_finance_operation")

    @patch("agents.finance.finance_tools.trend_summary")
    def test_finance_executor_and_formatter_use_trend_summary_results(self, mock_trend_summary):
        mock_trend_summary.return_value = {
            "window": "last_30_days",
            "range_start": "2026-03-15",
            "range_end": "2026-04-14",
            "total_revenue": 1000.0,
            "completed_services": 10,
            "total_customers": 12,
            "average_transaction": 100.0,
            "best_period": "2026-04-01",
            "points": [
                {"period": "2026-04-01", "revenue": 100.0, "customers": 2, "completed_services": 1},
                {"period": "2026-04-02", "revenue": 200.0, "customers": 3, "completed_services": 2},
                {"period": "2026-04-03", "revenue": 300.0, "customers": 4, "completed_services": 3},
                {"period": "2026-04-04", "revenue": 400.0, "customers": 5, "completed_services": 4},
                {"period": "2026-04-05", "revenue": 500.0, "customers": 6, "completed_services": 5},
                {"period": "2026-04-06", "revenue": 600.0, "customers": 7, "completed_services": 6},
            ],
        }

        executor = finance._build_finance_executor(41)
        result = executor(
            "trend_summary",
            {"query": "what is total revenue for last 30 days for each day"},
            [HumanMessage(content="what is total revenue for last 30 days for each day")],
        )
        content = finance._format_finance_response("trend_summary", result)

        mock_trend_summary.assert_called_once_with(41, "what is total revenue for last 30 days for each day")
        self.assertEqual(result.get("preferred_presentation"), "table")
        self.assertEqual(content, "Here is the day-by-day revenue table for last 30 days.")

    def test_finance_formatter_answers_zero_daily_revenue_cleanly(self):
        content = finance._format_finance_response(
            "daily_revenue",
            {
                "date": "2026-04-01",
                "completed_services": 0,
                "total_revenue": 0.0,
            },
        )

        self.assertIn("I don't see any completed services or recorded revenue", content)
        self.assertIn("2026-04-01", content)

    def test_finance_executor_requires_amount_for_record_payment(self):
        executor = finance._build_finance_executor(41)
        result = executor(
            "record_payment",
            {"method": "card"},
            [HumanMessage(content="record a card payment")],
        )

        self.assertEqual(result, {"error": "record_payment requires amount"})

    def test_parse_time_window_handles_typo_past_year(self):
        _, _, _, label = finance_tools._parse_time_window("largest revenue over past yer")
        self.assertEqual(label, "past_year")

    def test_parse_time_window_handles_last_two_years(self):
        _, _, granularity, label = finance_tools._parse_time_window(
            "give me revenue trend for last two years"
        )

        self.assertEqual(granularity, "month")
        self.assertEqual(label, "last_2_years")

    def test_parse_time_window_handles_last_eighteen_days(self):
        _, _, granularity, label = finance_tools._parse_time_window(
            "show revenue for last eighteen days"
        )

        self.assertEqual(granularity, "day")
        self.assertEqual(label, "last_18_days")

    def test_describe_time_window_humanizes_last_two_years(self):
        description = finance_tools._describe_time_window(
            "last_2_years",
            datetime(2024, 4, 27),
            datetime(2026, 4, 27),
            "month",
        )

        self.assertEqual(description, "last 2 years")

    def test_finance_formatter_humanizes_trend_window_label(self):
        content = finance._format_finance_response(
            "trend_summary",
            {
                "window": "last_2_years",
                "window_display": "last 2 years",
                "total_revenue": 5000.0,
                "completed_services": 25,
                "best_period": "2026-04",
                "best_period_revenue": 400.0,
            },
        )

        self.assertIn("For last 2 years, total revenue was $5000.00", content)


if __name__ == "__main__":
    unittest.main()
