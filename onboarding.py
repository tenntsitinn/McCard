"""Menu-backed starter cards, never automatically inserted into the library."""

from availability import check_item, default_item


def menu_order(menu):
    # Names only prioritize exploration; rounds in the real detail determine
    # whether a meal actually is a combo.
    def priority(code):
        name = menu[code].get("name", "")
        return 0 if any(word in name for word in ("三件套", "套餐", "单人餐")) else 1
    return sorted(menu, key=priority)


def starter_page(service, codes, saved, cursor=0, size=4, scan_limit=12):
    """Bound remote work per page; return next cursor even if no match is found."""
    candidates, scanned = [], 0
    while cursor < len(codes) and len(candidates) < size and scanned < scan_limit:
        code = codes[cursor]
        cursor += 1
        scanned += 1
        meal = service.menu[code]
        if meal.get("canWithOrder") or meal.get("withOrder"):
            continue
        detail = service.detail(code)
        if not detail or not detail.get("rounds"):
            continue
        try:
            item = default_item(detail)
            bad, unknown = check_item(item, detail)
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        if bad or unknown or any(card["items"] == [item] for card in saved):
            continue
        candidates.append({"name": item["name"], "tag": "", "items": [item]})
    return candidates, cursor
