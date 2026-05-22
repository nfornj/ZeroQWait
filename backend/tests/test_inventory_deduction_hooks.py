import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from modules.appointments.models import AppointmentStatus
from modules.appointments.service import appointment_service
from modules.queues.models import QueueStatus
from modules.queues.service import queue_service


class TestInventoryDeductionHooks(unittest.TestCase):
    @patch("modules.appointments.service.SessionLocal")
    @patch("agents.tools.inventory_tools.deduct_service_supplies")
    def test_appointment_completion_deducts_inventory_once(self, mock_deduct, _mock_session_local):
        session = MagicMock()
        appointment = SimpleNamespace(
            id=14,
            shop_id=8,
            service_id=5,
            status=AppointmentStatus.IN_PROGRESS,
            actual_end=None,
            customer_id=None,
            employee_id=None,
            customer_name="Ava",
            customer_phone=None,
            customer_email=None,
            scheduled_start=None,
            scheduled_end=None,
            actual_start=None,
            service_cost=0.0,
            notes=None,
            cancelled_at=None,
            cancel_reason=None,
            created_at=None,
        )
        session.query.return_value.filter.return_value.first.return_value = appointment

        with patch.object(appointment_service, "get_session", return_value=session):
            result = appointment_service.update_status(8, 14, "completed")

        self.assertEqual(result["status"], "completed")
        mock_deduct.assert_called_once_with(
            shop_id=8,
            service_id=5,
            appointment_id=14,
            session=session,
        )
        session.commit.assert_called_once()

    @patch("modules.appointments.service.SessionLocal")
    @patch("agents.tools.inventory_tools.deduct_service_supplies")
    def test_appointment_repeat_completed_does_not_deduct_twice(self, mock_deduct, _mock_session_local):
        session = MagicMock()
        appointment = SimpleNamespace(
            id=15,
            shop_id=8,
            service_id=5,
            status=AppointmentStatus.COMPLETED,
            actual_end=None,
            customer_id=None,
            employee_id=None,
            customer_name="Ava",
            customer_phone=None,
            customer_email=None,
            scheduled_start=None,
            scheduled_end=None,
            actual_start=None,
            service_cost=0.0,
            notes=None,
            cancelled_at=None,
            cancel_reason=None,
            created_at=None,
        )
        session.query.return_value.filter.return_value.first.return_value = appointment

        with patch.object(appointment_service, "get_session", return_value=session):
            result = appointment_service.update_status(8, 15, "completed")

        self.assertEqual(result["status"], "completed")
        mock_deduct.assert_not_called()

    @patch("modules.queues.service.schemas.QueueItem.model_validate", return_value={"id": 21, "status": "completed"})
    @patch("agents.tools.inventory_tools.deduct_service_supplies")
    def test_queue_completion_deducts_inventory_once(self, mock_deduct, _mock_validate):
        session = MagicMock()
        item = SimpleNamespace(
            id=21,
            service_id=11,
            status=QueueStatus.BEING_SERVED,
            queue=SimpleNamespace(shop_id=4),
        )
        session.query.return_value.filter.return_value.first.return_value = item

        with patch.object(queue_service, "get_db", return_value=session):
            result = queue_service.update_queue_item(21, {"status": "completed"})

        self.assertEqual(result["status"], "completed")
        mock_deduct.assert_called_once_with(
            shop_id=4,
            service_id=11,
            session=session,
        )
        session.commit.assert_called_once()

    @patch("modules.queues.service.schemas.QueueItem.model_validate", return_value={"id": 22, "status": "completed"})
    @patch("agents.tools.inventory_tools.deduct_service_supplies")
    def test_queue_repeat_completed_does_not_deduct_twice(self, mock_deduct, _mock_validate):
        session = MagicMock()
        item = SimpleNamespace(
            id=22,
            service_id=11,
            status=QueueStatus.COMPLETED,
            queue=SimpleNamespace(shop_id=4),
        )
        session.query.return_value.filter.return_value.first.return_value = item

        with patch.object(queue_service, "get_db", return_value=session):
            queue_service.update_queue_item(22, {"status": "completed"})

        mock_deduct.assert_not_called()


if __name__ == "__main__":
    unittest.main()