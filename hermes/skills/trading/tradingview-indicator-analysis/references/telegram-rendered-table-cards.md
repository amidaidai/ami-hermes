# Telegram 真表格卡协议（已由 RichMarkdown 取代图片方案）

## 当前结论

用户已明确确认：不要图片表格。Telegram 表格必须走 Bot API 10.1 `sendRichMessage` + `rich_message.markdown`，在客户端内直接渲染为原生表格。

## 输出原则

1. 正式方案段优先生成标准 Markdown 管道表，并通过 `rich_message.markdown` 发送。
2. 禁止把普通 `sendMessage` 下的管道符文字称为“真表格”。
3. 禁止把表格截图/PNG 当默认方案；只有用户明确要求图片时才生成。
4. 表格前不要紧贴 standalone `表1 · xxx` 标题行，否则 Telegram 手机端可能降级为文字。
5. 回执必须检查 `rich_message.blocks[type=table]`。

## 推荐形态

```markdown
○BTC执行卡 · 2026年7月3日18：20

| 项 | 数据 | 动作 |
|:--|:----|:----|
| 方向 | 偏多·守VWAP | 等回踩确认 |
| 入场 | `108,000-108,200` | 轻仓试 |
| 风控 | 止损`107,600` | 目标`109,200/110,000` |
```
