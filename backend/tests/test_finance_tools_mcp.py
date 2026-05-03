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


def test_process_refund_delegates_to_finance_mcp():
    client = Mock()
    client.process_refund.return_value = {"status": "refunded", "payment_id": 77, "shop_id": 41}

    with patch("agents.tools.finance_tools._get_finance_client", return_value=client):
        result = finance_tools.process_refund(41, 77, refund_amount=12.5, reason="Duplicate charge")

    assert result["payment_id"] == 77
    client.process_refund.assert_called_once_with(41, 77, refund_amount=12.5, reason="Duplicate charge")


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


def test_answer_finance_question_delegates_to_finance_mcp():
    client = Mock()
    client.answer_finance_question.return_value = {
        "answer": "Revenue today was $120.00.",
        "source": "dynamic_sql",
        "shop_id": 41,
    }

    with patch("agents.tools.finance_tools._get_finance_client", return_value=client):
        result = finance_tools.answer_finance_question(
            41,
            "how much revenue today?",
            operation="daily_revenue",
            mode="enabled",
        )

    assert result["answer"] == "Revenue today was $120.00."
    client.answer_finance_question.assert_called_once_with(
        41,
        "how much revenue today?",
        operation="daily_revenue",
        mode="enabled",
    )


def test_service_customer_counts_delegates_to_finance_mcp():
    client = Mock()
    client.service_customer_counts.return_value = {
        "services": [{"service_name": "Haircut", "customer_count": 5}],
        "shop_id": 41,
    }

    with patch("agents.tools.finance_tools._get_finance_client", return_value=client):
        result = finance_tools.service_customer_counts(
            41,
            query="customers attended for each service",
            limit=10,
        )

    assert result["services"][0]["customer_count"] == 5
    client.service_customer_counts.assert_called_once_with(
        41,
        query="customers attended for each service",
        limit=10,
    )
