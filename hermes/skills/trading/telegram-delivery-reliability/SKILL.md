---
name: telegram-delivery-reliability
description: Use when hardening Telegram delivery formatting or retries.
category: trading
---

> **同族导航** — TG投递组 5 个技能各司其职，别加载错 （同族入口：`tangxi-tg-delivery-format`）
> · **本技能 `telegram-delivery-reliability`** = 投递可靠性加固（重试/格式化守卫）
> · 同族其余：`tangxi-tg-delivery-format`（入口 · 投递格式铁律（纯 Markdown 管道表 / RichMarkdown 真表格 / 禁图片表））、`tangxi-tg-report-standard`（报告质量铁律（总体结论、置信降序、决策厚度））、`tangxi-tg-reports`（4 个 topic 架构 + 脚本改造通用规范（最短版））、`tangxi-tg-rich-reporting`（RichMarkdown 通道与「静默 collector」改造模板、做厚方法）
> · 组内改动请同步其余成员的触发词，避免同名族抢触发。


# Telegram Delivery Reliability

Use this class-level workflow when a project sends structured reports, analysis cards, or operational alerts to Telegram through Bot API wrappers or legacy direct senders.

## Core contract

1. Keep transport selection separate from Telegram `sendMessage` fields.
   - `RichMarkdown` is an internal selector for `/sendRichMessage`.
   - Never pass `RichMarkdown` as `sendMessage.parse_mode`.
   - Build a payload with `rich_message.markdown` for the rich endpoint.
2. Normalize structured Markdown before transport.
   - Put each pipe-table at a clear block boundary.
   - Remove standalone titles glued to table headers.
   - Keep mobile tables to at most three columns; merge excess evidence/action columns into a details column.
   - Keep cells one-line and remove inline syntax or literal pipes that can break parsing.
3. Use semantic fallback when rich delivery fails.
   - Ordinary `sendMessage` has no table primitive.
   - Convert rows to labeled text such as `指标：OI · 读数：107,616 · 状态：持平`.
   - Never forward the original raw pipe table as a fallback.
4. Protect external delivery.
   - Automated delivery requires an explicit enable flag and an exact configured target.
   - Do not let historical call-site topics override the configured target.
   - Keep real Telegram end-to-end tests disabled unless the operator explicitly authorizes them.
5. Make rate limiting cross-process.
   - On HTTP 429, parse `parameters.retry_after` first, then the HTTP `Retry-After` header, then use a conservative default.
   - Persist a bounded cooldown (minimum 1 second, maximum 900 seconds) in a shared file.
   - Text, photo, direct/legacy, and pending-flush paths must all check the same cooldown.
   - Do not sleep/retry blindly after the final 429 attempt.
6. Make pending queues safe.
   - Serialize append and flush/rewrite operations.
   - Preserve transient failures for controlled retry.
   - Move permanent client/configuration failures and exhausted/expired items to a dead-letter file.
   - Never auto-flush historical queues during a formatting fix without explicit authorization.

## Implementation workflow

- Inspect every send entry point, including legacy fallbacks, before editing.
- Add tests at the payload boundary: endpoint, thread routing, normalized Markdown, fallback text, and 429 state.
- Use monkeypatched HTTP fixtures for rich success, rich 4xx fallback, 429 response parsing, and photo delivery. Do not call the real Telegram API in tests.
- Verify syntax, targeted tests, then the full repository test suite. Report real test output and distinguish local verification from client-side rendering verification.

## Common pitfalls

- A successful HTTP response does not prove the message went to the intended forum topic; verify target construction separately.
- A rich endpoint failure followed by a plain send is only safe if the plain payload contains semantic text and no raw table syntax.
- In-memory cooldown alone does not protect separate cron/watchdog processes.
- A missing automated target is a configuration failure, not a reason to endlessly append duplicate pending rows.
- Avoid broad rewrites of queue files: they may contain historical production messages and test pollution.

## References

- See `references/telegram-delivery-hardening-session.md` for tested failure patterns, fixture cases, and verification boundaries from the hardening pass.
