# 9.5 交易执行系统落地说明

## 目标

把 v5.1 从分析模板升级为 9.5 分执行系统：分析、监控、风控、数据快照、事件日志、复盘统计闭环。

## 新增模块

- `scripts/trading_system.py`：公共交易系统模块。
  - `risk_gate()`：读取 `data/risk_state.json`，按日亏、连亏、数据质量、R:R、评分决定允许、降仓或禁做。
  - `position_size()`：按入场、止损、风险、杠杆反推数量、名义、保证金和最大亏损。
  - `source_snapshot()`：生成 `data/source_snapshot.json`，记录 Binance 现货价、futures mark/index、Funding、OI、多空比、Taker、Basis 和数据质量。
  - `log_plan()`、`log_event()`、`log_review()`：写入 `trade_plans.jsonl`、`trade_events.jsonl`、`trade_reviews.jsonl`。
- `scripts/daily_review.py`：每日复盘生成器，输出 `data/daily_review.md`。
- `scripts/smart_monitor.py` v6.3：监控推送加入衍生品摘要、风控闸门、状态机条件解释，并把事件同步写入 `trade_events.jsonl`。
- `scripts/check_monitor_events.py` v3.3：cron 兜底卡片同步显示衍生品、风控和中文化计划。

## 必须遵守

- CVD 当前仍为 C级估算，不得作为 A单加分，只能当辅助背景。
- 数据质量 C级时，`risk_gate()` 最高允许轻仓，默认不超过 `3U`。
- R:R 低于 1:2 时，`risk_gate()` 必须禁做。
- 连亏 2 笔降至轻仓；连亏 3 笔锁交易；日亏触达上限锁交易。
- 每次正式分析必须写入 `trade_plans.jsonl`；每次监控触发必须写入 `trade_events.jsonl`；每次成交或放弃必须写入 `trade_reviews.jsonl`。
- 监控卡片必须保留：品种、价格、计划、现状、CVD、衍生、风控、价位、周期、动作。

## 验证命令

```bash
python -m py_compile scripts/smart_monitor.py scripts/check_monitor_events.py scripts/trading_system.py scripts/daily_review.py
python scripts/trading_system.py snapshot --symbol BTCUSDT
python scripts/trading_system.py risk --score 9 --quality C --rr 2.5
python scripts/daily_review.py
```

## 当前已知边界

- 清算热力图还未接入，后续可用 Coinalyze 或其他数据源补齐。
- CVD 仍需升级到 Binance futures `aggTrades` 才能从 C级提升到 B/A级。
- TradingView 指标快照还未自动写入 `source_snapshot.json`。
