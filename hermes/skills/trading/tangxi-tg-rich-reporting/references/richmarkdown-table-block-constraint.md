# RichMarkdown 真表格块约束 — 2026-08-29 实战根因

## 现象
用户连续两次说「不是表格」：`sendRichMessage` + RichMarkdown 已推，但 Telegram 客户端把整张表渲染成 `| a | b |` 裸文本 / bullet 列表，而非原生表格块。

## 根因
**表格前紧贴了 standalone 章节标题行**。Bot API 10.1 `sendRichMessage` 解析 markdown 管道表成 `RichBlockTable` 时，要求表格块从块边界**干净开始**。若表头行前还有任何非表头文本行（即使是 `**当前基本情况**` 这种纯 Markdown 粗体标题行），解析器会把整块当段落文本，**不生成表格块**。

第一次踩坑误判为「表X · xxx」前缀行问题——`telegram_reliable.py::_normalize_rich_markdown_tables()` 只剥 `表X ·` 前缀（`cur.startswith("表") and "·" in cur`），**完全不会剥 `**XX**` 粗体标题**。所以剥完前缀后，粗体标题仍留在表头前 → 表格仍烂。**真正的凶手是粗体标题行，不是 `表X ·` 前缀。**

## 修复（正确输出形态）
```markdown
🛡 BTC 到价监控已就绪 · 静默等触发 · 2026年8月29日10：40
                                    ← 空行在这里，标题之后、表格之前
| 守护 | 状态 |
|:---|:---|
| 实时守位 | ✅ PID 16292 · 0.5s轮询 |
                                    ← 表与表之间空行
| 监测位 | 价位 | 到价动作 |
|:---|:--:|:---|
| 反抽POC·空触发 | 77,752 | 反抽回落放量→空 |
```
规则：
- **每张表直接从 `| 表头 |` 顶格开始**，不允许表头前有任何文本行（含粗体标题、`## `、`<h3>`、`表X ·`）。
- 表与表之间用**空行**分隔。
- 标题语义交给**表头列名**承载（`当前基本情况|数据`、`周期|方向`），不要用独立标题行。
- 开头结论行（`🛡 已就绪`）之后必须有空行再进入第一张表。

## 验证方法
1. **monkeypatch 检查 payload**（推荐，无需真发）：
```python
import sys; sys.path.insert(0,'scripts')
import telegram_reliable as tr
calls=[]
orig=tr._post_json
def spy(method,payload,token,timeout):
    calls.append((method, payload.get('rich_message',{}).get('markdown','') if 'rich_message' in payload else payload.get('text','')))
    return True,'spy'
tr._post_json=spy
tr.push_tg_rich('telegram:-1003733144325:386', text)
# 断言：calls[0][0]=='sendRichMessage'，且 markdown 里每张表头行前紧邻的上一行不是非空文本行
```
2. **客户端人工确认**：真发后看渲染是否成原生表格。若成段落/bullet → 表头前还有残留标题行。
3. 回执 `rich_sent` 只说明消息送达，**不代表表格块被解析**——必须靠上面两步或客户端目检确认。

## `rich_sent` 返回值的陷阱（2026-08-31 新）
`push_tg_rich()` 返回 `(True, "rich_sent")` **不代表送达正确 thread**，仅代表 HTTP 200、Telegram 接受 payload。但曾出现：返回 `rich_sent`（HTTP 200）而消息实际发到了 thread=846（Home），用户（thread=386）完全看不到。

**教训**：
1. `rich_sent`/`photo_sent` 返回 `True` ≠ 用户收到。返回值只说明 Telegram API 层接收，不验证目标 thread 是否正确。
2. **唯一可靠验证**：推送后用户人工确认，或观察 `data/pending_telegram.jsonl` 确认该条不在其中（pending 落盘 = 真正失败，不落盘 = 至少发出）。
3. **根本解法**：target 必须取当前会话 thread（动态），禁止硬编码 846（后台 cron 除外）。

## 相关函数
- `telegram_reliable.py::push_tg_rich(target, text)` — 统一入口，内部 `parse_mode="RichMarkdown"`。
- `telegram_reliable.py::_normalize_rich_markdown_tables(text)` — 只剥 `表X ·` 前缀，**不剥粗体标题**（这是本次误判的坑）。
- 若未来要更稳，可增强 `_normalize_rich_markdown_tables` 同时剥 `**...**`/`## ` 紧贴表头的行；但当前规范已改为「不用独立标题、标题语义进表头」，从源头规避。
