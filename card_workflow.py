"""Store-neutral card creation and conservative history import."""
import json
from collections import Counter
from availability import validate_item
from presets import MAX_PRESETS

# A reference catalog, never the user's selected restaurant or a stock promise.
CATALOG_CONTEXT = {'storeCode': '1420219', 'orderType': 1, 'beType': 1}


def fingerprint(items):
    def canonical(item):
        children = item.get('historyChoices', []) or [
            c for r in item.get('roundList', []) for c in r['comboItemList']]
        return json.dumps({
            'code': item.get('productCode', item.get('code', item['name'])),
            'children': sorted((canonical(c), c['quantity']) for c in children),
            'mods': sorted((v['code'], v['key'], v['quantity'])
                           for v in item.get('modification', {}).get('values', [])),
        }, sort_keys=True, ensure_ascii=False)
    counts = Counter()
    for item in items:
        counts[canonical(item)] += item['quantity']
    return json.dumps(sorted(counts.items()), ensure_ascii=False)


def history_card_name(items):
    """Build a stable card title from names already returned by order-list."""
    labels = []
    for item in items:
        label = item['name'].strip()
        if item['quantity'] > 1:
            label += f" ×{item['quantity']}"
        labels.append(label)
    if len(labels) == 1:
        return labels[0][:80]
    name = ' + '.join(labels[:2])
    if len(labels) > 2:
        name += f' 等 {len(labels)} 项'
    return name[:80]


def history_candidates(orders):
    candidates, skipped = [], 0
    # The API returns the latest ten; sort within that window, newest first.
    for order in sorted(orders[:10], key=lambda o: o.get('createTime', ''), reverse=True):
        if str(order.get('orderStatus')) not in ('6', '8', '订单已完成', '已完成', '已评价', '订单已评价'):
            skipped += 1
            continue
        try:
            items = []
            for product in order.get('orderProductList', []):
                item = {'productCode': product['productCode'], 'name': product['productName'],
                        'quantity': product['quantity'], 'needsConfiguration': True,
                        'historyChoices': [{'code': c['productCode'], 'name': c['name'],
                                            'quantity': c['quantity']}
                                           for c in product.get('comboItemList', [])]}
                items.append(validate_item(item))
            if not items:
                raise ValueError('empty order')
            candidates.append({'name': history_card_name(items),
                               'tag': '常点', 'items': items})
        except (ValueError, KeyError, TypeError):
            skipped += 1
    return candidates, skipped


def import_unique(store, candidates):
    """Deduplicate both the batch and existing library under one write lock."""
    created, duplicate = [], 0
    with store.connection:
        store.connection.execute('BEGIN IMMEDIATE')
        existing = store.list()
        seen = {fingerprint(c['items']) for c in existing}
        remaining = min(3, max(0, MAX_PRESETS - len(existing)))
        for card in candidates:
            key = fingerprint(card['items'])
            if key in seen:
                duplicate += 1
                continue
            if len(created) >= remaining:
                break
            cursor = store.connection.execute(
                'INSERT INTO presets (name, tag, items, face) VALUES (?, ?, ?, ?)',
                (card['name'], card['tag'], json.dumps(card['items'], ensure_ascii=False),
                 store.next_face()))
            created.append(cursor.lastrowid)
            seen.add(key)
    return {'created': created, 'duplicates': duplicate,
            'capacity': max(0, MAX_PRESETS-len(existing)-len(created))}
