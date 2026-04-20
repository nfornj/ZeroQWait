import os
import sys
import unittest
from unittest.mock import patch
from datetime import datetime

from langchain_core.messages import HumanMessage

# Add backend directory to import path when executed directly.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents import finance
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

    def test_classifier_routes_specific_date_to_daily(self):
        state: AgentState = {
            "messages": [HumanMessage(content="what was total revenue on april 1")],
            "tenant_id": 41,
            "user_id": 1,
            "current_agent": "finance",
            "pending_approval": None,
            "tool_results": None,
            "needs_human_input": False,
            "metadata": {},
        }
        intent = finance.finance_intent_classifier(state)
        self.assertEqual(intent, "daily_revenue")

    def test_classifier_routes_typo_specific_date_to_daily(self):
        state: AgentState = {
            "messages": [HumanMessage(content="wht ws total revenu on april 1")],
            "tenant_id": 41,
            "user_id": 1,
            "current_agent": "finance",
            "pending_approval": None,
            "tool_results": None,
            "needs_human_input": False,
            "metadata": {},
        }
        intent = finance.finance_intent_classifier(state)
        self.assertEqual(intent, "daily_revenue")

    @patch("agents.finance.finance_tools.trend_summary")
    def test_trend_summary_uses_all_points_for_each_day_requests(self, mock_trend_summary):
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

        state: AgentState = {
            "messages": [HumanMessage(content="what is total revenue for last 30 days for each day")],
            "tenant_id": 41,
            "user_id": 1,
            "current_agent": "finance",
            "pending_approval": None,
            "tool_results": None,
            "needs_human_input": False,
            "metadata": {},
        }

        result = finance.handle_trend_summary(state)
        self.assertIn("All points:", result["messages"][-1].content)
        self.assertIn("2026-04-01", result["messages"][-1].content)
        self.assertIn("2026-04-06", result["messages"][-1].content)

    @patch("agents.finance.finance_tools.trend_summary")
    def test_trend_summary_uses_all_points_for_each_date_requests(self, mock_trend_summary):
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

        state: AgentState = {
            "messages": [HumanMessage(content="what is last 30 days total revenue for each date")],
            "tenant_id": 41,
            "user_id": 1,
            "current_agent": "finance",
            "pending_approval": None,
            "tool_results": None,
            "needs_human_input": False,
            "metadata": {},
        }

        result = finance.handle_trend_summary(state)
        self.assertIn("All points:", result["messages"][-1].content)
        self.assertIn("2026-04-01", result["messages"][-1].content)
        self.assertIn("2026-04-06", result["messages"][-1].content)

    @patch("agents.finance.finance_tools.trend_summary")
    def test_trend_summary_answers_peak_revenue_directly(self, mock_trend_summary):
        mock_trend_summary.return_value = {
            "window": "this_month",
            "range_start": "2026-04-01",
            "range_end": "2026-04-14",
            "total_revenue": 10587.47,
            "completed_services": 350,
            "total_customers": 383,
            "average_transaction": 30.25,
            "best_period": "2026-04-05",
            "best_period_revenue": 1188.00,
            "points": [
                {"period": "2026-04-05", "revenue": 1188.00, "customers": 40, "completed_services": 34},
            ],
        }

        state: AgentState = {
            "messages": [HumanMessage(content="when did i get largest revenue this month")],
            "tenant_id": 41,
            "user_id": 1,
            "current_agent": "finance",
            "pending_approval": None,
            "tool_results": None,
            "needs_human_input": False,
            "metadata": {},
        }

        result = finance.handle_trend_summary(state)
        content = result["messages"][-1].content
        self.assertIn("highest revenue", content.lower())
        self.assertIn("2026-04-05", content)
        self.assertIn("$1188.00", content)

    @patch("agents.finance.finance_tools.trend_summary")
    def test_trend_summary_answers_largest_revenue_date_over_past_year(self, mock_trend_summary):
        mock_trend_summary.return_value = {
            "window": "past_year",
            "range_start": "2025-04-14",
            "range_end": "2026-04-14",
            "total_revenue": 212000.00,
            "completed_services": 7000,
            "total_customers": 7300,
            "average_transaction": 30.29,
            "best_period": "2026-03-29",
            "best_period_revenue": 1288.55,
            "points": [
                {"period": "2026-03-29", "revenue": 1288.55, "customers": 44, "completed_services": 42},
            ],
        }

        state: AgentState = {
            "messages": [HumanMessage(content="tell me the largest revenue date over past year")],
            "tenant_id": 41,
            "user_id": 1,
            "current_agent": "finance",
            "pending_approval": None,
            "tool_results": None,
            "needs_human_input": False,
            "metadata": {},
        }

        result = finance.handle_trend_summary(state)
        content = result["messages"][-1].content
        self.assertIn("highest revenue", content.lower())
        self.assertIn("2026-03-29", content)
        self.assertIn("$1288.55", content)

    @patch("agents.finance.finance_tools.trend_summary")
    def test_trend_summary_answers_typo_largest_revenue_date_over_past_year(self, mock_trend_summary):
        mock_trend_summary.return_value = {
            "window": "past_year",
            "range_start": "2025-04-14",
            "range_end": "2026-04-14",
            "total_revenue": 212000.00,
            "completed_services": 7000,
            "total_customers": 7300,
            "average_transaction": 30.29,
            "best_period": "2026-03-29",
            "best_period_revenue": 1288.55,
            "points": [
                {"period": "2026-03-29", "revenue": 1288.55, "customers": 44, "completed_services": 42},
            ],
        }

        state: AgentState = {
            "messages": [HumanMessage(content="tell me the largets revenu date over past yer")],
            "tenant_id": 41,
            "user_id": 1,
            "current_agent": "finance",
            "pending_approval": None,
            "tool_results": None,
            "needs_human_input": False,
            "metadata": {},
        }

        result = finance.handle_trend_summary(state)
        content = result["messages"][-1].content
        self.assertIn("highest revenue", content.lower())
        self.assertIn("2026-03-29", content)
        self.assertIn("$1288.55", content)

    def test_parse_time_window_handles_typo_past_year(self):
        _, _, _, label = finance_tools._parse_time_window("largest revenue over past yer")
        self.assertEqual(label, "past_year")


if __name__ == "__main__":
    unittest.main()
