import unittest

from langchain_core.messages import HumanMessage

from agents.hr import _normalize_hr_operation


class TestHrOperationNormalization(unittest.TestCase):
    def test_request_employee_details_normalizes_to_add_employee(self) -> None:
        operation = _normalize_hr_operation(
            "request_employee_details",
            {"requires_clarification": True, "clarification_question": "What email should I use?"},
            [HumanMessage(content="Add a new employee called Maria")],
        )

        self.assertEqual(operation, "add_employee")


if __name__ == "__main__":
    unittest.main()