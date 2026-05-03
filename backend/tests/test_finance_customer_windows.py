import os
import sys
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

# Add backend directory to import path when executed directly.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.tools import finance_tools


class TestFinanceCustomerWindows(unittest.TestCase):
    def test_parse_last_10_days_window(self):
        start_dt, end_dt, granularity, label = finance_tools._parse_time_window(
            "how many customers have visited last 10 days"
        )

        self.assertEqual(label, "last_10_days")
        self.assertEqual(granularity, "day")
        self.assertLessEqual(start_dt, end_dt)
        self.assertGreaterEqual((end_dt.date() - start_dt.date()).days, 9)

    def test_parse_named_month_window(self):
        now = datetime.now()
        expected_year = now.year if now.month >= 2 else now.year - 1

        start_dt, end_dt, granularity, label = finance_tools._parse_time_window(
            "total customers in february"
        )

        self.assertEqual(granularity, "day")
        self.assertEqual(label, f"month_{expected_year}_02")
        self.assertEqual(start_dt.year, expected_year)
        self.assertEqual(start_dt.month, 2)
        self.assertEqual(start_dt.day, 1)
        self.assertEqual(end_dt.month, 2)

    def test_parse_last_n_weeks_window(self):
        start_dt, end_dt, granularity, label = finance_tools._parse_time_window(
            "show customer traffic for last 3 weeks"
        )

        self.assertEqual(label, "last_3_weeks")
        self.assertEqual(granularity, "day")
        self.assertLessEqual(start_dt, end_dt)

    def test_parse_last_n_weeks_window_long_range_uses_week_granularity(self):
        _, _, granularity, label = finance_tools._parse_time_window(
            "show customer traffic for last 8 weeks"
        )

        self.assertEqual(label, "last_8_weeks")
        self.assertEqual(granularity, "week")

    def test_parse_today_uses_supplied_local_timezone_anchor(self):
        now = datetime(2026, 5, 2, 20, 3, 0, tzinfo=ZoneInfo("America/Toronto"))

        start_dt, end_dt, granularity, label = finance_tools._parse_time_window(
            "hello whats the total customers came today",
            now=now,
        )

        self.assertEqual(label, "today")
        self.assertEqual(granularity, "hour")
        self.assertEqual(start_dt.date().isoformat(), "2026-05-02")
        self.assertEqual(end_dt.date().isoformat(), "2026-05-02")


if __name__ == "__main__":
    unittest.main()
