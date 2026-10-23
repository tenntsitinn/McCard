"""Interactive local preset library backed by read-only McDonald's MCP."""

import argparse
import sqlite3
from pathlib import Path

from availability import Availability, business_data, default_item, default_modification
from mcp_probe import Client, token_from_local
from presets import DEFAULT_DB, MAX_PRESETS, PresetStore
from draw import card_pool, draw_card
from onboarding import menu_order, starter_page

STATUS = {"available": "当前可选", "adjust": "需要调整", "unknown": "暂未确认"}


def choose(prompt, values, label):
    if not values:
        raise ValueError("没有可选项。")
    for index, value in enumerate(values, 1):
        print(f"{index}. {label(value)}")
    while True:
        value = input(prompt).strip()
        if value.isdigit() and 1 <= int(value) <= len(values):
            return values[int(value) - 1]
        print("请输入列表中的序号。")


def positive(prompt):
    while True:
        value = input(prompt).strip()
        if value.isdigit() and int(value) > 0:
            return int(value)
        print("请输入正整数。")


def select_context(client):
    mode = choose("选择取餐方式：", [1, 5],
                  lambda v: "到店自取" if v == 1 else "得来速")
    city = input("城市：").strip()
    keyword = input("门店关键词：").strip()
    if not city or not keyword:
        raise ValueError("城市和门店关键词不能为空。")
    stores = business_data(client.call("query-nearby-stores", {
        "beType": mode, "searchType": 2, "city": city, "keyword": keyword,
    }))
    store = choose("选择门店：", stores,
                   lambda s: f"{s['storeName']} | {s['address']} | 编码 {s['storeCode']}"
                   + (" | 营业中" if s.get("businessStatus") is True else " | 营业状态未确认或暂停"))
    if store.get("businessStatus") is not True:
        raise ValueError("该门店当前营业状态不支持即时检查，请选择营业门店。")
    context = {"storeCode": store["storeCode"], "orderType": 1, "beType": mode}
    if mode == 5:
        if not store.get("beCode"):
            raise ValueError("该门店未返回得来速业务编码。")
        context["beCode"] = store["beCode"]
    return store["storeName"], context


def show_results(results):
    print("\n以下结果仅表示当前菜单和选项匹配，不保证库存，也不是报价。")
    if not results:
        print("方案库为空，可先保存一个方案。")
    for status in ("available", "adjust", "unknown"):
        group = [r for r in results if r["status"] == status]
        if not group:
            continue
        print(f"\n{STATUS[status]}（{len(group)}）")
        for result in group:
            preset = result["preset"]
            print(f"  #{preset['id']} {preset['name']} | 标签：{preset['tag'] or '未设置'}")
            for reason in result["reasons"]:
                print(f"    {reason}")


def customize_modifications(current):
    result = []
    for group in current.get("modification", {}).get("items", []):
        options = group.get("values", [])
        print(f"特调组选项：最少 {group.get('minValues')}，最多 {group.get('maxValues')}")
        for index, option in enumerate(options, 1):
            print(f"  {index}. {option['name']}（默认数量 {option.get('selectedQuantity', 0)}）")
        while True:
            raw = input("输入选中序号，以空格分隔；回车保留默认，0 表示全不选：").strip()
            try:
                indexes = ({i for i, o in enumerate(options, 1) if o.get("selectedQuantity", 0) > 0}
                           if not raw else set() if raw == "0" else {int(v) for v in raw.split()})
                if any(i < 1 or i > len(options) for i in indexes):
                    raise ValueError
                if not group["minValues"] <= len(indexes) <= group["maxValues"]:
                    raise ValueError
                break
            except (ValueError, KeyError):
                print("选择不符合该组选项数量限制，请重试。")
        for index, option in enumerate(options, 1):
            selected = index in indexes
            key = option.get("selectedKey") if selected else option.get("unselectedKey")
            if key is not None:
                count = 0
                if selected:
                    count = 1 if option.get("maxQuantity") == 1 else positive(f"{option['name']} 数量：")
                result.append({"code": option["code"], "key": key, "quantity": count})
    return {"values": result}


def build_item(detail):
    item = default_item(detail, positive("份数："))
    if input("调整套餐搭配或特调？[y/N]：").strip().lower() != "y":
        return item
    if detail.get("modification"):
        item["modification"] = customize_modifications(detail)
    item["roundList"] = []
    for group in detail.get("rounds", []):
        print(f"\n{group['name']}（总数量 {group['minQuantity']}–{group['maxQuantity']}）")
        selected = {}
        while True:
            choice = choose("选择搭配：", group["choices"],
                            lambda c: c["name"] + ("【可特调】" if c.get("supportModify") else ""))
            count = positive("该搭配数量：")
            value = {"code": choice["code"], "name": choice["name"], "quantity": count}
            if choice.get("modification"):
                value["modification"] = default_modification(choice)
                if input("调整此餐品特调？[y/N]：").strip().lower() == "y":
                    value["modification"] = customize_modifications(choice)
            selected[choice["code"]] = value
            total = sum(c["quantity"] for c in selected.values())
            if group["minQuantity"] <= total <= group["maxQuantity"]:
                if total == group["maxQuantity"] or input("继续添加搭配？[y/N]：").strip().lower() != "y":
                    break
            elif total > group["maxQuantity"]:
                print("超过本轮数量限制，请重新选择。")
                selected = {}
        item["roundList"].append({"round": str(group["id"]), "comboItemList": list(selected.values())})
    return item


