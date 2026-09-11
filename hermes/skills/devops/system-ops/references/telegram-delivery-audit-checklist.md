# Telegram Delivery Audit Checklist — cron + direct-send + daemon

Use this when the user asks “哪些任务会推电报 / 为什么不推 / 哪些不该推”. Do not rely on `deliver` alone.

## Two-layer delivery model

| Layer | What to check | Why |
|---|---|---|
| Cron delivery | `~/AppData/Local/hermes/cron/jobs.json` fields: `name`, `schedule`, `deliver`, `no_agent`, `script`, `workdir`, `prompt`, `skills`, `last_status` | `deliver=telegram:...` means Hermes cron may send stdout to Telegram; `deliver=local` normally does not |
| Script direct-send | Search resolved script for `send_telegram`, `api.telegram.org`, `telegram:-1003733144325`, `telegram_direct`, `TELEGRAM_*` | A script can bypass cron delivery and send via Bot API even when `deliver=local` |
| Daemon/manual pushers | Check running processes and known scripts such as `btc_daemon.py`, `btc_card_gen.py`, `btc_push_386.py` | Long-running daemons and manual push scripts are not necessarily listed in cron |
| Hermes Studio workflows | Use the Studio MCP/API workflow list in addition to cron | Studio workflows can be scheduled/triggered separately from Hermes cron; if `workflows=[]`, there is no extra Studio task noise |

## Audit steps

1. Load `jobs.json` directly, not only `hermes cron list`, because the JSON shows `deliver`, `workdir`, `script`, prompt jobs, and last status in one place.
2. Check Hermes Studio workflows separately (`profiles_list` then `workflows_list` for the active profile). Record whether Studio has extra automations beyond cron.
3. Build a matrix with: `任务 / schedule / deliver / script-or-prompt / no_agent / last_status / direct_tg / conclusion`.
4. Resolve each script path using this order: `workdir/script`, `workdir/scripts/script`, then `~/AppData/Local/hermes/scripts/script`.
5. Scan each resolved script for direct Telegram send markers.
6. Separately inspect daemon/manual pushers:
   - `scripts/btc_daemon.py` → usually pushes to `telegram:-1003733144325:386` on trade/zone triggers.
   - `scripts/btc_card_gen.py` and `scripts/btc_push_386.py` → manual or script-triggered BTC card pushes to 386.
   - `scripts/freerouter.py` → cron may be `deliver=local`, but model changes can call `send_telegram()` to topic 846.
7. Inspect recent `~/AppData/Local/hermes/cron/output/<job_id>/` files, but distinguish cron wrapper metadata from delivered content: `**Status:** silent (empty output)` means the script produced no user-facing stdout even though the wrapper file is non-empty.
8. Explain “不推电报” as a routing choice, not a malfunction, when the task is a data collector (`Dune/COT/Deribit/liquidation/stablecoin/QLib/macro_poly`) and `deliver=local` with no direct-send.
9. Call out exceptions explicitly: `deliver=local` + direct-send means “normally local, but may push under script conditions”.

## Recommended output shape

Use three Markdown tables:

| Table | Columns |
|---|---|
| 会推送Telegram的cron | 任务 / 时间 / 目标 / 说明 |
| 不推送Telegram的cron | 任务 / 时间 / deliver / 为什么不推 |
| 特殊直连或daemon | 脚本 / 目标 / 触发条件 |

## Durable routing defaults for Tang Xi

| Type | Default |
|---|---|
| Orion雷达 / X情绪LLM / BTC关键位 / 每日技能 / 每日系统审计 / 每日备份 | Telegram topic 846 unless user changes it |
| BTC daemon / BTC手动卡 | Telegram topic 386 |
| Dune / COT / Deribit / 清算 / 稳定币 / QLib / 宏观Poly / 原始X情绪采集 | local only; data source for analysis cards |
| OpenRouter model sync | local by cron, but direct Telegram only when model selection changes unless disabled |
