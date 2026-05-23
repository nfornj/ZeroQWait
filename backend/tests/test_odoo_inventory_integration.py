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