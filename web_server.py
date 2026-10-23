"""Local-only web UI. MCP credentials never leave this process."""
import argparse
from contextvars import ContextVar
from http.cookies import SimpleCookie
from threading import Lock
import time
import json
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from availability import Availability, business_data, default_item, validate_item, check_item
from mcp_probe import Client, READ_TOOLS, validate_token
from presets import CARD_FACES, PresetStore, DEFAULT_DB, MAX_PRESETS
from card_workflow import CATALOG_CONTEXT, history_candidates, import_unique

ROOT = Path(__file__).resolve().parent
WEB_API_VERSION = 'cards-first-1'
IMPORTED_FRONTS = {'pies-six', 'mcflurry-eight', 'chicken-ten'}
ORBIT_FRONTS = tuple(face for face in CARD_FACES if face not in IMPORTED_FRONTS)
WEB_TOOLS = READ_TOOLS | {'calculate-price', 'create-order'}


REQUEST_TOKEN = ContextVar('mcp_user_token', default='')

def live_client():
    token = REQUEST_TOKEN.get()
    if not token:
        raise ValueError('请先接入自己的 MCP Token。')
    client = Client(token, allowed_tools=WEB_TOOLS)
    client.initialize()
    return client


def history_client(token):
    client = Client(token, allowed_tools={'order-list'})
    client.initialize()
    return client


def context_from(value):
    if not isinstance(value, dict) or value.get('beType') not in (1, 5):
        raise ValueError('请选择取餐方式。')
    code = value.get('storeCode')
    if not isinstance(code, str) or not code or len(code) > 80:
        raise ValueError('请选择门店。')
    context = {'storeCode': code, 'orderType': 1, 'beType': value['beType']}
    if value['beType'] == 5:
        if not isinstance(value.get('beCode'), str) or not value['beCode']:
            raise ValueError('门店未提供得来速业务编码。')
        context['beCode'] = value['beCode']
    return context


def checkout_items(items):
    """Remove local display fields before sending a saved card to MCP."""
    result = []
    for saved in items:
        item = {'productCode': saved['productCode'], 'quantity': saved['quantity']}
        if saved.get('modification'):
            item['modification'] = saved['modification']
        if saved.get('roundList') is not None:
            item['roundList'] = []
            for saved_round in saved['roundList']:
                group = {'round': saved_round['round'], 'comboItemList': []}
                for saved_choice in saved_round['comboItemList']:
                    choice = {'code': saved_choice['code'], 'quantity': saved_choice['quantity']}
                    if saved_choice.get('modification'):
                        choice['modification'] = saved_choice['modification']
                    group['comboItemList'].append(choice)
                item['roundList'].append(group)
        result.append(item)
    return result


