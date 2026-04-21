import os
import sys
import unittest
from typing import cast
from unittest.mock import patch

from langchain_core.messages import HumanMessage

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents import supervisor  # noqa: E402
from agents.state import AgentState  # noqa: E402
from agents.tools.react_tools import make_hr_tools  # noqa: E402


class TestApprovalActions(unittest.TestCase):
    @patch("agents.tools.hr_tools.assign_shift")
    def test_hr_assign_shift_tool_only_proposes_approval(self, mock_assign_shift):
        tools = {tool.name: tool for tool in make_hr_tools(shop_id=9)}

        result = tools["assign_shift"].invoke(
            {
                "user_id": 4,
                "start_time": "09:00",
                "end_time": "17:00",
                "date": "2026-04-21",
            }
        )

        self.assertTrue(result["requires_approval"])
        self.assertEqual(result["action"], "assign_shift")
        self.assertEqual(result["details"]["user_id"], 4)
        self.assertEqual(result["details"]["date"], "2026-04-21")
        mock_assign_shift.assert_not_called()

    @patch("agents.supervisor.hr_tools.assign_shift")
    def test_execute_approved_action_routes_assign_shift(self, mock_assign_shift):
        mock_assign_shift.return_value = {
            "message": "Shift assigned to employee",
            "status": "assigned",
        }
        state = cast(AgentState, {"tenant_id": 9})

        result = supervisor._execute_approved_action(
            state,
            {
                "action": "assign_shift",
                "shop_id": 9,
                "details": {
                    "user_id": 4,
                    "start_time": "09:00",
                    "end_time": "17:00",
                    "date": "2026-04-21",
                },
            },
        )

        self.assertEqual(result["status"], "assigned")
        mock_assign_shift.assert_called_once_with(
            shop_id=9,
            user_id=4,
            start_time="09:00",
            end_time="17:00",
            date="2026-04-21",
        )

    @patch("agents.supervisor._execute_approved_action")
    @patch("agents.supervisor.interrupt")
    def test_approval_gate_executes_after_owner_approval(self, mock_interrupt, mock_execute):
        mock_interrupt.return_value = {"approved": True, "reason": "Capacity reached"}
        mock_execute.return_value = {
            "message": "Queue closed. Reason: Capacity reached",
            "status": "closed",
        }
        state = cast(
            AgentState,
            {
                "tenant_id": 9,
                "messages": [HumanMessage(content="close the queue")],
                "pending_approval": {
                    "action": "close_queue",
                    "details": {"reason": "Capacity reached"},
                    "shop_id": 9,
                },
            },
        )

        result = supervisor.approval_gate(state)

        self.assertFalse(result["needs_human_input"])
        self.assertIsNone(result["pending_approval"])
        self.assertEqual(result["tool_results"]["status"], "closed")
        self.assertIn("Queue closed", result["messages"][-1].content)
        mock_execute.assert_called_once()

    @patch("agents.supervisor._execute_approved_action")
    @patch("agents.supervisor.interrupt")
    def test_approval_gate_rejection_skips_execution(self, mock_interrupt, mock_execute):
        mock_interrupt.return_value = {"approved": False, "reason": "Not today"}
        state = cast(
            AgentState,
            {
                "tenant_id": 9,
                "messages": [HumanMessage(content="remove that employee")],
                "pending_approval": {
                    "action": "remove_employee",
                    "details": {"user_id": 4},
                    "shop_id": 9,
                },
            },
        )

        result = supervisor.approval_gate(state)

        self.assertFalse(result["needs_human_input"])
        self.assertIsNone(result["pending_approval"])
        self.assertEqual(result["tool_results"]["status"], "rejected")
        self.assertIn("rejected", result["messages"][-1].content)
        mock_execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()