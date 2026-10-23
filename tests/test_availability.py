from copy import deepcopy
import tempfile
import unittest
from pathlib import Path

from availability import Availability, check_item, default_item
from presets import PresetStore


def envelope(data):
    return {"structuredContent": {"success": True, "data": data}, "isError": False}


def detail():
    # Synthetic test data, shaped like the observed menu. Never a live quote.
    return {
        "code": "combo", "name": "测试套餐", "supportModify": False,
        "rounds": [{
            "id": 1, "name": "饮料", "minQuantity": 1, "maxQuantity": 1,
            "choices": [{
                "code": "drink", "name": "可乐", "quantity": 1, "isDefault": 1,
                "maxQuantity": -1, "supportModify": True,
                "modification": {"items": [{
                    "minValues": 1, "maxValues": 1,
                    "values": [
                        {"code": "ice", "name": "标准", "selectedKey": "normal",
                         "selectedQuantity": 1, "minQuantity": 0, "maxQuantity": 1},
                        {"code": "ice", "name": "去冰", "selectedKey": "none",
                         "selectedQuantity": 0, "minQuantity": 0, "maxQuantity": 1},
                    ],
                }]},
            }],
        }],
    }


class FakeClient:
    def __init__(self):
        self.calls = []
        self.data = detail()
        self.fail_detail = False
        self.fail_menu = False

    def call(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "query-meals":
            if self.fail_menu:
                return {"structuredContent": {"success": False}, "isError": False}
            return envelope({"meals": {"combo": {"name": "测试套餐"}} if args["storeCode"] == "A" else {}})
        if self.fail_detail:
            raise OSError("offline")
        return envelope(deepcopy(self.data))


class AvailabilityTests(unittest.TestCase):
    def preset(self):
        return {"id": 1, "name": "午餐", "tag": "常吃", "items": [default_item(detail())]}

    def service(self, client, store="A"):
        return Availability(client, {"storeCode": store, "orderType": 1, "beType": 1})

    def test_check_before_selection_deduplicates_and_refreshes(self):
        client = FakeClient()
        service = self.service(client)
        results = service.check([self.preset(), self.preset()])
        self.assertEqual([r["status"] for r in results], ["available", "available"])
        self.assertEqual([c[0] for c in client.calls].count("query-meal-detail"), 1)
        client.data["rounds"][0]["choices"] = []
        self.assertEqual(service.check([self.preset()])[0]["status"], "adjust")

    def test_store_change_does_not_modify_preset(self):
        original = self.preset()
        copy = deepcopy(original)
        client = FakeClient()
        self.assertEqual(self.service(client).check([original])[0]["status"], "available")
        result = self.service(client, "B").check([original])[0]
        self.assertEqual(result["status"], "adjust")
        self.assertIn("菜单未提供", result["reasons"][0])
        self.assertEqual(original, copy)

    def test_business_and_detail_failures_are_unknown(self):
        client = FakeClient()
        client.fail_menu = True
        self.assertEqual(self.service(client).check([self.preset()])[0]["status"], "unknown")
        client.fail_menu = False
        client.fail_detail = True
        self.assertEqual(self.service(client).check([self.preset()])[0]["status"], "unknown")

    def test_legacy_text_is_not_matched_by_name(self):
        preset = self.preset()
        preset["items"] = [{"name": "测试套餐", "quantity": 1}]
        self.assertEqual(self.service(FakeClient()).check([preset])[0]["status"], "unknown")

    def test_ice_key_not_just_code_is_checked(self):
        item = default_item(detail())
        option = item["roundList"][0]["comboItemList"][0]["modification"]["values"][0]
        option["key"] = "none"
        self.assertEqual(check_item(item, detail()), ([], []))
        option["key"] = "removed"
        bad, _ = check_item(item, detail())
        self.assertTrue(bad)

    def test_quantity_and_missing_round_rejected(self):
        item = default_item(detail())
        item["roundList"][0]["comboItemList"][0]["quantity"] = 2
        self.assertTrue(check_item(item, detail())[0])
        item["roundList"] = []
        self.assertTrue(check_item(item, detail())[0])

    def test_removed_topping_requires_explicit_unselected_choice(self):
        current = {"code": "burger", "name": "汉堡", "rounds": [], "supportModify": True,
                   "modification": {"items": [{"minValues": 0, "maxValues": 1, "values": [
                       {"code": "onion", "selectedKey": "yes", "unselectedKey": "no",
                        "selectedQuantity": 0, "minQuantity": 0, "maxQuantity": 1},
                   ]}]}}
        item = default_item(current)
        self.assertEqual(item["modification"]["values"][0]["key"], "no")
        self.assertEqual(check_item(item, current), ([], []))
        item["modification"]["values"] = []
        self.assertTrue(check_item(item, current)[0])

    def test_persistence_preserves_choices_without_store_context(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PresetStore(Path(directory) / "test.sqlite3")
            try:
                item = default_item(detail())
                store.save("午餐", [item], "常吃")
                self.assertEqual(store.list()[0]["items"], [item])
                with self.assertRaises(ValueError):
                    store.save("错误", [dict(item, storeCode="A")])
                self.assertEqual(len(store.list()), 1)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
