# Telegram 手机端 Markdown 表格渲染结论

## 核心结论

Telegram Bot 可以发送 Markdown/MarkdownV2，但普通 `sendMessage` 的 Markdown/MarkdownV2 **不支持 GitHub Flavored Markdown 管道表渲染成网格表格**。`| A | B |` 只会作为文本显示；手机端会因为窄屏换行、等宽字体过小或列宽过长导致可读性差。

## 社区/官方验证

| 来源 | 验证结论 | 实操含义 |
|:----|:----|:----|
| Telegram Bot API MarkdownV2 | 支持粗体、斜体、链接、代码块、引用等；未列出 GFM table | `parse_mode=MarkdownV2` 不能把管道表变成表格 |
| StackOverflow Telegram table 问题 | 常见兜底是 HTML `<pre>`/代码块；社区指出 smartphone small screens 不好用，建议转图片 | 手机端正式推送不要依赖代码块伪表 |
| Hermes 社区 issue #14160 | 明确说明 Telegram does not support markdown tables natively；管道表包进 code block 后 mobile UX 差 | 不能把“管道符文本”冒充 TG 真表格 |
| Telegram Bot API 10.1 / RichBlockTable | 新增 rich message / table block，理论上可原生表格 | 需要发送管道接入 `sendRichMessage`，普通 sendMessage 不会自动生效 |
| telegramify-markdown | 可把 Markdown 转 Telegram entities；新版提到 richify | entities 可改善 Markdown 转义，但普通 Markdown 表格仍需 rich/image 方案 |

## 渠道策略

| 场景 | 标准 |
|:----|:----|
| Telegram 正式交易/情绪/Orion 推送 | 优先生成图片表格卡：标题 + 2/3 列卡片 + 边框/行距，手机可读 |
| Telegram 文本兜底 | 保留恰好 3 张 Markdown 管道表作为结构化文本，但明确只是兜底，不承诺客户端渲染成表格 |
| Telegram 新能力 | 研究/接入 Bot API 10.1 `sendRichMessage` / `RichBlockTable` 后，Markdown 管道表可转原生 rich table |
| 飞书 | 继续走 sidecar 卡片，支持真表格视觉 |
| 本地/网页/报告 | 保留 Markdown 管道表 |

## 执行铁律

1. 用户在手机端看 Telegram 时，目标是“视觉真表格”，不是“语法上有管道符”。
2. 不要再把管道符文本解释成已经满足 Telegram 表格渲染；必须说明它只是 Markdown 结构。
3. 若用户要求 TG 表格像截图/手机卡片一样可读，优先做图片卡或 RichBlockTable，而不是继续调 `parse_mode`。
4. `parse_mode=MarkdownV2` 可用于粗体/链接/代码等格式，但不是表格解决方案。
