# Telegram RichMarkdown 真表格协议（2026-07-03）

## 结论

用户确认：Telegram 表格要在客户端内直接渲染为真表格；不要图片表格、不要代码块伪表、不要普通管道符文字、不要 bullet 列表。

正确发送路径：

- Bot API 方法：`sendRichMessage`
- 字段：`rich_message.markdown`
- 内容：标准 Markdown 管道表
- 验证：Bot API 回执里必须出现 `result.rich_message.blocks[*].type == "table"`

普通 `sendMessage` / `parse_mode=MarkdownV2` 不会把管道表渲染成真表格。

## 成功形态

RichMarkdown 表格必须直接位于块边界，表格前不要紧贴 standalone 标题行：

```markdown
○RichMarkdown解析回执测试 · 2026年7月3日18：20

| 品种 | 数据 | 状态 |
|:----|:----|:----|
| BTC | `108,420` · -1.2% | VWAP下方 |
| ETH | `2,425` · -0.8% | 跟随走弱 |
```

回执应包含：

```json
{"type":"table","is_bordered":true,"is_striped":true}
```

## 禁止形态

```markdown
表1 · 行情全景
| 品种 | 数据 | 状态 |
|:----|:----|:----|
```

`表1 · xxx` / `表2 · xxx` / `表3 · xxx` 这类 standalone 标题紧贴表格时，Telegram 手机端可能降级为文字。表名语义可放首行结论、表头或单元格内，不要作为独立标题段落。

**⚠ 2026-08-29 实战补强：standalone 标题不只在 `表X ·` 前缀。任何独立标题行（`**当前基本情况**`、`## 多周期定位`、`<h3>`）紧贴表格块都会把整块降级成 paragraph/bullet。** 本次一个 8 张表的完整驾驶舱卡两次推送失败（用户「不是表格」），根因就是每张表前都放了一个 `**章节名**` 粗体标题行。`telegram_reliable.py::_normalize_rich_markdown_tables()` **只剥离 `表X ·` 前缀标题，不会剥离 `**粗体**` 标题**——写卡时必须自查：每张表直接从 `| 表头 |` 顶格开始，前面只允许空行；标题语义交给表头列名承载，整个卡片开头可放一句非表格结论（第0行）。

## TradingView 卡片约束

| 场景 | 格式 |
|:----|:----|
| 非完整卡/告警/cron | 首行结论 + 恰好3张≤3列 RichMarkdown 表 |
| 完整驾驶舱发 Telegram | 优先压缩成手机三表版，避免4列以上宽表 |
| 本地/网页报告 | 可保留完整驾驶舱宽表 |
| 加密/XAU 更新 | 仍必须先发 TradingView full 截图，文字卡走 RichMarkdown |

## 发送器要求

1. 检测 Markdown 管道表。
2. 命中后走 `sendRichMessage`，不是 `sendMessage`。
3. 发送前自动剥离紧贴表格的 `表1 · xxx` / `表2 · xxx` / `表3 · xxx` 标题行。
4. 保留首行结论与表格本体。
5. 检查回执 table block；没有 table block 视为格式未成功。
