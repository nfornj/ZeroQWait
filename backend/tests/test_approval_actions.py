import os
import sys
import unittest
from typing import cast
from unittest.mock import patch

from langchain_core.messages import HumanMessage

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.hr import create_hr_runnable  # noqa: E402
from agents import supervisor  # noqa: E402
from agents.state import AgentState  # noqa: E402
from agents.specialist_graph import SpecialistPlan  # noqa: E402
from agents.tools import hr_tools  # noqa: E402


class _FakeStructuredLLM:
    def __init__(self, payload):
        self._payload = payload

    def invoke(self, _messages):
        return SpecialistPlan(**self._payload)


class _FakeLLM:
    def __init__(self, payload):
        self._payload = payload

    def with_structured_output(self, _schema):
        return _FakeStructuredLLM(self._payload)


class TestApprovalActions(unittest.TestCase):
    @patch("agents.specialist_graph.get_llm")
    @patch("agents.tools.hr_tools.assign_shift")
    def test_hr_assign_shift_request_only_proposes_approval(self, mock_assign_shift, mock_get_llm):
        mock_get_llm.return_value = _FakeLLM(
            {
                "operation": "assign_shift",
                "arguments": {
                    "user_id": 4,
                    "start_time": "09:00",
                    "end_time": "17:00",
                    "date": "2026-04-21",
                },
                "requires_clarification": False,
                "clarification_question": "",
                "rationale": "Shift assignment request.",
            }
        )

        result = create_hr_runnable(shop_id=9).invoke(
            {"messages": [HumanMessage(content="Assign employee 4 to a 9:00 to 17:00 shift on 2026-04-21.")]}
        )

        self.assertTrue(result["needs_human_input"])
        self.assertEqual(result["pending_approval"]["action"], "assign_shift")
        self.assertEqual(result["pending_approval"]["details"]["user_id"], 4)
        self.assertEqual(result["pending_approval"]["details"]["date"], "2026-04-21")
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

    @patch("agents.tools.hr_tools.SessionLocal")
    @patch("agents.tools.hr_tools.get_password_hash")
    def test_add_employee_creates_user_and_shop_link(self, mock_hash, mock_session_local):
        mock_hash.return_value = "hashed-password"

        class QueryStub:
            def __init__(self, result=None):
                self._result = result

            def filter(self, *args, **kwargs):
                return self

            def first(self):
                return self._result

        class SessionStub:
            def __init__(self):
                self.created = []
                self.user_query_count = 0

            def query(self, model):
                if model.__name__ == "User":
                    result = None if self.user_query_count < 3 else None
                    self.user_query_count += 1
                    return QueryStub(result)
                return QueryStub(None)

            def add(self, item):
                if item.__class__.__name__ == "User":
                    item.id = 321
                elif item.__class__.__name__ == "ShopEmployee":
                    item.id = 654
                self.created.append(item)

            def flush(self):
                return None

            def commit(self):
                return None

            def refresh(self, item):
                return None

            def rollback(self):
                return None

            def close(self):
                return None

        session = SessionStub()
        mock_session_local.return_value = session

        result = hr_tools._local_add_employee(
            shop_id=9,
            name="Casey Jones",
            email="casey@example.com",
            role="employee",
            created_by=17,
        )

        self.assertEqual(result["status"], "added")
        self.assertEqual(result["user_id"], 321)
        self.assertEqual(result["employee"]["user"]["username"], result["username"])
        self.assertTrue(result["temporary_password"])

    @patch("agents.tools.hr_tools.SessionLocal")
    @patch("agents.tools.hr_tools.get_password_hash")
    def test_add_employee_generates_staff_email_when_missing(self, mock_hash, mock_session_local):
        mock_hash.return_value = "hashed-password"

        class QueryStub:
            def __init__(self, result=None):
                self._result = result

            def filter(self, *args, **kwargs):
                return self

            def first(self):
                return self._result

        class SessionStub:
            def __init__(self):
                self.created = []

            def query(self, model):
                return QueryStub(None)

            def add(self, item):
                if item.__class__.__name__ == "User":
                    item.id = 777
                elif item.__class__.__name__ == "ShopEmployee":
                    item.id = 888
                self.created.append(item)

            def flush(self):
                return None

            def commit(self):
                return None

            def refresh(self, item):
                return None

            def rollback(self):
                return None

            def close(self):
                return None

        session = SessionStub()
        mock_session_local.return_value = session

        result = hr_tools._local_add_employee(
            shop_id=41,
            name="Neeraj Narayanan",
            email=None,
            role="employee",
            created_by=17,
        )

        self.assertEqual(result["status"], "added")
        self.assertEqual(result["email"], "neerajnarayanan.shop41@staff.zeroqwait.local")
        self.assertEqual(result["employee"]["user"]["email"], result["email"])
        self.assertIn("Staff email", result["message"])

    @patch("agents.specialist_graph.get_llm")
    def test_hr_add_employee_request_proposes_without_email(self, mock_get_llm):
        mock_get_llm.return_value = _FakeLLM(
            {
                "operation": "add_employee",
                "arguments": {"name": "Neeraj Narayanan", "role": "employee"},
                "requires_clarification": False,
                "clarification_question": "",
                "rationale": "Add employee request.",
            }
        )

        result = create_hr_runnable(shop_id=9).invoke(
            {"messages": [HumanMessage(content="Add employee Neeraj Narayanan as an employee.")]}
        )

        self.assertTrue(result["needs_human_input"])
        self.assertEqual(result["pending_approval"]["details"]["name"], "Neeraj Narayanan")
        self.assertIsNone(result["pending_approval"]["details"]["email"])
        self.assertIn("generated automatically", result["messages"][-1].content)


if __name__ == "__main__":
    unittest.main()