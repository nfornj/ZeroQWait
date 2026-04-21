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