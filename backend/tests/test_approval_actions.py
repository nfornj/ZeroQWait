import os
import sys
import unittest
from typing import cast
from unittest.mock import patch

from langchain_core.messages import HumanMessage

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.finance import create_finance_runnable  # noqa: E402
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


def _pending_policy_payload(action, details, mode="require_approval"):
    return {
        "action": action,
        "details": details,
        "shop_id": 9,
        "policy_key": f"approval.{action}",
        "policy_mode": mode,
        "category": "finance" if action in {"create_invoice", "record_payment", "process_refund"} else ("staffing" if action != "close_queue" else "operations"),
        "title": action.replace("_", " ").title(),
        "risk_level": "medium",
        "urgency": "normal",
        "summary": "A policy-controlled action is pending.",
        "rationale": "The agent proposed a high-impact operation.",
        "expected_impact": "Shop operations will change after execution.",
    }


class TestApprovalActions(unittest.TestCase):
    @patch("agents.specialist_graph.approval_policy.build_pending_approval")
    @patch("agents.specialist_graph.get_llm")
    @patch("agents.tools.hr_tools.assign_shift")
    def test_hr_assign_shift_request_only_proposes_approval(self, mock_assign_shift, mock_get_llm, mock_build_pending):
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
        mock_build_pending.return_value = _pending_policy_payload(
            "assign_shift",
            {
                "user_id": 4,
                "start_time": "09:00",
                "end_time": "17:00",
                "date": "2026-04-21",
            },
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

    @patch("agents.supervisor.interrupt")
    @patch("agents.supervisor.booking_tools.close_queue")
    def test_approval_gate_auto_executes_when_policy_allows(self, mock_close_queue, mock_interrupt):
        mock_close_queue.return_value = {
            "message": "Queue closed. Reason: Capacity reached",
            "status": "closed",
        }
        state = cast(
            AgentState,
            {
                "tenant_id": 9,
                "messages": [HumanMessage(content="close the queue")],
                "pending_approval": {
                    **_pending_policy_payload(
                        "close_queue",
                        {"reason": "Capacity reached"},
                        mode="allow",
                    ),
                    "title": "Close Active Queue",
                },
            },
        )

        result = supervisor.approval_gate(state)

        self.assertFalse(result["needs_human_input"])
        self.assertIsNone(result["pending_approval"])
        self.assertEqual(result["tool_results"]["status"], "closed")
        self.assertEqual(result["tool_results"]["policy_mode"], "allow")
        self.assertIn("executed this automatically", result["messages"][-1].content)
        mock_interrupt.assert_not_called()

    @patch("agents.supervisor.interrupt")
    @patch("agents.supervisor.booking_tools.close_queue")
    def test_approval_gate_blocks_when_policy_forbids(self, mock_close_queue, mock_interrupt):
        state = cast(
            AgentState,
            {
                "tenant_id": 9,
                "messages": [HumanMessage(content="close the queue")],
                "pending_approval": {
                    **_pending_policy_payload(
                        "close_queue",
                        {"reason": "Capacity reached"},
                        mode="forbid",
                    ),
                    "title": "Close Active Queue",
                },
            },
        )

        result = supervisor.approval_gate(state)

        self.assertFalse(result["needs_human_input"])
        self.assertIsNone(result["pending_approval"])
        self.assertEqual(result["tool_results"]["status"], "forbidden")
        self.assertIn("blocked by the current shop policy", result["messages"][-1].content)
        mock_interrupt.assert_not_called()
        mock_close_queue.assert_not_called()

    @patch("agents.specialist_graph.approval_policy.build_pending_approval")
    @patch("agents.specialist_graph.get_llm")
    def test_finance_create_invoice_request_proposes_approval(self, mock_get_llm, mock_build_pending):
        mock_get_llm.return_value = _FakeLLM(
            {
                "operation": "create_invoice",
                "arguments": {"service_name": "Haircut", "unit_price": 35.0, "quantity": 2},
                "requires_clarification": False,
                "clarification_question": "",
                "rationale": "Invoice creation request.",
            }
        )
        mock_build_pending.return_value = _pending_policy_payload(
            "create_invoice",
            {"service_name": "Haircut", "unit_price": 35.0, "quantity": 2},
        )

        result = create_finance_runnable(shop_id=9).invoke(
            {"messages": [HumanMessage(content="Create an invoice for two haircuts at 35 each.")]}
        )

        self.assertTrue(result["needs_human_input"])
        self.assertEqual(result["pending_approval"]["action"], "create_invoice")
        self.assertEqual(result["pending_approval"]["details"]["service_name"], "Haircut")

    @patch("agents.specialist_graph.approval_policy.build_pending_approval")
    @patch("agents.specialist_graph.get_llm")
    def test_finance_process_refund_request_proposes_approval(self, mock_get_llm, mock_build_pending):
        mock_get_llm.return_value = _FakeLLM(
            {
                "operation": "process_refund",
                "arguments": {"payment_id": 77, "refund_amount": 12.5, "reason": "Duplicate charge"},
                "requires_clarification": False,
                "clarification_question": "",
                "rationale": "Refund request.",
            }
        )
        mock_build_pending.return_value = _pending_policy_payload(
            "process_refund",
            {"payment_id": 77, "refund_amount": 12.5, "reason": "Duplicate charge"},
        )

        result = create_finance_runnable(shop_id=9).invoke(
            {"messages": [HumanMessage(content="Refund payment 77 for 12.50 because it was a duplicate charge.")]}
        )

        self.assertTrue(result["needs_human_input"])
        self.assertEqual(result["pending_approval"]["action"], "process_refund")
        self.assertEqual(result["pending_approval"]["details"]["payment_id"], 77)

    @patch("agents.supervisor.finance_tools.create_invoice")
    def test_execute_approved_action_routes_create_invoice(self, mock_create_invoice):
        mock_create_invoice.return_value = {
            "message": "Invoice INV-100 created successfully",
            "status": "created",
            "invoice_id": 100,
        }
        state = cast(AgentState, {"tenant_id": 9})

        result = supervisor._execute_approved_action(
            state,
            {
                "action": "create_invoice",
                "shop_id": 9,
                "details": {
                    "service_name": "Haircut",
                    "unit_price": 35.0,
                    "quantity": 2,
                    "customer_id": 5,
                    "tax_rate": 0.0,
                    "notes": "VIP customer",
                },
            },
        )

        self.assertEqual(result["status"], "created")
        mock_create_invoice.assert_called_once_with(
            shop_id=9,
            service_name="Haircut",
            unit_price=35.0,
            quantity=2,
            customer_id=5,
            tax_rate=0.0,
            notes="VIP customer",
        )

    @patch("agents.supervisor.finance_tools.process_refund")
    def test_execute_approved_action_routes_process_refund(self, mock_process_refund):
        mock_process_refund.return_value = {
            "message": "Refunded payment 77 for $12.50. Payment is now partially refunded.",
            "status": "partially_refunded",
            "payment_id": 77,
            "refund_amount": 12.5,
        }
        state = cast(AgentState, {"tenant_id": 9})

        result = supervisor._execute_approved_action(
            state,
            {
                "action": "process_refund",
                "shop_id": 9,
                "details": {
                    "payment_id": 77,
                    "refund_amount": 12.5,
                    "reason": "Duplicate charge",
                },
            },
        )

        self.assertEqual(result["status"], "partially_refunded")
        mock_process_refund.assert_called_once_with(
            shop_id=9,
            payment_id=77,
            refund_amount=12.5,
            reason="Duplicate charge",
        )

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

    @patch("agents.specialist_graph.approval_policy.build_pending_approval")
    @patch("agents.specialist_graph.get_llm")
    def test_hr_add_employee_request_proposes_without_email(self, mock_get_llm, mock_build_pending):
        mock_get_llm.return_value = _FakeLLM(
            {
                "operation": "add_employee",
                "arguments": {"name": "Neeraj Narayanan", "role": "employee"},
                "requires_clarification": False,
                "clarification_question": "",
                "rationale": "Add employee request.",
            }
        )
        mock_build_pending.return_value = _pending_policy_payload(
            "add_employee",
            {"name": "Neeraj Narayanan", "role": "employee", "email": None},
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