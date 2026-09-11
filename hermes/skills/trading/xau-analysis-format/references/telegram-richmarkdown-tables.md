# Telegram RichMarkdown 真表格发送规则

## 结论

Telegram 手机端要显示“真表格”，不要图片、不要代码块、不要普通管道符文本，必须走 Bot API 10.1：

- 方法：`sendRichMessage`
- 字段：`rich_message.markdown`
- 内容：标准 Markdown 管道表

普通 `sendMessage` + `parse_mode=MarkdownV2` 不会把管道表渲染为表格。

## 已验证成功形态

能正常渲染的 RichMarkdown 表格必须让管道表直接位于块边界：

```markdown
○RichMarkdown解析回执测试 · 2026年7月3日18：20

| 品种 | 数据 | 状态 |
|:----|:----|:----|
| BTC | `108,420` · -1.2% | VWAP下方 |
| ETH | `2,425` · -0.8% | 跟随走弱 |
```

Telegram API 回执应包含：

```json
{
  "type": "table",
  "is_bordered": true,
  "is_striped": true
}
```

## 关键坑

不要在表格前紧贴 standalone 标题行：

```markdown
表1 · 行情全景
| 品种 | 数据 | 状态 |
|:----|:----|:----|
```

这种格式在 Telegram RichMarkdown 下会导致手机端降级为纯文字。标题可放在首行结论里，或放入表头/单元格，但不要作为紧贴表格的独立段落。

## 发送器要求

发送前应做一次归一化：

1. 检测 Markdown 管道表。
2. 命中后走 `sendRichMessage`，不是 `sendMessage`。
3. 若发现 `表1 · xxx` / `表2 · xxx` / `表3 · xxx` 紧贴表格，自动剥离标题行。
4. 保留表格本体和首行结论。
5. 回执中检查 `rich_message.blocks` 是否包含 `type: "table"`。

## 棠溪格式偏好

- 不要图片表格。
- 不要代码块伪表。
- 不要普通管道符文字冒充表格。
- Telegram 正式推送必须是真 RichMarkdown 表格。
- 新会话/cron prompt 要内嵌这个规则，不能让子 agent 自由发挥。
