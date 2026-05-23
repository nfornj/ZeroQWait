import unittest
from unittest.mock import MagicMock, patch

from integrations.odoo_client import OdooClient
from agents import inventory


class TestOdooInventoryClient(unittest.TestCase):
    def _client(self) -> OdooClient:
        client = OdooClient.__new__(OdooClient)
        client.enabled = True
        client._uid = 1
        client._models = MagicMock()
        return client

    def test_get_product_by_barcode_resolves_m2o_record(self) -> None:
        client = self._client()
        client._execute = MagicMock(
            return_value=[
                {
                    "id": 12,
                    "name": "Color Tube",
                    "qty_on_hand": 8.0,
                    "uom_id": [1, "Units"],
                    "default_code": "COLOR-1",
                    "barcode": "ABC123",
                }
            ]
        )

        result = client.get_product_by_barcode("ABC123", company_id=7)

        self.assertEqual(result["product"]["id"], 12)
        self.assertEqual(result["product"]["uom_id"], "Units")
        client._execute.assert_called_once_with(
            "product.product", "search_read",
            [("barcode", "=", "ABC123"), ("company_id", "=", 7)],
            ["id", "name", "qty_on_hand", "list_price", "default_code", "barcode"],
            limit=1,
        )

    def test_get_product_by_id_uses_direct_domain_lookup(self) -> None:
        client = self._client()
        client._execute = MagicMock(
            return_value=[
                {
                    "id": 44,
                    "name": "Developer",
                    "qty_on_hand": 3.5,
                    "uom_id": [1, "Units"],
                    "default_code": "DEV",
                    "barcode": "DEV44",
                }
            ]
        )

        result = client.get_product_by_id(44, company_id=9)

        self.assertEqual(result["product"]["name"], "Developer")
        self.assertEqual(result["product"]["uom_id"], "Units")
        client._execute.assert_called_once_with(
            "product.product", "search_read",
            [("id", "=", 44), ("company_id", "=", 9)],
            ["id", "name", "qty_on_hand", "uom_id", "default_code", "barcode"],
            limit=1,
        )

    def test_receive_stock_uses_execute_wrapper_for_existing_quant(self) -> None:
        client = self._client()
        client._execute = MagicMock(side_effect=[[{"id": 31, "quantity": 4.0}], True])

        result = client.receive_stock(44, 2.5, company_id=9, notes="delivery")

        self.assertEqual(result, {"quant_id": 31, "qty_added": 2.5, "notes": "delivery"})
        self.assertEqual(client._execute.call_args_list[1].args, ("stock.quant", "write", [31], {"quantity": 6.5}))

    def test_receive_stock_uses_execute_wrapper_for_new_quant(self) -> None:
        client = self._client()
        client._execute = MagicMock(side_effect=[[], 55])

        result = client.receive_stock(44, 2.5, company_id=9)

        self.assertEqual(result["quant_id"], 55)
        self.assertEqual(
            client._execute.call_args_list[1].args,
            ("stock.quant", "create", {"product_id": 44, "quantity": 2.5, "location_id": 8, "company_id": 9}),
        )

    def test_adjust_stock_uses_execute_wrapper(self) -> None:
        client = self._client()
        client._execute = MagicMock(side_effect=[[{"id": 31, "quantity": 4.0}], True])

        result = client.adjust_stock(44, -1.5, reason="count", company_id=9)

        self.assertEqual(result, {"quant_id": 31, "qty_delta": -1.5, "reason": "count"})
        self.assertEqual(client._execute.call_args_list[1].args, ("stock.quant", "write", [31], {"quantity": 2.5}))

    def test_diagnose_access_uses_allowlisted_read_models(self) -> None:
        client = self._client()
        client._execute = MagicMock(return_value=[{"id": 1}])

        result = client.diagnose_access(models=["res.partner"], company_id=9)

        self.assertEqual(result["checks"], [{"model": "res.partner", "ok": True, "sample_count": 1}])
        client._execute.assert_called_once_with(
            "res.partner", "search_read", [("company_id", "=", 9)], ["id"], limit=1
        )

    def test_diagnose_access_rejects_non_allowlisted_model(self) -> None:
        client = self._client()
        client._execute = MagicMock()

        result = client.diagnose_access(models=["ir.config_parameter"], company_id=9)

        self.assertFalse(result["checks"][0]["ok"])
        self.assertIn("not allowlisted", result["checks"][0]["error"])
        client._execute.assert_not_called()

    def test_aggregate_records_uses_read_group_with_company_scope(self) -> None:
        client = self._client()
        client._execute = MagicMock(return_value=[{"stage_id": [4, "Won"], "expected_revenue": 1000.0}])

        result = client.aggregate_records(
            "crm.lead",
            domain=[("type", "=", "opportunity")],
            fields=["expected_revenue:sum"],
            groupby=["stage_id"],
            company_id=9,
        )

        self.assertEqual(result["rows"][0]["stage_id"], "Won")
        client._execute.assert_called_once_with(
            "crm.lead",
            "read_group",
            [("type", "=", "opportunity"), ("company_id", "=", 9)],
            ["expected_revenue:sum"],
            ["stage_id"],
            limit=80,
        )

    def test_health_check_verifies_odoo_database_auth(self) -> None:
        client = self._client()
        common = MagicMock()
        common.version.return_value = {"server_version": "17.0-test"}
        common.authenticate.return_value = 7

        with patch("integrations.odoo_client.xmlrpc.client.ServerProxy", return_value=common), patch(
            "integrations.odoo_client.ODOO_DB", "demo_odoo"
        ):
            result = client.health_check()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["db"], "demo_odoo")
        self.assertEqual(result["uid"], 7)
        common.authenticate.assert_called_once()

    def test_health_check_reports_database_auth_failure(self) -> None:
        client = self._client()
        common = MagicMock()
        common.version.return_value = {"server_version": "17.0-test"}
        common.authenticate.return_value = False

        with patch("integrations.odoo_client.xmlrpc.client.ServerProxy", return_value=common), patch(
            "integrations.odoo_client.ODOO_DB", "missing_odoo"
        ):
            result = client.health_check()

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["db"], "missing_odoo")
        self.assertIn("authentication failed", result["error"])


class TestInventoryOdooLookup(unittest.TestCase):
    def test_check_stock_product_id_uses_direct_odoo_lookup(self) -> None:
        executor = inventory._build_inventory_executor(shop_id=504)
        fake_odoo_client = MagicMock()
        fake_odoo_client.enabled = True
        fake_odoo_client.get_product_by_id.return_value = {"product": {"id": 44, "name": "Developer"}}

        with patch.object(inventory, "_get_odoo_company_id", return_value=9), patch.object(
            inventory, "odoo_client", fake_odoo_client
        ):
            result = executor("check_stock", {"product_id": "44"}, [])

        self.assertEqual(result, {"product": {"id": 44, "name": "Developer"}})
        fake_odoo_client.get_product_by_id.assert_called_once_with(44, company_id=9)
        fake_odoo_client.get_low_stock_items.assert_not_called()


if __name__ == "__main__":
    unittest.main()