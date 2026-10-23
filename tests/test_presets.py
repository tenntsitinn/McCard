import tempfile
import unittest
from pathlib import Path

from presets import CARD_FACES, MAX_PRESETS, PresetStore


class PresetStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "presets.sqlite3"
        self.store = PresetStore(self.path)

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_save_survives_restart(self):
        self.store.save("午餐", [{"name": "巨无霸", "quantity": 2}], "工作日")
        self.store.close()
        self.store = PresetStore(self.path)
        preset = self.store.list()[0]
        self.assertEqual(preset["name"], "午餐")
        self.assertEqual(preset["tag"], "工作日")
        self.assertEqual(preset["items"], [{"name": "巨无霸", "quantity": 2}])

    def test_limit_and_delete_free_slot(self):
        for number in range(MAX_PRESETS):
            self.store.save(str(number), [{"name": "薯条"}])
        with self.assertRaisesRegex(ValueError, "最多保存 16"):
            self.store.save("超出上限", [{"name": "可乐"}])
        self.assertEqual(len(self.store.list()), MAX_PRESETS)
        self.assertTrue(self.store.delete(self.store.list()[0]["id"]))
        self.store.save("新方案", [{"name": "可乐"}])
        self.assertEqual(len(self.store.list()), MAX_PRESETS)
        self.assertFalse(self.store.delete(-1))

    def test_faces_follow_fixed_order_and_reuse_first_open_face(self):
        first = self.store.save("一号", [{"name": "汉堡"}])
        self.store.save("二号", [{"name": "鸡翅"}])
        cards = self.store.list()
        self.assertEqual([card["face"] for card in cards], list(CARD_FACES[:2]))
        self.assertTrue(self.store.delete(first))
        self.store.save("补位", [{"name": "薯条"}])
        self.assertEqual(self.store.list()[-1]["face"], CARD_FACES[0])

    def test_invalid_input_does_not_save(self):
        for name, items in [
            (" ", [{"name": "可乐"}]),
            ("午餐", []),
            ("午餐", [{"name": " "}]),
            ("午餐", [{"name": "可乐", "quantity": 0}]),
            ("午餐", [{"name": "可乐", "quantity": True}]),
            ("午餐", [{"name": "可乐", "quantity": 1.5}]),
        ]:
            with self.subTest(name=name, items=items), self.assertRaises(ValueError):
                self.store.save(name, items)
        self.assertEqual(self.store.list(), [])


if __name__ == "__main__":
    unittest.main()
