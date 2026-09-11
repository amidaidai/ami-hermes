# TG 报告 RichMarkdown 真表格一致性（2026-07-08 棠溪确认）

## 铁律
所有推 `telegram:-1003733144325:846` 的定时任务报告（审计/任务盘点/运维聚合/Orion雷达/守护看门狗/复盘提醒/X情绪LLM）**必须用 RichMarkdown 真表格投递**，禁止退化为裸 `|` 文本。用户原话：「这个才对，其他的任务报告，也是这种的格式才对」。

## 为什么 cron no_agent stdout 投递会退化
`hermes cron` 的 no_agent 模式把脚本 stdout 经 agent 侧 `send_message_tool` 投递，该工具走 `sendMessage` + `parse_mode=MarkdownV2`。Telegram 的 MarkdownV2 **不渲染管道表格**，表格降级成 `|` 竖线文本。
同理 `hermes send`（CLI）也走 `sendMessage`，同样退化——`bare sent` 不是交付证明，必须 `--json` 看 `message_id` 连续递增且用户在 TG 里确认看到真表格。

## 正确通道
`scripts/telegram_reliable.py` → `send_telegram_reliable(target, text, parse_mode="RichMarkdown")`
走 Bot API 10.1 `sendRichMessage`，RichMarkdown 渲染真表格，回执 `rich_sent`。脚本 `_normalize_rich_markdown_tables` 已自动剥离表格前紧贴的 standalone `表1 · xxx` 标题行（否则 RichMarkdown 会降级成文字）。

## 7 个推 TG 的 cron（必须统一）
| cron | 当前通道 | 修复动作 |
|:---|:---|:---|
| BTC关键位同步 | btc_ref_levels_sync 内 subprocess 调发送器 | 统一 telegram_reliable RichMarkdown |
| Orion全市场雷达 | cron no_agent stdout | 脚本内 self-send RichMarkdown；cron deliver 改 local |
| BTC守护看门狗 | monitor/btc_watchdog subprocess | 统一 telegram_reliable RichMarkdown |
| 每日复盘提醒 | cron no_agent stdout | 脚本内 self-send；cron deliver 改 local |
| X情绪LLM分析 | cron no_agent stdout | 脚本内 self-send；cron deliver 改 local |
| 行情守望看门狗 | monitor/market_watchdog subprocess | 统一 telegram_reliable RichMarkdown |
| 每日运维聚合 | cron no_agent stdout | 脚本内 self-send；cron deliver 改 local |

## 转换模板（no_agent → self-send）
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from telegram_reliable import send_telegram_reliable

# 产出纯管道表文本 report_md（表格前不要 standalone 表1·标题行）
ok, reason = send_telegram_reliable(
    "telegram:-1003733144325:846", report_md, parse_mode="RichMarkdown"
)
# reason == "rich_sent" 即成功渲染真表格
```
配套：把该 cron 的 `deliver` 从 `telegram:...` 改为 `local`，避免 cron 再发一遍退化版（双重投递且第二份是裸 `|`）。

## 验证
发完后让用户确认 TG 里是渲染后的真表格（非 `|` 文本）；或查回执 `rich_sent`。失败/客户端不支持 RichMarkdown 时退回图片表兜底（写深色 HTML → browser_navigate → browser_vision 截图 PNG → `telegram_reliable.send_telegram_photo()`），详见 `xau-analysis-format` §⑬。
