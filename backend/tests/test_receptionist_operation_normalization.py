import unittest

from langchain_core.messages import HumanMessage

from agents.receptionist import _normalize_receptionist_operation


class TestReceptionistOperationNormalization(unittest.TestCase):
    def test_queue_length_alias_normalizes_to_list_queue(self) -> None:
        operation = _normalize_receptionist_operation(
            "get_queue_length",
            {},
            [HumanMessage(content="How many people are waiting in our queue right now?")],
        )

        self.assertEqual(operation, "list_queue")

    def test_generic_answer_for_queue_status_normalizes_to_list_queue(self) -> None:
        operation = _normalize_receptionist_operation(
            "answer",
            {"rationale": "Queue count question"},
            [HumanMessage(content="How many people are waiting in our queue right now?")],
        )

        self.assertEqual(operation, "list_queue")

    def test_generic_answer_for_wait_time_normalizes_to_get_wait_time(self) -> None:
        operation = _normalize_receptionist_operation(
            "answer",
            {"rationale": "Wait time question"},
            [HumanMessage(content="What is the estimated wait time for the queue?")],
        )

        self.assertEqual(operation, "get_wait_time")


if __name__ == "__main__":
    unittest.main()