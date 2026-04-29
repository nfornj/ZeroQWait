import unittest

from agents.briefings import (
    build_owner_briefing,
    build_owner_briefing_actions,
    enrich_pending_approval_payload,
)


class TestOperationalBriefings(unittest.TestCase):
    def test_owner_briefing_actions_prioritize_operational_follow_up(self):
        actions = build_owner_briefing_actions(
            {
                "queue_length": 9,
                "estimated_wait_minutes": 55,
                "active_employees": 1,
            },
            pending_count=2,
            active_services=0,
        )

        labels = [item["label"] for item in actions]
        self.assertIn("Review approvals", labels)
        self.assertIn("Check queue", labels)
        self.assertIn("Show staffing gaps", labels)
        self.assertIn("Fix services", labels)

    def test_enrich_pending_approval_close_queue_adds_decision_context(self):
        payload = enrich_pending_approval_payload(
            {
                "action": "close_queue",
                "details": {"reason": "Team is at capacity"},
                "shop_id": 4,
            },
            metrics={"queue_length": 6, "estimated_wait_minutes": 35},
        )

        self.assertEqual(payload["title"], "Close Active Queue")
        self.assertEqual(payload["risk_level"], "high")
        self.assertIn("Team is at capacity", payload["reason"])
        self.assertIn("6 customers", payload["expected_impact"])

    def test_build_owner_briefing_includes_actions_and_alert_history(self):
        briefing = build_owner_briefing(
            shop_id=7,
            shop_name="North Barbers",
            metrics={
                "queue_length": 4,
                "estimated_wait_minutes": 25,
                "people_being_served": 1,
                "active_employees": 1,
            },
            active_services=3,
            active_employees=1,
            pending_count=1,
            today_revenue=320.0,
            today_transactions=9,
            weekly_revenue=1840.0,
            alert_history=[
                {
                    "severity": "warning",
                    "title": "Queue pressure is building",
                    "body": "There are 4 people waiting.",
                    "created_at": "2026-04-20T08:00:00Z",
                }
            ],
            generated_at="2026-04-20T09:00:00Z",
            source="scheduled",
        )

        self.assertEqual(briefing["source"], "scheduled")
        self.assertEqual(briefing["metrics"]["pending_approvals"], 1)
        self.assertTrue(briefing["actions"])
        self.assertTrue(briefing["alerts"])
        self.assertEqual(briefing["alert_history"][0]["title"], "Queue pressure is building")

    def test_enrich_pending_approval_assign_shift_adds_schedule_context(self):
        payload = enrich_pending_approval_payload(
            {
                "action": "assign_shift",
                "details": {
                    "user_id": 12,
                    "date": "2026-04-21",
                    "start_time": "09:00",
                    "end_time": "17:00",
                },
                "shop_id": 4,
            }
        )

        self.assertEqual(payload["title"], "Assign Employee Shift")
        self.assertEqual(payload["risk_level"], "medium")
        self.assertIn("2026-04-21", payload["summary"])
        self.assertIn("09:00", payload["reason"])


if __name__ == "__main__":
    unittest.main()