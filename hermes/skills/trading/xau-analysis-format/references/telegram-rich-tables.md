# Telegram 真表格发送规则（RichMessage）

## 结论

棠溪要求 Telegram 手机上看到“真真正正的表格”，且明确不要图片表格。普通 `sendMessage`、`parse_mode=MarkdownV2`、HTML `<pre>`、Markdown 管道符原文都不满足。

正确路径是 Telegram Bot API 10.1 Rich Messages：

- Markdown 管道表：`sendRichMessage` + `rich_message.markdown`
- HTML 表格：`sendRichMessage` + `rich_message.html`
- 验证回执必须检查 `result.rich_message.blocks[*].type == "table"`
- 最终不是图片，不是代码块，不是纯文字管道符

## 操作顺序

1. 先生成棠溪标准 3 张窄表内容（每表≤3列）。
2. Telegram 发送时不要用普通 `sendMessage`。
3. 调用 `sendRichMessage`：
   - `chat_id`
   - `message_thread_id`（如果是话题）
   - `rich_message: {"markdown": markdown_text}` 或 `{"html": html_text}`
4. 发送后读取 Bot API 回执，必须确认：
   - `ok == true`
   - `result.rich_message.blocks` 存在
   - 至少一个或多个 block 的 `type` 是 `table`
5. 如果用户反馈仍是文字，优先对比：
   - RichMarkdown 是否被解析成 table block
   - RichHTML `<table>` 是否被解析成 table block
   - 当前 Telegram 手机客户端是否支持渲染 RichBlockTable

## 实测坑点

- 普通 Markdown 管道表：会显示为 `| 品种 | 数据 | 状态 |` 文本，不是用户要的。
- `parse_mode=MarkdownV2`：不支持 GitHub 风格表格。
- `sendRichMessage` 返回 `ok=true` 不够，必须看 `rich_message.blocks`。
- 实测确认：RichMarkdown 单表/多表在“表格前无 standalone 标题行”时可返回 `type: table`；`表1 · xxx` 紧贴表格会导致降级为文字。
- RichHTML `<table>` 可用于诊断服务端 table block，但不是默认格式。

## 推荐路径

当用户明确要求 Telegram 真表格、不要图片时：

- 首选：`sendRichMessage` + `rich_message.markdown`（RichMarkdown 管道表）。
- 输出不要“全是表格”。采用 **首行结论 → 1-2句人话解释 → 编号小标题 → 真表格 → 最终裁决** 的混合结构。
- 首屏必须富文本精排，时间一律北京时间中文格式且放最前：第一行用 RichMarkdown 标题块，例如 `## 2026年7月3日14：41 · BTC`。
- 标题下先写“现在基本情况”（当前状态快照），再给结论：例如 `当前：现价61,890，刚从62,180冲高回落，回踩到VWAP/POC区后反弹；结构位 POC 61,713 · VWAP 61,746 · VAL 61,497。` 下一行再写加粗结论：`**○ 回踩已到，确认不足：等61,900站稳，不追空也不现价追多**`。
- 整体排版侧重点：首屏先“现在发生了什么/价格在哪/贴近哪个结构位”，再“结论/动作”。不要把流程表放在首屏抢重点。后续用 `## ① 结构位`、`## ② 多周期`、`## ③ 订单流`、`## ④ 方案`、`## ⑤ 裁决`。
- 标题可以用 RichMarkdown 标题块（如 `## ① 流程完成度`），标题与表格之间留一个空行；不要用紧贴表格的 standalone `表1 · xxx` 标题行，否则手机端可能降级成文字。
- 每个表保留明确语义：`## ① 流程完成度`、`## ② 多周期定位`、`## ③ 关键位`、`## ④ 交易方案`、`## ⑤ 最终裁决`。这样既有标题/序号，又让表格解析成 RichBlockTable。
- RichHTML `<table>` 只作为诊断/兜底，不作为默认输出；用户已确认正常样式是 `○RichMarkdown解析回执测试` 那种。
- 最终回复不要再解释“Telegram 不支持表格”作为结论；应先尝试 RichMarkdown，并用回执证明。
