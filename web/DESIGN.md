# 前端视觉规范

2026-10-22：根据用户指定的 https://www.mcdonalds.com.cn/ 调整本地建卡网页。

参考 skill：https://github.com/anthropics/skills/tree/main/skills/frontend-design 。本次直接阅读并应用，没有全局安装。

官网样式来源：https://www.mcdonalds.com.cn/files/css/base.min.css?v=2026-01-12 。只读检查官网 HTML/CSS，不引入官网脚本、跟踪代码或活动文案。

## 视觉规则

- 金黄 #ffbc0d：主视觉、主要选择按钮、当前分类和步骤。
- 红色 #db0007：主视觉入口及保存操作。
- 白色 #ffffff：页面、导航及表单。
- 深灰 #2d2d2d：正文和标题。
- 浅灰 #f7f7f7：次要容器及输入背景；边线 #e4e4e4。
- 中文使用 Microsoft YaHei / PingFang SC，西文回退 Arial。标题加粗，正文不添加装饰性字距。
- 导航 → 金黄主视觉（保留项目原创像素卡）→ 建卡步骤 → 门店条 → 菜单与搭配侧栏。
- 将原有奶油色全页、零散装饰标签收敛为品牌色主视觉，功能区保持白色，优先让用户辨认选择和保存操作。
- 小屏采用单列；保留焦点标识、表单标签和减少动态效果支持。

## 卡阵首页文字层级

参考 [Carbon 字号体系](https://www.carbondesignsystem.com/building-blocks/foundations/typography/type-sets) 的字号与行高档位，按本页中文主副标题关系调整，并非规范强制配对。以下 px 数值按默认根字号 16px 换算；实现使用 rem，支持用户字体设置。

- 桌面：主标题 36px / 44px 行高，副标题 22px / 32px 行高。
- 手机（宽度 ≤600px）：主标题 28px / 36px 行高，副标题 18px / 27px 行高。
- 矮桌面窗口（宽度 >600px、高度 ≤650px）：主标题 32px / 40px 行高，副标题 20px / 30px 行高。
- 主标题字重 700，副标题常规字重；不添加额外字距，两行间距 12px。

## 本次验证

JavaScript 语法检查通过；页面 ID 唯一，所有脚本引用的 ID 和页内导航锚点均存在。没有修改 MCP、数据库或保存校验逻辑。
当前浏览器工具仅能发现 MCP Apps，无法获取网站截图，因此未完成真实浏览器视觉及小屏截图验收。
