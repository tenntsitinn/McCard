"""Explicit live MCP smoke; writes cards only to a temporary database."""
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from web_server import WebApp

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    with tempfile.TemporaryDirectory() as directory:
        app = WebApp(Path(directory)/'smoke.sqlite3')
        stores = app.api('/api/stores', {'city': '惠州', 'keyword': '华贸天地', 'beType': 1})['stores']
        store = next(s for s in stores if s['storeCode'] == '1420219' and s['businessStatus'] is True)
        context = {'storeCode': store['storeCode'], 'beType': 1}
        menu = app.api('/api/menu', {'context': context})
        image_url = menu['meals']['1100']['image']
        assert image_url.startswith('https://menu-img.mcd.cn/')
        with urlopen(image_url, timeout=30) as image:
            assert image.headers.get('Content-Type', '').startswith('image/')
            assert image.read(8) == b'\x89PNG\r\n\x1a\n'
        product = app.api('/api/detail', {'context': context, 'code': '9900005466'})
        item = product['item']
        for group in item['roundList']:
            for choice in group['comboItemList']:
                if choice['code'] == '3050':
                    choice['modification'] = {'values': [{'code': '200002', 'key': '0-0', 'quantity': 1}]}
        saved = app.api('/api/save', {'context': context, 'items': [item], 'name': '网页联调临时卡', 'tag': '测试'})
        assert saved.get('id'), saved
        persisted = app.presets()[0]
        assert persisted['items'] == [item]
        assert 'context' not in persisted
        print(f"LIVE PASS: {store['storeName']}, {len(menu['meals'])} products; customized combo saved and reloaded from temporary SQLite. Status: {saved['status']}")