class WebApp:
    def __init__(self, db=DEFAULT_DB, factory=live_client):
        self.db, self.factory = db, factory
        self.csrf = secrets.token_urlsafe(32)

    def presets(self):
        store = PresetStore(self.db)
        try:
            return store.list()
        finally:
            store.close()

    def card(self, card_id):
        if type(card_id) is not int:
            raise ValueError('卡牌编号无效。')
        card = next((card for card in self.presets() if card['id'] == card_id), None)
        if card is None:
            raise ValueError('卡牌不存在，请刷新卡包。')
        items = [validate_item(item) for item in card['items']]
        if any(not item.get('productCode') or item.get('needsConfiguration') for item in items):
            raise ValueError('这张卡仍需确认餐品配置，暂时不能核价。')
        return card, checkout_items(items)

    def api(self, route, body):
        if route == '/api/catalog':
            return self.api('/api/menu', {'context': CATALOG_CONTEXT}) | {
                'notice': '参考菜单，不绑定餐厅；实际供应和整单价格请在用卡时确认。'}
        if route == '/api/catalog-detail':
            return self.api('/api/detail', {'context': CATALOG_CONTEXT, 'code': body.get('code')})
        if route == '/api/quick-start':
            data = business_data(self.factory().call('order-list', {}))
            if not isinstance(data, dict) or not isinstance(data.get('list'), list):
                raise ValueError('历史订单格式不完整，请稍后重试。')
            candidates, skipped = history_candidates(data['list'])
            store = PresetStore(self.db)
            try:
                return import_unique(store, candidates) | {'skipped': skipped}
            finally:
                store.close()
        if route == '/api/library-check':
            context = context_from(body.get('context'))
            cards = self.presets()
            if not cards:
                return {'cards': []}
            checked = Availability(self.factory(), context).check(cards, defer_promotions=True)
            return {'cards': [{'id': c['preset']['id'], 'status': c['status'],
                               'reasons': c['reasons'], 'checkedAt': c['checkedAt']} for c in checked]}
        if route in ('/api/checkout-price', '/api/checkout-create'):
            context = context_from(body.get('context'))
            card, items = self.card(body.get('id'))
            need_tableware = body.get('needTableware', False)
            if type(need_tableware) is not bool:
                raise ValueError('餐具选项无效。')
            client = self.factory()
            arguments = context | {'items': items, 'needTableware': need_tableware}
            quote = business_data(client.call('calculate-price', arguments))
            if type(quote.get('price')) is not int:
                raise ValueError('核价接口未返回可确认的应付金额。')
            take_ways = [{key: option.get(key) for key in ('code', 'title', 'subtitle')}
                         for option in quote.get('takeWayList', [])
                         if isinstance(option, dict) and isinstance(option.get('code'), str)]
            if route == '/api/checkout-price':
                fields = ('price', 'originalPrice', 'discount', 'productPrice',
                          'packingPrice', 'tablewarePrice', 'deliveryPrice')
                return {'card': {'id': card['id'], 'name': card['name']},
                        'quote': {key: quote.get(key) for key in fields},
                        'takeWayList': take_ways}
            expected = body.get('expectedPrice')
            if type(expected) is not int or expected != quote['price']:
                raise ValueError('应付金额已经变化，请重新核价并确认。')
            take_way = body.get('takeWayCode')
            if not isinstance(take_way, str) or take_way not in {option['code'] for option in take_ways}:
                raise ValueError('请选择当前可用的取餐方式。')
            order = business_data(client.call('create-order', arguments | {'takeWayCode': take_way}))
            pay_url = order.get('payH5Url')
            if pay_url is not None and (not isinstance(pay_url, str) or not pay_url.startswith('https://')):
                raise ValueError('订单已创建，但支付链接格式异常，请到麦当劳官方渠道查看订单。')
            return {'orderId': order.get('orderId'), 'payH5Url': pay_url,
                    'orderDetail': order.get('orderDetail')}
        if route == '/api/cards-save':
            items = body.get('items')
            if not isinstance(items, list) or not 1 <= len(items) <= 100:
                raise ValueError('请选择 1–100 项餐品。')
            items = [validate_item(item) for item in items]
            if not all(i.get('productCode') for i in items):
                raise ValueError('请从参考菜单选择餐品。')
            name, tag, card_id = body.get('name'), body.get('tag', ''), body.get('id')
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
                raise ValueError('卡牌名称须为 1–80 个字符。')
            if not isinstance(tag, str) or len(tag) > 40:
                raise ValueError('标签最多 40 个字符。')
            store = PresetStore(self.db)
            try:
                if card_id is None:
                    card_id = store.save(name, items, tag)
                else:
                    if type(card_id) is not int:
                        raise ValueError('卡牌编号无效。')
                    with store.connection:
                        cursor = store.connection.execute(
                            'UPDATE presets SET name=?, tag=?, items=? WHERE id=?',
                            (name.strip(), tag.strip(), json.dumps(items, ensure_ascii=False), card_id))
                        if not cursor.rowcount:
                            raise ValueError('卡牌不存在，请刷新卡包。')
                return {'id': card_id}
            finally:
                store.close()
        if route == '/api/delete':
            if type(body.get('id')) is not int:
                raise ValueError('方案编号无效。')
            store = PresetStore(self.db)
            try:
                return {'deleted': store.delete(body['id'])}
            finally:
                store.close()
        if route not in ('/api/stores', '/api/menu', '/api/detail', '/api/validate', '/api/save'):
            raise ValueError('接口不存在。')
        if route == '/api/stores':
            city, keyword = body.get('city'), body.get('keyword')
            if not all(isinstance(s, str) and 0 < len(s.strip()) <= 100 for s in (city, keyword)):
                raise ValueError('请填写城市和门店关键词。')
            if body.get('beType') not in (1, 5):
                raise ValueError('取餐方式无效。')
            response = self.factory().call('query-nearby-stores', {
                'city': city.strip(), 'keyword': keyword.strip(), 'beType': body['beType'], 'searchType': 2})
            result = response.get('structuredContent')
            if isinstance(result, dict) and result.get('success') is False and result.get('code') == 600014:
                raise ValueError('无法在所选城市定位该位置，请核对城市与商圈/街道；也可清空“筛选位置”后重新查询。')
            stores = business_data(response)
            return {'stores': [{k: s.get(k) for k in ('storeCode', 'storeName', 'address', 'businessStatus', 'beCode')} for s in stores]}
        context = context_from(body.get('context'))
        if route in ('/api/save', '/api/validate'):
            items = body.get('items')
            if not isinstance(items, list) or not 1 <= len(items) <= 100:
                raise ValueError('请选择 1–100 项餐品。')
            items = [validate_item(i) for i in items]
            if not all(i.get('productCode') for i in items):
                raise ValueError('请从当前菜单选择餐品。')
            if route == '/api/save':
                if not isinstance(body.get('name'), str) or not body['name'].strip() or len(body['name']) > 80:
                    raise ValueError('方案名称须为 1–80 个字符。')
                if not isinstance(body.get('tag', ''), str) or len(body.get('tag', '')) > 40:
                    raise ValueError('标签最多 40 个字符。')
                if len(self.presets()) >= MAX_PRESETS:
                    raise ValueError(f'最多保存 {MAX_PRESETS} 个方案，请先删除一个。')
            service = Availability(self.factory(), context)
            # Building a card validates its configuration, not promotional eligibility.
            # Discounts and the payable total belong to final whole-order pricing.
            checked = service.check([{'items': items}], defer_promotions=True)[0]
            result = {'status': checked['status'], 'reasons': checked['reasons']}
            if route == '/api/validate' or checked['status'] == 'adjust':
                return result
            if checked['status'] == 'unknown' and body.get('allowUnknown') is not True:
                return result
            # Replace untrusted display names with names returned by MCP when available.
            for item in items:
                detail = service.details.get(item['productCode'])
                if detail:
                    item['name'] = detail['name']
                    rounds = {str(r['id']): r for r in detail.get('rounds', [])}
                    for group in item.get('roundList', []):
                        choices = {c['code']: c for c in rounds.get(group['round'], {}).get('choices', [])}
                        for choice in group['comboItemList']:
                            if choice['code'] in choices:
                                choice['name'] = choices[choice['code']]['name']
            store = PresetStore(self.db)
            try:
                result['id'] = store.save(body['name'], items, body.get('tag', ''))
            finally:
                store.close()
            return result
        client = self.factory()
        if route == '/api/menu':
            data = business_data(client.call('query-meals', context))
            return {'categories': data['categories'], 'meals': {code: {
                key: meal.get(key) for key in ('name', 'image', 'currentPrice', 'originalPrice', 'discountType', 'canWithOrder', 'withOrder')
            } for code, meal in data['meals'].items()}}
        code = body.get('code')
        if not isinstance(code, str) or not code or len(code) > 80:
            raise ValueError('餐品编码无效。')
        detail = business_data(client.call('query-meal-detail', context | {'code': code}))
        if detail.get('code') != code:
            raise ValueError('餐品详情不匹配。')
        return {'detail': detail, 'item': default_item(detail)}


