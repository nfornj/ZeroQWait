from unittest.mock import Mock, patch

from agents.tools import finance_tools


def test_daily_revenue_delegates_to_finance_mcp():
    client = Mock()
    client.daily_revenue.return_value = {
        "date": "2026-04-20",
        "total_revenue": 245.0,
        "completed_services": 7,
        "average_transaction": 35.0,
        "shop_id": 41,
    }

    with patch("agents.tools.finance_tools._get_finance_client", return_value=client):
        result = finance_tools.daily_revenue(41, "2026-04-20")

    assert result["total_revenue"] == 245.0
    client.daily_revenue.assert_called_once_with(41, "2026-04-20")


def test_create_invoice_delegates_to_finance_mcp():
    client = Mock()
    client.create_invoice.return_value = {"status": "created", "invoice_id": 88, "shop_id": 41}

    with patch("agents.tools.finance_tools._get_finance_client", return_value=client):
        result = finance_tools.create_invoice(41, "Haircut", 35.0, quantity=2)

    assert result["invoice_id"] == 88
    client.create_invoice.assert_called_once_with(41, "Haircut", 35.0, quantity=2, customer_id=None, tax_rate=0.0, notes=None)


def test_customer_search_delegates_to_finance_mcp():
    client = Mock()
    client.search_clients.return_value = {
        "clients": [{"id": 7, "name": "Jordan"}],
        "shop_id": 41,
    }

    with patch("agents.tools.finance_tools._get_finance_client", return_value=client):
        result = finance_tools.search_clients(41, "Jordan")

    assert result["clients"][0]["id"] == 7
    client.search_clients.assert_called_once_with(41, "Jordan")


def test_top_clients_delegates_to_finance_mcp():
    client = Mock()
    client.get_top_clients.return_value = {
        "clients": [{"id": 1, "name": "Alex", "visit_count": 12}],
        "shop_id": 41,
    }

    with patch("agents.tools.finance_tools._get_finance_client", return_value=client):
        result = finance_tools.get_top_clients(41, 5)

    assert result["clients"][0]["visit_count"] == 12
    client.get_top_clients.assert_called_once_with(41, limit=5)