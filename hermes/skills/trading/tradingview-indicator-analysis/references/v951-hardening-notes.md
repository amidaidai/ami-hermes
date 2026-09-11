# v9.5.1 硬化记录

## 新增能力

- `trading_system.py score`：机器化七项评分器，字段为结构、周期、订单流、衍生品、催化、风控、情绪；输出 A做多/做空、B等待、X禁做。
- `trading_system.py review`：记录成交复盘，并自动更新 `risk_state.json` 的今日盈亏、交易次数、连亏和锁定状态。
- `smart_monitor.py`：`condition` 增加 `combo/combined`，支持价格接近 + `confirm_if` 收盘确认的组合触发。
- `monitor_display.py`：统一监控卡中文显示层，避免实时监控和 cron 兜底出现不同排版。

## 验证命令

```bash
python -m py_compile scripts/monitor_display.py scripts/smart_monitor.py scripts/check_monitor_events.py scripts/trading_system.py scripts/daily_review.py
python scripts/trading_system.py score --quality A --rr 2.4 --scores '{"structure":1.5,"timeframe":1,"order_flow":1,"derivatives":1.5,"catalyst":1,"risk":2,"sentiment":1}'
python scripts/trading_system.py review --symbol BTCUSDT --plan-id PLAN --pnl -1.5 --r -0.5 --note '止损复盘'
```

## 注意

- C级数据最高只能 B等待。
- R:R 低于 1:2 直接 X禁做。
- 复盘命令会真实更新 `risk_state.json`，测试后如不想影响风控，需要清理测试记录。