def make_server(port=8765, db=DEFAULT_DB, factory=live_client):
    app = WebApp(db, factory)

    sessions = {}
    session_lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        def session_id(self):
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie', ''))
                return cookie['mcd_session'].value if 'mcd_session' in cookie else ''
            except Exception:
                return ''

        def user_token(self):
            with session_lock:
                now = time.monotonic()
                for key in list(sessions):
                    if sessions[key][1] < now:
                        del sessions[key]
                return sessions.get(self.session_id(), ('', 0))[0]

        def log_message(self, *_):
            pass

        def trusted_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def respond(self, status, data, content_type='application/json; charset=utf-8'):
            payload = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' https://menu-img.mcd.cn; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if getattr(self, 'session_cookie', None):
                self.send_header('Set-Cookie', self.session_cookie)
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if not self.trusted_host():
                return self.respond(403, {'error': '访问来源不允许。'})
            route = urlsplit(self.path).path
            try:
                if route == '/api/mcp-session':
                    return self.respond(200, {'connected': bool(self.user_token())})
                if route == '/api/bootstrap':
                    return self.respond(200, {'apiVersion': WEB_API_VERSION, 'csrf': app.csrf, 'presets': app.presets()})
                assets = {'/credentials.js': ('web/credentials.js', 'text/javascript; charset=utf-8'),
                          '/credentials.css': ('web/credentials.css', 'text/css; charset=utf-8'),
                          '/logo-on-red.svg': ('assets/brand/logo-on-red.svg', 'image/svg+xml'),
                          '/logo.svg': ('assets/brand/logo.svg', 'image/svg+xml'),
                          '/': ('web/orbit.html', 'text/html; charset=utf-8'),
                          '/builder': ('web/index.html', 'text/html; charset=utf-8'),
                          '/library': ('web/index.html', 'text/html; charset=utf-8'),
                          '/orbit': ('web/orbit.html', 'text/html; charset=utf-8'),
                          '/orbit.css': ('web/orbit.css', 'text/css; charset=utf-8'),
                          '/orbit.js': ('web/orbit.js', 'text/javascript; charset=utf-8'),
                          '/orbit-assets/card-back.png': ('assets/cards/back/card-back.png', 'image/png'),
                          '/app.js': ('web/app.js', 'text/javascript; charset=utf-8'),
                          '/style.css': ('web/style.css', 'text/css; charset=utf-8'),
                          '/card.png': ('assets/cards/front/ronald-king-v1.png', 'image/png')}
                assets.update({f'/orbit-assets/{name}.png':
                               (f'assets/cards/front/{name}.png', 'image/png')
                               for name in ORBIT_FRONTS})
                assets.update({f'/orbit-assets/{name}.png':
                               (f'assets/cards/imported/{name}.png', 'image/png')
                               for name in ('pies-six', 'mcflurry-eight', 'chicken-ten')})
                if route not in assets:
                    return self.respond(404, {'error': '页面不存在。'})
                filename, kind = assets[route]
                self.respond(200, (ROOT/filename).read_bytes(), kind)
            except (OSError, sqlite3.Error):
                self.respond(500, {'error': '本地文件或数据库读取失败。'})

        def do_POST(self):
            origin = self.headers.get('Origin')
            allowed = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
            if not self.trusted_host() or (origin and origin not in allowed) or self.headers.get('X-CSRF-Token') != app.csrf:
                return self.respond(403, {'error': '访问校验失败，请刷新页面。'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 262144 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise ValueError('请求格式无效或内容过大。')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('请求必须为对象。')
                route = urlsplit(self.path).path
                if route == '/api/mcp-session':
                    token = body.get('token')
                    if body.get('disconnect') is True:
                        with session_lock:
                            sessions.pop(self.session_id(), None)
                        self.session_cookie = 'mcd_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'
                        return self.respond(200, {'connected': False})
                    token = validate_token(token)
                    sid = secrets.token_urlsafe(32)
                    with session_lock:
                        sessions.pop(self.session_id(), None)
                        sessions[sid] = (token, time.monotonic() + 8 * 3600)
                    self.session_cookie = f'mcd_session={sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'
                    return self.respond(200, {'connected': True})
                user_token = self.user_token()
                local_routes = {'/api/cards-save', '/api/delete', '/api/save'}
                if factory is live_client and route not in local_routes and not user_token:
                    return self.respond(401, {'error': '请先接入自己的 MCP Token。'})
                context = REQUEST_TOKEN.set(user_token)
                try:
                    result = app.api(route, body)
                finally:
                    REQUEST_TOKEN.reset(context)
                self.respond(200, result)
            except ValueError as exc:
                # Our client errors contain no raw request/response or credentials.
                message = str(exc)
                token = self.user_token()
                if token:
                    message = message.replace(token, '[REDACTED]')
                self.respond(400, {'error': message})
            except (OSError, sqlite3.Error):
                self.respond(502, {'error': '连接 MCP 或数据库失败，请重试。'})
            except (KeyError, TypeError, AttributeError):
                self.respond(502, {'error': '餐品数据不完整，请刷新后重试。'})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    server = make_server(args.port, args.db)
    print(f'Local: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
