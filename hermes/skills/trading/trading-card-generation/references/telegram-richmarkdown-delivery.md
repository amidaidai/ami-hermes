# Telegram RichMarkdown 真表格投递管线

## 问题

棠溪的 Bot `@anheauberon_bot` 支持 Telegram Bot API 10.1 `sendRichMessage`（RichMarkdown 真表格渲染），但以下场景会收到纯文本 `|` 竖线而非真表格：

1. **`hermes send` 投递** — Hermes CLI 的 `send` 命令发的是 `sendMessage`（纯文本），不支持 parse_mode。cron 的 no-agent 模式（stdout 直发）走的就是此路径。
2. **`auto_card.py` 推送段** — 第 3573-3584 行调用 `hermes_cli.main send`，同样纯文本。
3. **助手普通回复** — 在聊天对话中粘贴表格文本，Telegram 会降级成项目符号。

## 正确通路

```python
from scripts.telegram_reliable import send_telegram_reliable

ok, reason = send_telegram_reliable(
    target='telegram:-1003733144325:846',   # chat_id:thread_id
    text=card_content,
    parse_mode='RichMarkdown',               # 关键：触发 sendRichMessage
    timeout=20,
    retries=3,
    persist_on_fail=True,
)
# ok=True, reason='rich_sent'  → 真表格渲染成功
# ok=True, reason='sent_plain_after_rich_fail:...'  → RichMarkdown降级为纯文本但仍送达
# ok=False → 发送失败，已落盘 data/pending_telegram.jsonl
```

`scripts/telegram_reliable.py` 的 `send_telegram_reliable()` 会自动：
- 检测文本是否含 Markdown 管道表（自动路由到 `sendRichMessage`）
- `parse_mode='RichMarkdown'` 时强制走新端点
- 如果 `sendRichMessage` 失败（如旧版 Bot API），自动降级到 `sendMessage` + 标注 `sent_plain_after_rich_fail`
- 3 次重试 + 指数退避
- 持久化失败消息到 `data/pending_telegram.jsonl`
- 按行解析 `telegram:` 目标格式（支持 `thread_id`）

## 关键修复点

### `auto_card.py` 推送段（行 3573-3584）

**当前**：
```python
import subprocess
subprocess.run([
    sys.executable, "-m", "hermes_cli.main", "send",
    "-t", target,
    "-q", msg
], timeout=15, capture_output=True)
```

**应改为**：
```python
from scripts.telegram_reliable import send_telegram_reliable
ok_text = card[:4096]  # RichMarkdown消息上限
if screenshot_path:
    ok_text += f"\nMEDIA:{screenshot_path}"
send_telegram_reliable(target, ok_text, parse_mode='RichMarkdown',
                       timeout=20, retries=3, persist_on_fail=True)
```

### TG 推送 cron（no-agent 模式）

所有 deliver: `telegram:-1003733144325:846` 的 cron 走的是 `hermes send` 纯文本。要发 RichMarkdown 表，cron 脚本必须自己调用 `telegram_reliable.send_telegram_reliable()` 并且**不依赖 stdout 投递**（脚本 stdout 只写调试日志，或改为 `deliver: local` 不投递）。

## 配置文件

`~/.hermes/.env` → `TELEGRAM_BOT_TOKEN=8787073936:***`
`~/.hermes/config.yaml` → `telegram.extra.rich_messages: true`

`telegram_reliable.py` 自动从 `%LOCALAPPDATA%/hermes/.env` 读取 token。

## 常用话题 ID

| 目标 | topic ID |
|:----|:--------:|
| 阿弥黛黛 / 846（主推） | `-1003733144325:846` |
| 阿弥黛黛 / 386（BTC卡） | `-1003733144325:386` |
| 阿弥黛黛 / 385（XAU卡） | `-1003733144325:385` |
