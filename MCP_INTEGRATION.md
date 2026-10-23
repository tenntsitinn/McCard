# MCP 接入与字段调查

## 2026-10-21 前端建卡数据复核

22:45 再次通过真实 MCP 查询惠州华贸餐厅（1420219，到店自取）。业务成功，返回 108 个餐品。`data.categories[].meals[].code` 关联 `data.meals[code]`，后者提供 name、image、currentPrice、originalPrice，以及可选的 discountType、canWithOrder、withOrder。

实测巨无霸：currentPrice="25.5"，image=https://menu-img.mcd.cn/pcm/prod/menu/20260309/product/MS_1100_320.png。巨无霸三件套：currentPrice="36.5"、originalPrice="49"，同样有官方图片 URL。已直接请求巨无霸图片，确认响应为 image 类型且 PNG 文件签名正确；浏览器实际渲染尚未验证。

因此菜单浏览所需的名称、分类、图片链接和展示价格已可取得。选择餐品后再按需查询详情以配置套餐及特调；保存方案复用现有结构，不固化图片和价格。展示价不等于核价结果，会员随单购需展示条件。菜单价格单位仍应按前述未确认事项处理。

前端通过项目后端获取整理后的菜单，MCP API Key 只保留在服务器内存会话中。建卡时可读取最近订单，或浏览固定参考菜单并完成详情配置；用卡时再选择门店和取餐方式，重新检查卡牌、实时核价，并在用户明确确认后创建待支付订单。

## 项目实际使用的 MCP Tools

| Tool | McCard 中的用途 |
|---|---|
| `order-list` | 读取最近 10 笔订单，去重生成最多 3 张卡牌 |
| `query-nearby-stores` | 按城市、关键词与取餐方式查找可用门店 |
| `query-meals` | 获取参考菜单或实际用卡门店菜单 |
| `query-meal-detail` | 读取套餐轮次、子项和特调选项 |
| `calculate-price` | 对当前门店中的整张卡牌进行实时核价 |
| `create-order` | 用户确认金额与取餐方式后创建待支付订单 |

调用流程：个人 MCP API Key 接入 → 最近订单建卡或参考菜单自定义建卡 → 本地保存方案 → 选择实际餐厅 → 查询菜单与详情并校验 → 随机或手动选择卡牌 → 实时核价 → 用户确认 → 创建待支付订单 → 跳转麦当劳支付页面。

业务价值：将重复点单配置沉淀为可复用卡牌，同时保留门店、菜单、价格和特调的实时校验，减少重复操作，也避免把历史展示价或其他门店的供应情况当作当前结果。

同日已通过网页后端 WebApp 完成真实接口验收：惠州华贸餐厅的 108 款菜单 → 巨无霸三件套详情 → 可乐去冰 → 保存前刷新校验 → 临时 SQLite 保存及读回，状态 available，未向正式卡库写入测试数据。内置浏览器自动化因环境初始化错误未完成视觉和点击验收。

官方接入说明：https://github.com/M-China/mcd-mcp-server

接入地址 `https://mcp.mcd.cn`，协议为 Streamable HTTP，使用 Bearer Token。
项目 `mcp_probe.py` 是最小只读探查客户端，不是完整通用 MCP SDK；
支持初始化、会话头、JSON/SSE 响应、工具列表分页和指定查询。
不会自动重试业务调用，不包含下单、领券等操作。

## 本地使用

在项目 `.env` 文件填入 `MCD_TOKEN=...`，或设置同名环境变量。
`.env` 和 `data/` 已被 Git 忽略，不提交凭据和原始账户数据。

```powershell
python mcp_probe.py
python mcp_probe.py --tool query-nearby-stores --arguments data/mcp/store-args.json
python mcp_probe.py --tool query-meals --arguments data/mcp/menu-args.json
python mcp_probe.py --tool query-meal-detail --arguments data/mcp/detail-args.json
```

参数文件必须根据实时 `tools/list` 定义填写；探查结果保存到 `data/mcp/`。

## 2026-10-20 已验证

- 初始化和 `tools/list` 成功，服务端返回 35 个工具。
- `query-nearby-stores` 实际调用成功，但业务返回 `success=false`、错误码
  `600050`：收藏门店列表为空，需要城市与关键词搜索。
- 工具级 `isError=false` 不代表业务成功，必须同时检查 `structuredContent.success`。
- 已按用户指定的“惠州 华贸天地”完成门店、菜单、套餐及单品详情查询，见下文。

## 服务端声明的字段

| 工具 | 输入与数据 |
|---|---|
| `query-nearby-stores` | 必填 `beType`、`searchType`；支持 `city`、`keyword`；输出门店编码、名称、地址、营业状态等 |
| `query-meals` | 必填 `storeCode`、`orderType`、`beType`；输出分类、餐品 code、餐品映射中的名称、图片、字符串价格、随单购信息等 |
| `query-meal-detail` | 在门店和业务上下文外，必填餐品 `code`；输出 `rounds` 选配轮次、choices、默认项、数量限制、特调选项 |
| `calculate-price` | 商品使用 `productCode` 与 `quantity`；套餐使用 `roundList[].round`、`comboItemList`；特调使用 code/key/quantity |

重要差异：

