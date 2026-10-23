import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from presets import PresetStore
from test_availability import FakeClient, envelope


class InteractiveClient(FakeClient):
    def initialize(self):
        return {}

    def call(self, name, args):
        if name == "query-nearby-stores":
            self.calls.append((name, dict(args)))
            return envelope([{
                "storeName": "测试门店", "address": "测试地址", "storeCode": "A",
                "businessStatus": True, "beCode": "drive-A",
            }])
        return super().call(name, args)


class AppTests(unittest.TestCase):
    def test_choose_store_save_then_choose_preset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.sqlite3"
            answers = [
                "1", "测试城市", "测试门店", "1",  # context
                "2", "测试", "1", "1", "n", "n",  # meal, count, defaults
                "午餐", "工作日", "y",  # save
                "1", "1",  # select saved preset
                "0",
            ]
            output = io.StringIO()
            with patch("sys.argv", ["app.py", "--db", str(path)]), \
                 patch("app.Client", return_value=InteractiveClient()), \
                 patch("app.token_from_local", return_value="test-only"), \
                 patch("builtins.input", side_effect=answers), \
                 patch("sys.stdout", output):
                app.main()
            self.assertIn("已选择：午餐", output.getvalue())
            store = PresetStore(path)
            try:
                saved = store.list()[0]
                self.assertEqual(saved["tag"], "工作日")
                self.assertEqual(saved["items"][0]["productCode"], "combo")
                self.assertNotIn("storeCode", saved["items"][0])
            finally:
                store.close()

    def test_drive_through_uses_selected_business_code(self):
        client = InteractiveClient()
        with patch("builtins.input", side_effect=["2", "城市", "门店", "1"]), \
             patch("sys.stdout", io.StringIO()):
            _, context = app.select_context(client)
        self.assertEqual(context, {"storeCode": "A", "orderType": 1, "beType": 5, "beCode": "drive-A"})


if __name__ == "__main__":
    unittest.main()
