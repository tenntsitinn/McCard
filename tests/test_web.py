import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from availability import default_item
from test_availability import FakeClient, detail
from presets import MAX_PRESETS
from web_server import WebApp, make_server, context_from, WEB_API_VERSION


class WebTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db = Path(self.directory.name)/'web.sqlite3'
        self.client = FakeClient()
        self.app = WebApp(self.db, lambda: self.client)
        self.body = {'context': {'storeCode': 'A', 'beType': 1}, 'items': [default_item(detail())], 'name': '午餐', 'tag': '常吃'}

    def tearDown(self):
        self.directory.cleanup()

    def test_promotional_item_still_checks_configuration_without_membership_prompt(self):
        original_call = self.client.call
        def call(name, args):
            response = original_call(name, args)
            if name == 'query-meals':
                response['structuredContent']['data']['meals']['combo'].update(
                    canWithOrder=True, withOrder={'membershipCode': '106'})
            return response
        self.client.call = call
        self.assertEqual(self.app.api('/api/validate', self.body)['status'], 'available')
        self.assertIn('id', self.app.api('/api/save', self.body))
        self.client.data['rounds'][0]['choices'] = []
        self.assertEqual(self.app.api('/api/validate', self.body)['status'], 'adjust')

    def test_store_location_failure_explains_city_and_keyword(self):
        self.client.call = lambda *_: {'structuredContent': {
            'success': False, 'code': 600014, 'message': '没有查询到该地址'}}
        with self.assertRaisesRegex(ValueError, '核对城市与商圈/街道'):
            self.app.api('/api/stores', {'city': '广州', 'keyword': '华贸天地', 'beType': 1})

    def test_other_store_failures_are_not_misreported_as_location_errors(self):
        self.client.call = lambda *_: {'structuredContent': {
            'success': False, 'code': 500, 'message': 'upstream error'}}
        with self.assertRaisesRegex(ValueError, '接口业务查询失败'):
            self.app.api('/api/stores', {'city': '广州', 'keyword': '麦当劳', 'beType': 1})

    def test_detail_zero_quantity_default_remains_unselected(self):
        self.client.data['rounds'][0]['choices'][0]['quantity'] = 0
        result = self.app.api('/api/detail', {
            'context': self.body['context'], 'code': 'combo'})
        self.assertEqual(result['item']['quantity'], 1)
        self.assertEqual(result['item']['roundList'][0]['comboItemList'], [])
        self.assertEqual(len(result['detail']['rounds'][0]['choices']), 1)
        # An incomplete round may be displayed, but must not be saved as valid.
        self.body['items'] = [result['item']]
        rejected = self.app.api('/api/save', self.body)
        self.assertEqual(rejected['status'], 'adjust')
        self.assertEqual(self.app.presets(), [])

    def test_detail_positive_default_is_preserved(self):
        result = self.app.api('/api/detail', {
            'context': self.body['context'], 'code': 'combo'})
        self.assertEqual(result['item'], default_item(detail()))

    def test_save_checks_current_menu_and_persists_modification_without_context(self):
        self.body['items'][0]['roundList'][0]['comboItemList'][0]['modification']['values'][0]['key'] = 'none'
        result = self.app.api('/api/save', self.body)
        self.assertEqual(result['status'], 'available')
        saved = self.app.presets()[0]
        self.assertNotIn('context', saved)
        self.assertEqual(saved['items'][0]['roundList'][0]['comboItemList'][0]['modification']['values'][0]['key'], 'none')
        self.client.data['rounds'][0]['choices'] = []
        rejected = self.app.api('/api/save', self.body)
        self.assertEqual(rejected['status'], 'adjust')
        self.assertEqual(len(self.app.presets()), 1)

    def test_unknown_requires_explicit_confirmation_and_fresh_check(self):
        self.client.fail_detail = True
        self.assertNotIn('id', self.app.api('/api/save', self.body))
        self.assertEqual(self.app.presets(), [])
        self.body['allowUnknown'] = True
        self.assertIn('id', self.app.api('/api/save', self.body))

    def test_checkout_reprices_before_creating_order(self):
        card_id = self.app.api('/api/cards-save', {
            'items': self.body['items'], 'name': '午餐', 'tag': ''})['id']
        original_call = self.client.call
        def call(name, args):
            if name == 'calculate-price':
                self.assertNotIn('name', args['items'][0])
                self.assertNotIn('name', args['items'][0]['roundList'][0]['comboItemList'][0])
                return {'structuredContent': {'success': True, 'data': {
                    'price': 3650, 'originalPrice': 4900, 'discount': 1250,
                    'productPrice': 3650, 'packingPrice': 0, 'tablewarePrice': 0,
                    'deliveryPrice': 0, 'takeWayList': [
                        {'code': 'counter', 'title': '柜台取餐', 'subtitle': ''}]}}}
            if name == 'create-order':
                return {'structuredContent': {'success': True, 'data': {
                    'orderId': 'ORDER-1', 'payH5Url': 'https://pay.mcd.cn/order/1'}}}
            return original_call(name, args)
        self.client.call = call
        price = self.app.api('/api/checkout-price', {
            'id': card_id, 'context': self.body['context'], 'needTableware': False})
        self.assertEqual(price['quote']['price'], 3650)
        with self.assertRaisesRegex(ValueError, '金额已经变化'):
            self.app.api('/api/checkout-create', {
                'id': card_id, 'context': self.body['context'], 'needTableware': False,
                'takeWayCode': 'counter', 'expectedPrice': 3600})
        created = self.app.api('/api/checkout-create', {
            'id': card_id, 'context': self.body['context'], 'needTableware': False,
            'takeWayCode': 'counter', 'expectedPrice': 3650})
        self.assertEqual(created['orderId'], 'ORDER-1')
        self.assertTrue(created['payH5Url'].startswith('https://'))

    def test_limit_and_untrusted_context(self):
        for _ in range(MAX_PRESETS):
            self.app.api('/api/save', self.body)
        with self.assertRaisesRegex(ValueError, '16'):
            self.app.api('/api/save', self.body)
        with self.assertRaises(ValueError):
            context_from({'storeCode': 'A', 'beType': 5})
        self.body['items'][0]['storeCode'] = 'A'
        with self.assertRaises(ValueError):
            self.app.api('/api/validate', self.body)

    def test_http_blocks_cross_origin_and_files_outside_allowlist(self):
        server = make_server(0, self.db, lambda: self.client)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base+'/api/bootstrap') as r:
                bootstrap = json.load(r)
            self.assertEqual(bootstrap['apiVersion'], WEB_API_VERSION)
            self.assertTrue(all(card.get('face') for card in bootstrap['presets']))
            for route in ('/builder', '/library'):
                with urlopen(base+route) as r:
                    self.assertEqual(r.status, 200)
            for path in ('/.env', '/data/presets.sqlite3', '/../mcp_probe.py'):
                with self.assertRaises(HTTPError) as caught:
                    urlopen(base+path)
                self.assertEqual(caught.exception.code, 404)
            request = Request(base+'/api/save', data=json.dumps(self.body).encode(), headers={
                'Content-Type': 'application/json', 'X-CSRF-Token': bootstrap['csrf'], 'Origin': 'https://evil.example'})
            with self.assertRaises(HTTPError) as caught:
                urlopen(request)
            self.assertEqual(caught.exception.code, 403)
            request.remove_header('Origin')
            with urlopen(request) as r:
                self.assertIn('id', json.load(r))
            self.assertEqual(len(self.app.presets()), 1)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
