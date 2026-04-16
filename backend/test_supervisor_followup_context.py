import os
import sys
import unittest
from typing import cast
from unittest.mock import patch

from langchain_core.messages import HumanMessage

# Allow direct execution: python backend/test_supervisor_followup_context.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents import supervisor  # noqa: E402
from agents.state import AgentState  # noqa: E402


class TestSupervisorFollowupContext(unittest.TestCase):
    def test_contextual_followup_routes_to_last_specialist(self):
        state = cast(AgentState, {
            "messages": [HumanMessage(content="what are their names?")],
            "metadata": {"last_specialist_target": "hr"},
            "current_agent": "supervisor",
        })

        command = supervisor.classify_intent(state)
        update = command.update or {}

        self.assertEqual(update["current_agent"], "hr")
        self.assertEqual(update["metadata"]["classification_source"], "followup_contextual")
        self.assertEqual(update["metadata"]["followup_from"], "hr")

    def test_contextual_followup_does_not_override_explicit_domain(self):
        state = cast(AgentState, {
            "messages": [HumanMessage(content="what are their names and revenue today?")],
            "metadata": {"last_specialist_target": "hr"},
            "current_agent": "supervisor",
        })

        command = supervisor.classify_intent(state)
        update = command.update or {}

        self.assertEqual(update["current_agent"], "finance")
        self.assertEqual(update["metadata"]["classification_source"], "heuristic")

    def test_contextual_followup_uses_recent_history_when_metadata_missing(self):
        state = cast(AgentState, {
            "messages": [
                HumanMessage(content="no i want to talk about employees now"),
                HumanMessage(content="what are their names?"),
            ],
            "metadata": {"shop_id": 1, "user_id": 1},
            "current_agent": "supervisor",
        })

        command = supervisor.classify_intent(state)
        update = command.update or {}

        self.assertEqual(update["current_agent"], "hr")
        self.assertEqual(update["metadata"]["classification_source"], "followup_contextual")
        self.assertEqual(update["metadata"]["followup_from"], "hr")

    @patch("agents.supervisor.placeholder_hr")
    def test_execute_plan_persists_last_specialist_target(self, mock_placeholder_hr):
        mock_placeholder_hr.return_value = {
            "messages": [HumanMessage(content="ok")],
            "current_agent": "hr",
        }
        state = cast(AgentState, {
            "messages": [HumanMessage(content="list employees")],
            "metadata": {"execution_target": "hr"},
            "current_agent": "hr",
        })

        result = supervisor.execute_plan(state)

        self.assertEqual(result["metadata"]["last_specialist_target"], "hr")


if __name__ == "__main__":
    unittest.main()
