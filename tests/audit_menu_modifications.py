"""Read-only audit of unnamed modification groups; no orders or card writes."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from availability import business_data
from web_server import live_client


def main():
    client = live_client()
    context = {'storeCode': '1420219', 'orderType': 1, 'beType': 1}
    menu = business_data(client.call('query-meals', context))['meals']
    report = {'checkedAt': datetime.now(timezone.utc).isoformat(),
              'context': context, 'total': len(menu), 'checked': 0,
              'groups': [], 'failures': []}
    for code, meal in menu.items():
        try:
            detail = business_data(client.call('query-meal-detail', context | {'code': code}))
            nodes = [detail] + [choice for group in detail.get('rounds', [])
                                for choice in group.get('choices', [])]
            for node in nodes:
                for index, group in enumerate(node.get('modification', {}).get('items', [])):
                    values = group.get('values', [])
                    names = [value.get('name', '') for value in values]
                    unnamed = not group.get('name')
                    ambiguous = unnamed and any(name.strip() in ('加', '不加', '有', '无', '标准', '正常') for name in names)
                    # Ice labels make the meaning of an otherwise unnamed group clear.
                    if any('冰' in name for name in names):
                        ambiguous = False
                    report['groups'].append({
                        'menuCode': code, 'menuName': meal.get('name'),
                        'productCode': node.get('code'), 'productName': node.get('name'),
                        'groupIndex': index + 1, 'groupName': group.get('name'),
                        'ambiguous': ambiguous, 'options': [
                            {k: value.get(k) for k in ('code', 'name', 'selectedKey', 'price')}
                            for value in values]})
            report['checked'] += 1
        except (ValueError, OSError, KeyError, TypeError):
            report['failures'].append({'code': code, 'name': meal.get('name')})
        if (report['checked'] + len(report['failures'])) % 20 == 0:
            print(f"Checked {report['checked'] + len(report['failures'])}/{len(menu)}", flush=True)
    target = Path(__file__).resolve().parents[1] / 'data' / 'mcp' / 'modification-audit.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'checked': report['checked'], 'total': report['total'],
                      'failures': report['failures'], 'report': str(target)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