def save_from_menu(store, service):
    if len(store.list()) >= MAX_PRESETS:
        print(f"方案已满 {MAX_PRESETS} 个，请先删除一个。")
        return
    menu = service.load_menu()
    service.details = {}
    items = []
    while True:
        keyword = input("搜索餐品名称：").strip()
        matches = [(code, value) for code, value in menu.items() if keyword in value.get("name", "")]
        code, meal = choose("选择餐品：", matches, lambda pair: pair[1]["name"])
        detail = service.detail(code)
        if detail is None:
            raise ValueError("餐品详情查询失败，未保存方案，请重试。")
        items.append(build_item(detail))
        if input("继续添加餐品？[y/N]：").strip().lower() != "y":
            break
    name = input("方案名称：").strip()
    tag = input("自定义标签（可留空）：").strip()
    preview = {"id": "预览", "name": name, "tag": tag, "items": items}
    checks = service.check([preview])
    show_results(checks)
    if checks[0]["status"] == "adjust":
        print("搭配不符合当前菜单，未保存。请重新选择。")
        return
    for item in items:
        print(f"{item['name']} × {item['quantity']}")
        for group in item.get("roundList", []):
            for choice in group["comboItemList"]:
                print(f"  {choice['name']} × {choice['quantity']}")
    if input("保存这份方案？[y/N]：").strip().lower() == "y":
        number = store.save(name, items, tag)
        print(f"已保存 #{number}。门店和取餐方式未写入方案。")


def show_card(card, drawn=False):
    if drawn:
        print(f"抽中了：#{card['id']} {card['name']} | 标签：{card['tag'] or '未设置'}")
    else:
        print(f"已选择：{card['name']}。")
    for item in card["items"]:
        print(f"  {item['name']} × {item['quantity']}")
        for group in item.get("roundList", []):
            for choice in group["comboItemList"]:
                print(f"    {choice['name']} × {choice['quantity']}")
    print("仅选择一张卡，本版本不核价、不下单。")


def draw_interactive(results, service, by_tag=False):
    tag = None
    if by_tag:
        tags = sorted({r["preset"]["tag"] for r in results})
        if not tags:
            print("卡库为空，请先保存一张卡。")
            return
        tag = choose("选择抽卡标签：", tags,
                     lambda t: f"{t or '未设置标签'}（当前可抽 {len(card_pool(results, t))} 张）")
    print(f"本次卡池：{len(card_pool(results, tag))} 张；每张等概率，可重复抽到。")
    card = draw_card(results, tag)
    fresh = service.check([card])
    if fresh[0]["status"] != "available":
        print("抽中的卡未通过最新检查，本次抽卡未完成，请刷新后重试。")
        show_results(fresh)
        return
    show_card(card, drawn=True)


