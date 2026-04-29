import os
import sys
import unittest
from unittest.mock import patch

from langchain_core.messages import HumanMessage

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.finance import create_finance_runnable  # noqa: E402
from agents.hr import create_hr_runnable  # noqa: E402
from agents.receptionist import create_receptionist_runnable  # noqa: E402
from agents.specialist_graph import SpecialistPlan  # noqa: E402


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


class _RaisingStructuredLLM:
    def __init__(self, message):
        self._message = message

    def invoke(self, _messages):
        raise RuntimeError(self._message)


class _RaisingLLM:
    def __init__(self, message):
        self._message = message

    def with_structured_output(self, _schema):
        return _RaisingStructuredLLM(self._message)


class TestExplicitSpecialistGraphs(unittest.TestCase):
    @patch("agents.specialist_graph.create_chat_model")
    @patch("agents.tools.booking_tools.list_queue")
    def test_receptionist_recovers_from_structured_output_boolean_string(self, mock_list_queue, mock_create_chat_model):
        mock_create_chat_model.return_value = _RaisingLLM(
            "Error code: 400 - {'error': {'message': 'tool call validation failed: parameters for tool SpecialistPlan did not match schema: errors: [`/requires_clarification`: expected boolean, but got string]', 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '<function=SpecialistPlan>{\"operation\": \"list_queue\", \"rationale\": \"To get today\\'s queue summary\", \"requires_clarification\": \"false\"}</function>'}}"
        )
        mock_list_queue.return_value = {
            "queue_items": [{"customer_name": "Alex", "position": 1}],
            "live_metrics": {"queue_length": 1, "estimated_wait_minutes": 8},
            "shop_id": 9,
        }

        result = create_receptionist_runnable(shop_id=9).invoke(
            {"messages": [HumanMessage(content="Give me today's queue summary and the next operational action.")]}
        )

        self.assertEqual(result["current_agent"], "receptionist")
        self.assertEqual(result["tool_results"]["live_metrics"]["queue_length"], 1)
        self.assertIn("1 people waiting", result["messages"][-1].content)
        self.assertIn("Next operational action", result["messages"][-1].content)
        mock_list_queue.assert_called_once_with(9)

    @patch("agents.specialist_graph.create_chat_model")
    @patch("agents.tools.booking_tools.list_queue")
    def test_receptionist_handles_natural_language_queue_question(self, mock_list_queue, mock_create_chat_model):
        mock_create_chat_model.return_value = _FakeLLM(
            {
                "operation": "list_queue",
                "arguments": {},
                "requires_clarification": False,
                "clarification_question": "",
                "rationale": "Queue status question.",
            }
        )
        mock_list_queue.return_value = {
            "queue_items": [{"customer_name": "Alex", "position": 1}],
            "live_metrics": {"queue_length": 1, "estimated_wait_minutes": 8},
            "shop_id": 9,
        }

        result = create_receptionist_runnable(shop_id=9).invoke(
            {"messages": [HumanMessage(content="How many people are in the queue right now?")]}
        )

        self.assertEqual(result["current_agent"], "receptionist")
        self.assertEqual(result["tool_results"]["live_metrics"]["queue_length"], 1)
        self.assertIn("1 people waiting", result["messages"][-1].content)
        mock_list_queue.assert_called_once_with(9)

    @patch("agents.specialist_graph.create_chat_model")
    @patch("agents.tools.booking_tools.list_appointments")
    def test_receptionist_routes_appointment_listing_through_booking_tools(self, mock_list_appointments, mock_create_chat_model):
        mock_create_chat_model.return_value = _FakeLLM(
            {
                "operation": "list_appointments",
                "arguments": {"date": "2026-04-22"},
                "requires_clarification": False,
                "clarification_question": "",
                "rationale": "Owner asked for appointment schedule.",
            }
        )
        mock_list_appointments.return_value = {
            "appointments": [{"id": 3, "customer_name": "Jordan", "scheduled_start": "2026-04-22 10:00:00"}],
            "shop_id": 9,
            "count": 1,
        }

        result = create_receptionist_runnable(shop_id=9).invoke(
            {"messages": [HumanMessage(content="Show me the appointments for 2026-04-22")]} 
        )

        self.assertEqual(result["current_agent"], "receptionist")
        self.assertEqual(result["tool_results"]["count"], 1)
        self.assertIn("Jordan", result["messages"][-1].content)
        mock_list_appointments.assert_called_once_with(9, date="2026-04-22", status=None, employee_id=None)

    @patch("agents.specialist_graph.create_chat_model")
    @patch("agents.tools.finance_tools.daily_revenue")
    def test_finance_handles_natural_language_revenue_question(self, mock_daily_revenue, mock_create_chat_model):
        mock_create_chat_model.return_value = _FakeLLM(
            {
                "operation": "daily_revenue",
                "arguments": {"date": "2026-04-20"},
                "requires_clarification": False,
                "clarification_question": "",
                "rationale": "Single-day revenue question.",
            }
        )
        mock_daily_revenue.return_value = {
            "date": "2026-04-20",
            "total_revenue": 245.0,
            "completed_services": 7,
            "average_transaction": 35.0,
            "shop_id": 9,
        }

        result = create_finance_runnable(shop_id=9).invoke(
            {"messages": [HumanMessage(content="What was revenue on 2026-04-20?")]}
        )

        self.assertEqual(result["current_agent"], "finance")
        self.assertEqual(result["tool_results"]["total_revenue"], 245.0)
        self.assertIn("$245.00", result["messages"][-1].content)
        mock_daily_revenue.assert_called_once_with(9, "2026-04-20")

    @patch("agents.specialist_graph.create_chat_model")
    @patch("agents.tools.finance_tools.get_top_clients")
    def test_finance_routes_top_clients_through_finance_tools(self, mock_get_top_clients, mock_create_chat_model):
        mock_create_chat_model.return_value = _FakeLLM(
            {
                "operation": "get_top_clients",
                "arguments": {"limit": 3},
                "requires_clarification": False,
                "clarification_question": "",
                "rationale": "Owner wants best clients.",
            }
        )
        mock_get_top_clients.return_value = {
            "clients": [{"id": 3, "name": "Jordan", "visit_count": 8}],
            "shop_id": 9,
        }

        result = create_finance_runnable(shop_id=9).invoke(
            {"messages": [HumanMessage(content="Who are my top clients?")]}
        )

        self.assertEqual(result["current_agent"], "finance")
        self.assertEqual(result["tool_results"]["clients"][0]["id"], 3)
        self.assertIn("Jordan", result["messages"][-1].content)
        mock_get_top_clients.assert_called_once_with(9, 3)

    @patch("agents.specialist_graph.create_chat_model")
    @patch("agents.tools.hr_tools.list_employees")
    def test_hr_routes_employee_listing_through_hr_tools(self, mock_list_employees, mock_create_chat_model):
        mock_create_chat_model.return_value = _FakeLLM(
            {
                "operation": "list_employees",
                "arguments": {},
                "requires_clarification": False,
                "clarification_question": "",
                "rationale": "Owner asked for the team list.",
            }
        )
        mock_list_employees.return_value = {
            "employees": [{"id": 5, "name": "Riley", "role": "employee"}],
            "shop_id": 9,
        }

        result = create_hr_runnable(shop_id=9).invoke(
            {"messages": [HumanMessage(content="Show me my employees")]} 
        )

        self.assertEqual(result["current_agent"], "hr")
        self.assertEqual(result["tool_results"]["employees"][0]["id"], 5)
        self.assertIn("Riley", result["messages"][-1].content)
        mock_list_employees.assert_called_once_with(9, False)


if __name__ == "__main__":
    unittest.main()