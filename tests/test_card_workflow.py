from copy import deepcopy
import tempfile
import unittest
import json
import threading
from pathlib import Path
from urllib.request import Request, urlopen

from availability import default_item
from card_workflow import history_candidates, history_card_name, fingerprint, import_unique
from presets import CARD_FACES, MAX_PRESETS, PresetStore
from web_server import WebApp, make_server
from test_availability import FakeClient, detail, envelope


def order(code, time='2026-10-22 12:00:00', status='订单已完成'):
    return {'createTime': time, 'orderStatus': status, 'storeCode': 'private-store',
            'orderId': 'private-id', 'orderProductList': [
                {'productCode': code, 'productName': '餐品 '+code, 'quantity': 1,
                 'comboItemList': [{'productCode': 'drink', 'name': '可乐', 'quantity': 1}]}]}


class CardWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'cards.sqlite3'
        self.client = FakeClient()
        self.app = WebApp(self.path, lambda: self.client)

    def tearDown(self):
        self.temp.cleanup()

    def test_history_recent_unique_and_repeat_import(self):
        orders = [order('a'), order('a'), order('b', '2026-10-21'),
                  order('c', '2026-10-20'), order('d', '2026-10-19')]
        self.client.call = lambda *_: envelope({'list': orders})
        result = self.app.api('/api/quick-start', {})
        self.assertEqual(len(result['created']), 3)
        saved = self.app.presets()
        self.assertEqual([c['items'][0]['productCode'] for c in saved], ['a', 'b', 'c'])
        self.assertNotIn('storeCode', saved[0]['items'][0])
        self.assertNotIn('orderId', saved[0]['items'][0])
        self.assertEqual(saved[0]['items'][0]['historyChoices'][0]['code'], 'drink')
        self.assertTrue(saved[0]['items'][0]['needsConfiguration'])
        self.assertEqual(saved[0]['name'], '餐品 a')
        self.assertEqual(saved[0]['tag'], '常点')
        self.assertEqual([card['face'] for card in saved], list(CARD_FACES[:3]))
        # Repeating can add only the remaining unique combination, not duplicates.
        self.assertEqual(len(self.app.api('/api/quick-start', {})['created']), 1)
        self.assertEqual(self.app.api('/api/quick-start', {})['created'], [])

    def test_quick_start_and_store_neutral_save_over_http(self):
        self.client.call = lambda *_: envelope({'list': [order('a'), order('b'), order('c')]})
        server = make_server(0, self.path, lambda: self.client)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base+'/api/bootstrap') as response:
                token = json.load(response)['csrf']
            def post(route, body):
                req = Request(base+route, data=json.dumps(body).encode(), headers={
                    'Content-Type': 'application/json', 'X-CSRF-Token': token})
                with urlopen(req) as response:
                    return json.load(response)
            self.assertEqual(len(post('/api/quick-start', {})['created']), 3)
            self.assertEqual(post('/api/quick-start', {})['created'], [])
            saved = post('/api/cards-save', {'name': '新卡', 'items': [default_item(detail())]})
            self.assertIsInstance(saved['id'], int)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_pending_cancelled_and_malformed_orders_are_skipped(self):
        candidates, skipped = history_candidates([
            order('a', status='待支付'), order('b', status='订单已取消'),
            {'createTime': '', 'orderStatus': '6', 'orderProductList': []}, order('c')])
        self.assertEqual(skipped, 3)
        self.assertEqual(len(candidates), 1)

    def test_fingerprint_ignores_display_names_order_and_merged_quantities(self):
        first = [{'productCode': 'a', 'name': 'A', 'quantity': 2},
                 {'productCode': 'b', 'name': 'B', 'quantity': 1}]
        second = [{'productCode': 'b', 'name': '改名', 'quantity': 1},
                  {'productCode': 'a', 'name': 'A', 'quantity': 1},
                  {'productCode': 'a', 'name': 'A', 'quantity': 1}]
        self.assertEqual(fingerprint(first), fingerprint(second))
        second[0]['quantity'] = 2
        self.assertNotEqual(fingerprint(first), fingerprint(second))

    def test_history_card_name_uses_order_names_without_another_api(self):
        self.assertEqual(history_card_name([
            {'name': '巨无霸', 'quantity': 2}]), '巨无霸 ×2')
        self.assertEqual(history_card_name([
            {'name': '巨无霸', 'quantity': 1},
            {'name': '麦乐鸡', 'quantity': 1}]), '巨无霸 + 麦乐鸡')
        self.assertEqual(history_card_name([
            {'name': '巨无霸', 'quantity': 1},
            {'name': '麦乐鸡', 'quantity': 1},
            {'name': '薯条', 'quantity': 1}]), '巨无霸 + 麦乐鸡 等 3 项')

    def test_import_respects_card_capacity(self):
        store = PresetStore(self.path)
        try:
            for i in range(MAX_PRESETS-1):
                store.save(str(i), [{'productCode': str(i), 'name': str(i), 'quantity': 1}])
            candidates, _ = history_candidates([order('a'), order('b'), order('c')])
            self.assertEqual(len(import_unique(store, candidates)['created']), 1)
            self.assertEqual(len(store.list()), MAX_PRESETS)
            self.assertEqual(import_unique(store, candidates)['created'], [])
        finally:
            store.close()

    def test_save_and_edit_without_store_or_mcp(self):
        self.app.factory = lambda: self.fail('saving a card must not query a restaurant')
        body = {'name': '午餐', 'tag': '常吃', 'items': [default_item(detail())]}
        card_id = self.app.api('/api/cards-save', body)['id']
        body.update(id=card_id, name='午餐改名')
        self.app.api('/api/cards-save', body)
        self.assertEqual(len(self.app.presets()), 1)
        self.assertEqual(self.app.presets()[0]['name'], '午餐改名')
        body['items'][0]['storeCode'] = 'A'
        with self.assertRaises(ValueError):
            self.app.api('/api/cards-save', body)

    def test_library_checks_selected_restaurant_without_changing_cards(self):
        item = default_item(detail())
        self.app.api('/api/cards-save', {'name': '午餐', 'items': [item]})
        before = deepcopy(self.app.presets())
        good = self.app.api('/api/library-check', {'context': {'storeCode': 'A', 'beType': 1}})
        bad = self.app.api('/api/library-check', {'context': {'storeCode': 'B', 'beType': 1}})
        self.assertEqual(good['cards'][0]['status'], 'available')
        self.assertEqual(bad['cards'][0]['status'], 'adjust')
        self.assertEqual(self.app.presets(), before)

    def test_history_never_silently_uses_default_modifications(self):
        cards, _ = history_candidates([order('combo')])
        self.app.api('/api/cards-save', cards[0])
        result = self.app.api('/api/library-check', {'context': {'storeCode': 'A', 'beType': 1}})
        self.assertEqual(result['cards'][0]['status'], 'unknown')
        self.assertIn('历史订单', result['cards'][0]['reasons'][0])


if __name__ == '__main__':
    unittest.main()
