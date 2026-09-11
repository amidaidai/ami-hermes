# 棠溪推 TG 任务清单（2026-07-08 全量改造后状态）

## 4 个 TG Topic
- `telegram:-1003733144325:846` — 情报/提醒（Orion/X情绪/BTC关键位/复盘/运维/看门狗/各 collector）
- `telegram:-1003733144325:416` — auto_card 交易卡（走 send_telegram_reliable RichMarkdown，已真表格）
- `telegram:-1003733144325:386` — BTC分析卡（btc_card_gen/btc_daemon/btc_push_386，telegram_direct 已默认 RichMarkdown）
- 看门狗类 — 守护重启通知

## 19 个 cron 任务（全部 Deliver=local，脚本内自推 846）
| 脚本 | 改前 | 改后 |
|:---|:---|:---|
| btc_ref_levels_sync.py | 成功静默 | 推关键位表+偏离%+决策+结论 |
| orion_screener_radar.py | 简表 | 置信前置⭐🔸⚪+仓位系数+结论 |
| dune_collector.py | 只print静默 | 推链上表+交易所符号+结论 |
| cot_collector.py | 单行文本 | 详细机构多空表+结论（缓存命中也推） |
| deribit_options.py | 简表 | 加C/P符号/MaxPain🧲+结论 |
| liquidation_collector.py | 简表 | 加OI/价方向符号+爆仓决策+结论 |
| stablecoin_collector.py | 只print静默 | 推占比表+资金流符号+结论 |
| qlib_factors.py | 只print静默 | 推因子表+🟢🔴方向+三维+结论 |
| macro_poly_refresh.py | 静默成功 | 推宏观面板+风险情绪符号+结论 |
| x_sentiment_collector.py | 只print静默 | 推情绪表+😱分档+结论 |
| xau_tv_sync.py | 只print静默 | 推五层现场表+区间位置符号+结论 |
| data_freshness_watchdog.py | 只print静默 | 过期时推告警表+结论 |
| trade_exec_bridge.py | 一行文本 | 结构化事件表+结论 |
| btc_watchdog.py / market_watchdog.py | 看门狗 | 已 push_tg_rich |
| daily_trade_review_reminder.py | 简表 | 已 push_tg_rich |
| repo-maintenance/daily_ops_bundle.py | 简表 | 已 push_tg_rich |
| x_sentiment_context.py (LLM) | JSON | 额外快照表 push_tg_rich |
| X情绪LLM分析 (cron agent) | LLM卡 | 脚本内补快照表 |

## 关键修复点
- 386 通道 telegram_direct 默认 RichMarkdown
- 双发：cron Deliver=local + 脚本内 push_tg_rich
- COT 缓存命中走详细表
- qlib RSI 真实值 bug
- stablecoin 结论逻辑冲突
- **signal_confluence.py 加 dedup 限频（2026-07-09）**：`should_send("signal_confluence", report, force_every_seconds=7200)` — 内容变化或每2h推，之前每小时无条件推
- **x_sentiment_context.py 加 dedup 限频（2026-07-09）**：`should_send("x_sentiment_llm", rich, force_every_seconds=7200)` — 同上
- **8个高频cron批量降频（2026-07-09）**：从 165条/天降到 48条/天（-71%），详见 `tangxi-system-audit/references/cron-night-silent-and-downschedule.md` 第二轮深度降频段
