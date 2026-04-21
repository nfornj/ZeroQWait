from unittest.mock import Mock, patch

from agents.tools import hr_tools


def test_list_employees_delegates_to_hr_mcp():
    client = Mock()
    client.list_employees.return_value = {
        "employees": [{"id": 4, "name": "Casey"}],
        "shop_id": 41,
    }

    with patch("agents.tools.hr_tools._get_hr_client", return_value=client):
        result = hr_tools.list_employees(41)

    assert result["employees"][0]["id"] == 4
    client.list_employees.assert_called_once_with(41, include_inactive=False)


def test_add_employee_delegates_to_hr_mcp():
    client = Mock()
    client.add_employee.return_value = {"status": "added", "user_id": 321, "shop_id": 41}

    with patch("agents.tools.hr_tools._get_hr_client", return_value=client):
        result = hr_tools.add_employee(41, "Casey Jones", email="casey@example.com", created_by=17)

    assert result["status"] == "added"
    client.add_employee.assert_called_once_with(
        41,
        "Casey Jones",
        email="casey@example.com",
        phone=None,
        role="employee",
        employee_code=None,
        created_by=17,
    )


def test_assign_shift_delegates_to_hr_mcp():
    client = Mock()
    client.assign_shift.return_value = {"status": "assigned", "shop_id": 41, "user_id": 4}

    with patch("agents.tools.hr_tools._get_hr_client", return_value=client):
        result = hr_tools.assign_shift(41, 4, "09:00", "17:00", "2026-04-21")

    assert result["status"] == "assigned"
    client.assign_shift.assert_called_once_with(41, 4, "09:00", "17:00", "2026-04-21")