def quick_start(store, service):
    print("\n先存下几份你愿意吃的卡，建议 3 张；不用一次完成。")
    print("以下来自当前门店菜单，均为 1 份套餐、默认搭配和默认特调。")
    print("需要更换搭配或特调，可以返回选择“自由组合”。")
    service.load_menu()
    service.details = {}
    codes = menu_order(service.menu)
    cursor = 0
    while len(store.list()) < MAX_PRESETS:
        candidates, cursor = starter_page(service, codes, store.list(), cursor)
        while candidates:
            print(f"\n已存 {len(store.list())} 张卡")
            for index, candidate in enumerate(candidates, 1):
                item = candidate["items"][0]
                parts = [f"{choice['name']} × {choice['quantity']}"
                         for group in item["roundList"] for choice in group["comboItemList"]]
                print(f"{index}. {candidate['name']}：{' + '.join(parts)}")
            can_draw = len(store.list()) >= 2
            action = input("输入序号预览保存 / n 换一批 / 0 返回"
                           + (" / d 去抽卡" if can_draw else "") + "：").strip().lower()
            if action == "0":
                return
            if action == "d" and can_draw:
                fresh = service.check(store.list())
                if len(card_pool(fresh)) >= 2:
                    draw_interactive(fresh, service)
                    return
                print("当前可用卡不足 2 张，可继续添加，或返回直接选用已有卡。")
                continue
            if action == "n":
                break
            if not action.isdigit() or not 1 <= int(action) <= len(candidates):
                print("请输入有效序号或操作。")
                continue
            candidate = candidates[int(action) - 1]
            print(f"预览：{candidate['name']} × 1，使用默认搭配与默认特调。")
            name = input(f"卡名（回车使用“{candidate['name']}”）：").strip() or candidate["name"]
            tag = input("标签（可留空，之后也可先用全量抽卡）：").strip()
            if input("确认保存这张卡？[y/N]：").strip().lower() != "y":
                continue
            fresh = service.check([dict(candidate, id="预览")])
            if fresh[0]["status"] != "available":
                print("这张候选卡未通过最新检查，尚未保存。")
                show_results(fresh)
                candidates.remove(candidate)
                continue
            if any(card["items"] == candidate["items"] for card in store.list()):
                print("这份默认搭配已经保存过了。")
            else:
                number = store.save(name, candidate["items"], tag)
                count = len(store.list())
                print(f"已保存 #{number}，目前 {count} 张。")
                if count == 1:
                    print("第一张卡已就位，可以直接选用；再存一张就能随机选。")
                elif count == 2:
                    print("已经有两张卡，可以试抽一次，也可以继续添加。")
                    if input("输入 d 立即抽卡，回车继续添加：").strip().lower() == "d":
                        fresh = service.check(store.list())
                        if len(card_pool(fresh)) >= 2:
                            draw_interactive(fresh, service)
                            return
                        print("当前可用卡不足 2 张，请返回重试检查或继续添加。")
            candidates.remove(candidate)
            if len(store.list()) >= MAX_PRESETS:
                print(f"已达到 {MAX_PRESETS} 张上限。")
                return
        if cursor >= len(codes):
            print("当前菜单没有更多通过检查的默认套餐候选。可返回自由组合或切换门店。")
            return
        if input("输入 n 查看下一批，其他输入返回：").strip().lower() != "n":
            return


def menu_prompt(results):
    if not results:
        print("\n欢迎！先创建第一张卡。可以快速挑选默认套餐，也可以自由组合。")
        return "\n8 快速建卡 / 2 自由组合 / 4 切换门店或方式 / 5 重试 / 0 退出："
    available_count = len(card_pool(results))
    if len(results) == 1:
        print("\n已有 1 张卡，可以直接选用；再存一张就能随机选。")
    elif available_count < 2:
        print("\n当前可用卡不足 2 张，可直接选用可用卡，或添加新卡、切换门店。")
    draw_actions = " / 6 全量抽卡 / 7 按标签抽卡" if available_count >= 2 else ""
    return ("\n1 选卡 / 2 自由组合 / 8 快速建卡 / 3 删除卡 / 4 切换门店或方式"
            " / 5 重试检查" + draw_actions + " / 0 退出：")


def main():
    parser = argparse.ArgumentParser(description="先选门店与取餐方式，再检查常用方案")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    store = PresetStore(args.db)
    try:
        client = Client(token_from_local())
        client.initialize()
        while True:
            store_name, context = select_context(client)
            service = Availability(client, context)
            while True:
                print(f"\n当前门店：{store_name}")
                cards = store.list()
                results = service.check(cards) if cards else []
                show_results(results)
                action = input(menu_prompt(results)).strip()
                try:
                    if action == "0":
                        return
                    if action == "4":
                        break
                    if action == "2":
                        save_from_menu(store, service)
                    elif action == "8":
                        quick_start(store, service)
                    elif action == "3":
                        number = positive("删除方案编号：")
                        print("已删除。" if store.delete(number) else "方案不存在。")
                    elif action in {"6", "7"}:
                        if len(card_pool(results)) < 2:
                            print("当前可用卡不足 2 张，请先添加卡片或直接选用已有卡。")
                        else:
                            draw_interactive(results, service, by_tag=action == "7")
                    elif action == "1":
                        available = [r["preset"] for r in results if r["status"] == "available"]
                        if not available:
                            print("没有已确认可选的方案，可重试检查或保存新方案。")
                            continue
                        selected = choose("选择方案：", available, lambda p: f"{p['name']} | {p['tag']}")
                        # Re-check after user input; never reuse stale choices as current.
                        fresh = service.check([selected])
                        if fresh[0]["status"] != "available":
                            show_results(fresh)
                            continue
                        show_card(selected)
                except (ValueError, OSError, sqlite3.Error) as exc:
                    print(f"操作未完成：{str(exc).replace(client.token, '[REDACTED]')}")
    except (ValueError, OSError, sqlite3.Error) as exc:
        print("无法继续，请检查门店选择、网络或本地 Token 配置。")
        raise SystemExit(1) from None
    except (KeyboardInterrupt, EOFError):
        print("\n已退出。")
    finally:
        store.close()


if __name__ == "__main__":
    main()
