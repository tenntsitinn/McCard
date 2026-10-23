import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import menu_prompt, quick_start
from availability import Availability, default_item
from onboarding import menu_order, starter_page
from presets import PresetStore
from test_availability import detail, envelope


class StarterClient:
    def __init__(self):
        self.calls = []
        self.fail = False

    def call(self, name, args):
        self.calls.append((name, args))
        if name == "query-meals":
            return envelope({"meals": {
                "a": {"name": "A套餐"}, "b": {"name": "B套餐"},
                "member": {"name": "会员套餐", "canWithOrder": True},
            }})
        if self.fail:
            raise OSError("offline")
        value = detail()
        value.update(code=args["code"], name=args["code"].upper() + "套餐")
        return envelope(value)


class OnboardingTests(unittest.TestCase):
    def service(self):
        client = StarterClient()
        service = Availability(client, {"storeCode": "A", "orderType": 1, "beType": 1})
        service.load_menu()
        return service

    def test_candidates_skip_membership_duplicates_and_failed_details(self):
        service = self.service()
        saved = [{"items": [default_item(service.detail("a"))]}]
        candidates, cursor = starter_page(service, menu_order(service.menu), saved)
        self.assertEqual([c["items"][0]["productCode"] for c in candidates], ["b"])
        self.assertEqual(cursor, 3)
        self.assertNotIn("member", [a.get("code") for _, a in service.client.calls])
        service.details = {}
        service.client.fail = True
        self.assertEqual(starter_page(service, menu_order(service.menu), [])[0], [])

    def test_scan_budget_allows_pagination(self):
        service = self.service()
        first, cursor = starter_page(service, menu_order(service.menu), [], scan_limit=1)
        second, cursor = starter_page(service, menu_order(service.menu), [], cursor, scan_limit=1)
        self.assertEqual(first[0]["items"][0]["productCode"], "a")
        self.assertEqual(second[0]["items"][0]["productCode"], "b")
        self.assertEqual(cursor, 2)

    def test_two_confirmed_cards_then_first_draw(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PresetStore(Path(directory) / "test.sqlite3")
            service = self.service()
            output = io.StringIO()
            try:
                with patch("builtins.input", side_effect=[
                    "1", "", "", "y",  # first card, default name, no tag
                    "1", "晚餐", "常吃", "y", "d",  # second, draw immediately
                ]), patch("sys.stdout", output):
                    quick_start(store, service)
                cards = store.list()
                self.assertEqual(len(cards), 2)
                self.assertEqual(cards[0]["tag"], "")
                self.assertEqual(cards[1]["name"], "晚餐")
                self.assertIn("抽中了：", output.getvalue())
                self.assertNotIn("storeCode", str(cards))
            finally:
                store.close()

    def test_cancel_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PresetStore(Path(directory) / "test.sqlite3")
            try:
                with patch("builtins.input", side_effect=["1", "", "", "n", "0"]), \
                     patch("sys.stdout", io.StringIO()):
                    quick_start(store, self.service())
                self.assertEqual(store.list(), [])
            finally:
                store.close()

    def test_empty_and_single_card_do_not_offer_draw(self):
        with patch("sys.stdout", io.StringIO()):
            self.assertNotIn("6 全量抽卡", menu_prompt([]))
            one = [{"status": "available", "preset": {"id": 1, "tag": ""}}]
            self.assertNotIn("6 全量抽卡", menu_prompt(one))
            two = one + [{"status": "available", "preset": {"id": 2, "tag": ""}}]
            self.assertIn("6 全量抽卡", menu_prompt(two))
            two[1]["status"] = "unknown"
            self.assertNotIn("6 全量抽卡", menu_prompt(two))


if __name__ == "__main__":
    unittest.main()
