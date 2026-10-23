"""Compare saved choices with a freshly fetched menu; never infer stock."""

from copy import deepcopy
from datetime import datetime, timezone


def validate_item(item):
    """Validate the persisted selection shape, without binding it to a store."""
    def quantity(value):
        if type(value) is not int or value < 1:
            raise ValueError("餐品数量必须为正整数。")

    def modification(value):
        if not isinstance(value, dict) or set(value) != {"values"} or not isinstance(value["values"], list):
            raise ValueError("特调格式应为 modification.values 数组。")
        for option in value["values"]:
            if not isinstance(option, dict) or set(option) != {"code", "key", "quantity"}:
                raise ValueError("特调需要 code、key 和 quantity。")
            if not all(isinstance(option[k], str) and option[k] for k in ("code", "key")):
                raise ValueError("特调 code 和 key 不能为空。")
            if type(option["quantity"]) is not int or option["quantity"] < 0:
                raise ValueError("特调数量必须为非负整数。")

    def product(value, root=False):
        allowed = {"name", "quantity", "modification", "productCode" if root else "code"}
        if root:
            allowed.update({"roundList", "historyChoices", "needsConfiguration"})
        if not isinstance(value, dict) or set(value) - allowed:
            raise ValueError("餐品含不支持的字段；门店和取餐方式不能存入方案。")
        if not isinstance(value.get("name"), str) or not value["name"].strip():
            raise ValueError("餐品名称不能为空。")
        quantity(value.get("quantity", 1))
        key = "productCode" if root else "code"
        if key in value and (not isinstance(value[key], str) or not value[key]):
            raise ValueError("商品编码必须是非空字符串。")
        if not root and key not in value:
            raise ValueError("套餐子项缺少商品编码。")
        if "modification" in value:
            modification(value["modification"])

    product(item, True)
    if 'needsConfiguration' in item and type(item['needsConfiguration']) is not bool:
        raise ValueError('配置确认标记无效。')
    if 'historyChoices' in item:
        if not isinstance(item['historyChoices'], list) or item.get('needsConfiguration') is not True:
            raise ValueError('历史子项必须保持待确认状态。')
        for choice in item['historyChoices']:
            product(choice)
    if "roundList" in item:
        if not isinstance(item["roundList"], list):
            raise ValueError("roundList 必须是数组。")
        seen = set()
        for group in item["roundList"]:
            if not isinstance(group, dict) or set(group) != {"round", "comboItemList"}:
                raise ValueError("套餐轮次需要 round 和 comboItemList。")
            if not isinstance(group["round"], str) or not group["round"] or group["round"] in seen:
                raise ValueError("套餐轮次必须为不重复的字符串。")
            seen.add(group["round"])
            if not isinstance(group["comboItemList"], list):
                raise ValueError("套餐子项必须是数组。")
            codes = set()
            for choice in group["comboItemList"]:
                product(choice)
                if choice["code"] in codes:
                    raise ValueError("同一轮次的重复餐品请合并数量。")
                codes.add(choice["code"])
    return deepcopy(item)


def business_data(response):
    body = response.get("structuredContent")
    if response.get("isError") or not isinstance(body, dict):
        raise ValueError("接口未返回可确认的结构化数据")
    if body.get("success") is not True or "data" not in body:
        raise ValueError("接口业务查询失败")
    return body["data"]


def default_modification(detail):
    values = []
    for group in detail.get("modification", {}).get("items", []):
        for option in group.get("values", []):
            count = option.get("selectedQuantity", 0)
            key = option.get("selectedKey") if count else option.get("unselectedKey")
            if key is not None:
                values.append({"code": option["code"], "key": key, "quantity": count})
    return {"values": values}


def default_item(detail, quantity=1):
    def selection(data, code_key):
        result = {code_key: data["code"], "name": data["name"], "quantity": 1}
        if data.get("modification"):
            result["modification"] = default_modification(data)
        return result
    result = selection(detail, "productCode")
    result["quantity"] = quantity
    result["roundList"] = []
    for group in detail.get("rounds", []):
        choices = []
        for choice in group.get("choices", []):
            if choice.get("isDefault") == 1:
                # MCP can flag a default choice with zero quantity. It is not
                # a selected item; leave the round open for the user to fill.
                if type(choice.get("quantity")) is int and choice["quantity"] == 0:
                    continue
                selected = selection(choice, "code")
                selected["quantity"] = choice["quantity"]
                choices.append(selected)
        result["roundList"].append({"round": str(group["id"]), "comboItemList": choices})
    return validate_item(result)


