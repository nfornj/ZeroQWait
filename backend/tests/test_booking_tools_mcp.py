import os
import sys
from unittest.mock import Mock, patch


sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.tools import booking_tools  # noqa: E402


def test_list_queue_normalizes_booking_mcp_snapshot():
    client = Mock()
    client.list_queue.return_value = {
        "shop_id": 41,
        "queue_id": 9,
        "items": [{"id": 1, "customer_name": "Alex", "position": 1}],
        "total_in_queue": 1,
        "waiting_count": 1,
        "serving_count": 0,
        "next_customer": "Alex",
        "live_metrics": {"queue_length": 1, "estimated_wait_minutes": 8},
    }

    with patch("agents.tools.booking_tools._get_booking_client", return_value=client):
        result = booking_tools.list_queue(41)

    assert result["shop_id"] == 41
    assert result["queue_id"] == 9
    assert result["queue_items"][0]["customer_name"] == "Alex"
    assert result["live_metrics"]["estimated_wait_minutes"] == 8
    client.list_queue.assert_called_once_with(41)


def test_call_next_normalizes_booking_mcp_queue_item_response():
    client = Mock()
    client.call_next.return_value = {
        "id": 11,
        "customer_name": "Jordan",
        "status": "being_served",
    }

    with patch("agents.tools.booking_tools._get_booking_client", return_value=client):
        result = booking_tools.call_next(41, employee_id=5)

    assert result["message"] == "Now serving Jordan"
    assert result["queue_item"]["id"] == 11
    assert result["status"] == "being_served"
    client.call_next.assert_called_once_with(41, 5)


def test_close_queue_normalizes_booking_mcp_close_response():
    client = Mock()
    client.close_queue.return_value = {
        "success": True,
        "shop_id": 41,
        "closed_queues": 1,
        "reason": "Owner approved closure",
    }

    with patch("agents.tools.booking_tools._get_booking_client", return_value=client):
        result = booking_tools.close_queue(41, "Owner approved closure")

    assert result["shop_id"] == 41
    assert result["status"] == "closed"
    assert result["closed_queues"] == 1
    assert result["message"] == "Queue closed. Reason: Owner approved closure"
    client.close_queue.assert_called_once_with(41, "Owner approved closure")


def test_create_service_delegates_to_booking_mcp():
    client = Mock()
    client.create_service.return_value = {
        "message": "Service 'Haircut' created at $35.00",
        "service": {"id": 21, "name": "Haircut", "cost": 35.0},
        "shop_id": 41,
    }

    with patch("agents.tools.booking_tools._get_booking_client", return_value=client):
        result = booking_tools.create_service(41, "Haircut", 35.0, duration_minutes=30)

    assert result["service"]["id"] == 21
    client.create_service.assert_called_once_with(41, "Haircut", 35.0, duration_minutes=30, description=None, currency="USD")


def test_book_appointment_delegates_to_booking_mcp():
    client = Mock()
    client.book_appointment.return_value = {
        "id": 99,
        "shop_id": 41,
        "customer_name": "Alex",
        "scheduled_start": "2026-04-22 10:00:00",
    }

    with patch("agents.tools.booking_tools._get_booking_client", return_value=client):
        result = booking_tools.book_appointment(41, 7, "2026-04-22T10:00", "Alex")

    assert result["id"] == 99
    client.book_appointment.assert_called_once_with(41, 7, "2026-04-22T10:00", "Alex", customer_phone=None, customer_email=None, employee_id=None, notes=None)


def test_list_appointments_normalizes_booking_mcp_response():
    client = Mock()
    client.list_appointments.return_value = {
        "appointments": [{"id": 9, "customer_name": "Alex"}],
        "shop_id": 41,
        "count": 1,
    }

    with patch("agents.tools.booking_tools._get_booking_client", return_value=client):
        result = booking_tools.list_appointments(41, date="2026-04-22")

    assert result["count"] == 1
    assert result["appointments"][0]["id"] == 9
    client.list_appointments.assert_called_once_with(41, date="2026-04-22", status=None, employee_id=None)


def test_get_available_slots_normalizes_booking_mcp_response():
    client = Mock()
    client.get_available_slots.return_value = {
        "available_slots": [{"start": "2026-04-22 10:00:00", "end": "2026-04-22 10:30:00", "available": True}],
        "shop_id": 41,
        "date": "2026-04-22",
    }

    with patch("agents.tools.booking_tools._get_booking_client", return_value=client):
        result = booking_tools.get_available_slots(41, 7, "2026-04-22")

    assert len(result["available_slots"]) == 1
    client.get_available_slots.assert_called_once_with(41, 7, "2026-04-22", employee_id=None)