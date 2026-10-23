from copy import deepcopy
import io
import unittest
from unittest.mock import Mock, patch

from app import draw_interactive
from draw import card_pool, draw_card


def result(number, tag, status="available"):
    return {"preset": {"id": number, "name": f"卡{number}", "tag": tag, "items": []},
            "status": status, "reasons": ["需要调整"] if status != "available" else []}


class DrawTests(unittest.TestCase):
    def setUp(self):
        self.results = [result(1, "午餐"), result(2, "午餐"), result(3, ""),
                        result(4, "午餐", "adjust"), result(5, "午餐", "unknown")]

    def test_all_and_exact_tag_pools_exclude_unavailable(self):
        self.assertEqual([c["id"] for c in card_pool(self.results)], [1, 2, 3])
        self.assertEqual([c["id"] for c in card_pool(self.results, "午餐")], [1, 2])
        self.assertEqual([c["id"] for c in card_pool(self.results, "")], [3])
        self.assertEqual(card_pool(self.results, "午"), [])

    def test_empty_pool_and_single_card(self):
        with self.assertRaises(ValueError):
            draw_card([])
        with self.assertRaises(ValueError):
            draw_card(self.results, "晚餐")
        self.assertEqual(draw_card(self.results, "")["id"], 3)

    def test_draw_passes_each_card_once_and_does_not_consume(self):
        before = deepcopy(self.results)
        with patch("draw.random.choice", side_effect=lambda pool: pool[0]) as choice:
            first = draw_card(self.results, "午餐")
            second = draw_card(self.results, "午餐")
        self.assertEqual(first, second)
        self.assertEqual([c["id"] for c in choice.call_args.args[0]], [1, 2])
        self.assertEqual(self.results, before)

    def test_tag_draw_ui_rechecks_and_shows_result(self):
        service = Mock()
        service.check.return_value = [self.results[2]]
        output = io.StringIO()
        with patch("builtins.input", return_value="1"), patch("sys.stdout", output):
            draw_interactive(self.results, service, by_tag=True)
        service.check.assert_called_once_with([self.results[2]["preset"]])
        self.assertIn("抽中了：#3", output.getvalue())

    def test_failed_recheck_does_not_announce_success_or_redraw(self):
        service = Mock()
        service.check.return_value = [result(1, "午餐", "unknown")]
        output = io.StringIO()
        with patch("draw.random.choice", side_effect=lambda pool: pool[0]) as choice, \
             patch("sys.stdout", output):
            draw_interactive(self.results, service)
        choice.assert_called_once()
        self.assertIn("本次抽卡未完成", output.getvalue())
        self.assertNotIn("抽中了：", output.getvalue())


if __name__ == "__main__":
    unittest.main()