def check_item(item, detail):
    """Return definite incompatibilities and unresolved schema limitations."""
    problems, unknown = [], []

    def limits(count, spec, lower, upper, label):
        lo, hi = spec.get(lower), spec.get(upper)
        if type(lo) is not int or type(hi) is not int:
            unknown.append(f"{label}：接口缺少数量限制")
            return
        if count < lo or (hi >= 0 and count > hi):
            problems.append(f"{label}：数量不符合当前限制")
        # -1 is present in live choices; group bounds still apply. Do not
        # claim an unsupported interpretation of this sentinel.
        if hi < 0:
            unknown.append(f"{label}：单项数量上限为 {hi}，含义未确认")

    def modifications(selected, current, label):
        values = selected.get("modification", {}).get("values", [])
        groups = current.get("modification", {}).get("items", [])
        if "supportModify" not in current:
            unknown.append(f"{label}：特调支持状态缺失")
        if not groups:
            if values:
                problems.append(f"{label}：当前不支持保存的特调")
            elif current.get("supportModify"):
                unknown.append(f"{label}：缺少特调选项")
            return
        if current.get("supportModify") is False and values:
            problems.append(f"{label}：当前不支持特调")
            return
        consumed = set()
        for group in groups:
            selected_count = 0
            for option in group.get("values", []):
                matches = [
                    (index, value) for index, value in enumerate(values)
                    if value["code"] == option.get("code")
                    and value["key"] in {option.get("selectedKey"), option.get("unselectedKey")}
                ]
                if len(matches) > 1:
                    problems.append(f"{label}：特调重复")
                for index, value in matches:
                    consumed.add(index)
                    if value["key"] == option.get("selectedKey"):
                        limits(value["quantity"], option, "minQuantity", "maxQuantity", label)
                        selected_count += int(value["quantity"] > 0)
                    elif value["quantity"] != 0:
                        problems.append(f"{label}：未选特调的数量应为 0")
                if not matches and option.get("unselectedKey") is not None:
                    problems.append(f"{label}：缺少配料的明确选择")
            limits(selected_count, group, "minValues", "maxValues", label)
        if len(consumed) != len(values):
            problems.append(f"{label}：保存的特调选项已不存在")

    modifications(item, detail, item["name"])
    if not isinstance(detail.get("rounds"), list):
        unknown.append("接口缺少套餐轮次信息")
        return problems, unknown
    current_rounds = {str(group["id"]): group for group in detail["rounds"]}
    selected_rounds = {group["round"]: group for group in item.get("roundList", [])}
    for round_id in selected_rounds.keys() - current_rounds.keys():
        problems.append(f"套餐轮次 {round_id} 已不存在")
    for round_id, group in current_rounds.items():
        choices = selected_rounds.get(round_id, {}).get("comboItemList", [])
        limits(sum(c["quantity"] for c in choices), group, "minQuantity", "maxQuantity", group["name"])
        options = {c["code"]: c for c in group.get("choices", [])}
        for choice in choices:
            current = options.get(choice["code"])
            if current is None:
                problems.append(f"{choice['name']}：当前套餐不支持此搭配")
                continue
            # A group with max=1 already proves a quantity of 1 cannot
            # exceed a meaningful positive per-choice limit.
            hi = current.get("maxQuantity")
            if hi == -1 and group.get("maxQuantity") == 1 and choice["quantity"] == 1:
                pass
            else:
                limits(choice["quantity"], {"minQuantity": 0, "maxQuantity": hi},
                       "minQuantity", "maxQuantity", choice["name"])
            modifications(choice, current, choice["name"])
    return problems, unknown


class Availability:
    def __init__(self, client, context):
        self.client = client
        self.context = dict(context)
        self.details = {}
        self.menu = None

    def load_menu(self):
        data = business_data(self.client.call("query-meals", self.context))
        if not isinstance(data, dict) or not isinstance(data.get("meals"), dict):
            raise ValueError("菜单结构不完整")
        self.menu = data["meals"]
        return self.menu

    def detail(self, code):
        if code not in self.details:
            try:
                data = business_data(self.client.call(
                    "query-meal-detail", self.context | {"code": code}))
                if not isinstance(data, dict) or data.get("code") != code:
                    raise ValueError("餐品详情编码不匹配")
                self.details[code] = data
            except (ValueError, OSError):
                self.details[code] = None
        return self.details[code]

    def check(self, presets, *, defer_promotions=False):
        self.details = {}  # cache only within this fresh check
        checked_at = datetime.now(timezone.utc).isoformat()
        try:
            self.load_menu()
        except (ValueError, OSError):
            return [dict(preset=p, status="unknown", reasons=["菜单查询失败，请重试"],
                         checkedAt=checked_at) for p in presets]
        results = []
        for preset in presets:
            problems, unknown = [], []
            for item in preset["items"]:
                code = item.get("productCode")
                if not code:
                    unknown.append(f"{item['name']}：旧文本方案缺少商品编码")
                elif code not in self.menu:
                    problems.append(f"{item['name']}：当前门店及取餐方式的菜单未提供")
                elif item.get('needsConfiguration'):
                    unknown.append(f"{item['name']}：历史订单缺少完整特调或套餐轮次，请先确认配置")
                elif not defer_promotions and (self.menu[code].get("canWithOrder") or self.menu[code].get("withOrder")):
                    unknown.append(f"{item['name']}：包含随单购条件，当前版本无法确认")
                else:
                    detail = self.detail(code)
                    if detail is None:
                        unknown.append(f"{item['name']}：详情查询失败")
                    else:
                        try:
                            bad, unsure = check_item(item, detail)
                            problems.extend(bad)
                            unknown.extend(unsure)
                        except (KeyError, TypeError, AttributeError):
                            unknown.append(f"{item['name']}：详情字段不完整，无法确认")
            status = "adjust" if problems else ("unknown" if unknown else "available")
            results.append(dict(preset=preset, status=status, reasons=problems + unknown,
                                checkedAt=checked_at))
        return results
