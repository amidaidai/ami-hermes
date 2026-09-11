# Studio 与 Telegram 对话表格渲染差异

## 结论

Studio 与 Telegram 当前对话可能不是同一条输出链。Studio 可以直接使用 Rich Message/富文本渲染；普通 Telegram 回复如果走 legacy MarkdownV2，则不会渲染 Markdown 管道表格。

## 权威依据

Hermes 官方 Telegram 文档说明：

- Rich Messages 使用 Telegram Bot API 10.1 的 `sendRichMessage`，原始 Markdown 中的表格可原生渲染。
- MarkdownV2 没有原生表格语法；回退时 Hermes 会把小表格展平为项目符号，较宽表格转为对齐代码块。
- 富消息配置示例为：

```yaml
gateway:
  platforms:
    telegram:
      extra:
        rich_messages: true
        rich_drafts: false
```

来源：<https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram#rendering-rich-messages-tables-and-link-previews>

Telegram Bot API：<https://core.telegram.org/bots/api>

## 诊断清单

1. 确认用户看到的是 Studio 预览、Gateway 普通回复，还是独立 RichMarkdown 投递。
2. 检查配置是否位于当前版本识别的 `gateway.platforms.telegram.extra`，不要只确认旧式顶层 `telegram.extra`。
3. 修改后重启 Gateway；配置通常在进程启动时读取。
4. 若使用独立发送器，确认 `parse_mode="RichMarkdown"`/`sendRichMessage` 实际被调用。
5. 验证 chat_id 与 thread_id；发送成功回执不等于用户所在话题可见。
6. 出现项目符号或代码块时，明确标记为 MarkdownV2 回退，不要称为真表格。

## 本次复现记录

- 普通回复中的管道表在 Telegram 中显示为项目符号。
- Unicode 对齐表放入代码块后只是代码块，不是真表格。
- 独立 RichMarkdown 发送尝试返回 `automated_delivery_disabled`，因此未把未验证的成功投递当作事实。
- 本机配置曾看到 `telegram.extra.rich_messages: true`，但官方当前文档示例使用 `gateway.platforms.telegram.extra`；仅凭配置文件存在不能证明运行中的 Gateway 已加载该开关。