- 菜单餐品标识叫 `code`，核价参数叫 `productCode`。
- 详情轮次 `id` 为整数，核价的 `round` 为字符串。
- `currentPrice` / `originalPrice` 在菜单 schema 中为字符串，单位尚待实测，
  不能直接当整数分入库。
- 核价 schema 的主要金额字段为整数分，但嵌套 `realDiscount` 明确描述为元，
  不可把所有价格字段统一按分解释。
- 特调有 `selectedKey` 和 `unselectedKey`，不能只保存一个“去冰”文本。
- 菜单带有门店与取餐业务上下文，不能把商品编码当作脱离上下文的全国统一标识。

## 真实样本：惠州华贸餐厅

查询时间：2026-10-20 12:32–12:34（北京时间）。
门店 `1420219`，地址为江北文昌一路九号惠州华贸天地 B1 层 0110 号商铺。
使用 `orderType=1`、`beType=1`（到店自取），不传 `beCode`。

菜单成功返回 15 个分类、110 个不同餐品编码。

| 餐品 | code | currentPrice 原始字符串 | originalPrice 原始字符串 |
|---|---|---|---|
| 巨无霸 | `1100` | `"25.5"` | `"25.5"` |
| 巨无霸三件套 | `9900005466` | `"36.5"` | `"49"` |
| 巨无霸四件套 | `9900000888` | `"32"` | `"58.5"` |

四件套同时返回 `discountType="随单购麦金卡优惠"`、
`canWithOrder=true` 和 `withOrder` 会员信息，不能把价格当成无条件报价。
这些是菜单快照，未调用 calculate-price 确认应付金额。
价格字符串形态符合元的展示形式，但菜单 schema 未标明单位；保存时先保留原始字符串及来源。

巨无霸单品详情：`rounds=[]`，`supportModify=true`，顶层 `modification`。
套餐详情：顶层 `supportModify=false`，但子项可以支持特调：

| round id | 默认选项 | code | 数量 |
|---|---|---|---|
| 1 | 巨无霸 | `1100` | 1 |
| 2 | 中薯条 | `4810` | 1 |
| 3 | 可乐中杯 | `3050` | 1 |

实测结构中需要特别处理：

- 可乐的标准、去冰、多冰、少冰使用相同 `code=200002`，但不同
  `selectedKey`（`0-1`、`0-0`、`0-2`、`1-1`）。不能按 code 单独去重。
- 汉堡配料使用 `selectedKey=0-1`、`unselectedKey=0-0`；
  对存在 unselectedKey 的未选项，后续核价也需要传值。
- 选项 `maxQuantity=-1` 实际存在，不能擅自当作非法数量或推定其含义。
- 差价是展示字符串，例如 `"+ ¥2.5"`，不适合作为核价依据。
- 套餐是否需要展开应看 rounds，不能靠名称含“套餐”或 supportModify 判断。

原始结果位于 Git 忽略的 `data/mcp/`：
`query-meals.json`、`combo-detail.json`、`query-meal-detail.json`（巨无霸单品）。

## 保存结构（已实现）

区分“用户选择”与“查询时的可选项快照”，不要把整份菜单当成方案：

```text
方案
  id / name / tag / created_at
  items[]
    productCode / name / quantity
    modification.values[]: code / key / quantity（单品已选特调）
    roundList[]（套餐已选搭配）
      round（字符串）
      comboItemList[]: code / name / quantity / modification
```

设计依据：

- 门店与业务上下文仅属于当前使用会话，不属于方案，不写入数据库。
- 用户自定义 `tag` 与菜单自带的 `tags` 分开。
- 核价字段结构尽量沿用服务端入参；名称等展示字段不直接发送给核价接口。
- 图片、展示价与完整详情目前不写入方案，每次使用重新查询。
- 旧文本方案通过缺少 productCode 识别，不通过名称猜测商品编码。
- 原始调查快照仅在本地 data/mcp 中保留，与用户保存的方案分开。

## 当前运行流程

`app.py` 提供交互入口：

1. 用户选择到店自取或得来速，再搜索并选择营业中的门店。
2. 当前会话创建 context：storeCode、orderType、beType；
   得来速额外使用该门店返回的 beCode。
3. `availability.py` 查询菜单，检查所有方案涉及的商品；
   同一轮按商品编码缓存详情，不同门店或重试时重新查询。
4. 检查套餐轮次、子项与特调 code/key/quantity，输出三个状态及原因。
5. 用户选择方案前已看到检查结果；选择完成时再检查一次以减少过时结果。
6. 新方案从实时菜单选择，可修改搭配和特调，保存后仍保持与门店无关。

网页支持到店自取和得来速的即时取餐场景，不包含预约和外送；已实现核价与创建待支付订单，最终支付由麦当劳页面完成。
没有明确库存字段，因此“可选”只能表示当前菜单与选项兼容。
本版本对未知字段限制、查询失败或会员随单购条件采用“暂未确认”，不假定可用。

2026-10-20 已对惠州华贸餐厅完成真实只读联调：
巨无霸单品、巨无霸三件套默认搭配均经过“取详情 → 临时库保存 → 实时检查”，
结果均为 `available`。测试库已自动清理，没有向用户方案库写入示例方案。
