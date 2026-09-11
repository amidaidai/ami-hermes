# 休眠引擎接线进度 v9.4（2026-06-29 第二轮审计后）

## 已接线 ✅

| 引擎 | 行数 | 接线方式 | 时间 |
|------|:--:|------|------|
| dmi_decision.py | 368 | pipeline_integration.py import `compute_dmi()` | 2026-06-29 |
| qlib_factors.py | 200+ | 新建·独立cron·因子注入card | 2026-06-29 |
| trade_exec_bridge.py | 120+ | 新建·桥接trading_system→trade_events.jsonl | 2026-06-29 |

## 待接线 ⚠️

| 引擎 | 行数 | 功能 | 接线难点 |
|------|:--:|------|------|
| risk_constitution.py | 739 | 风险宪法·Kelly·熔断 | 需OHLCV+TV数据，`check_constitution()` API |
| five_model_matcher.py | 569 | 五模型入场匹配 | 分散函数(VWAPrejection/VahReclaim/ValReclaim等)无统一入口 |
| scoring_engine.py | 511 | 14分评分v1 | 管线用v2，v1被忽略 |
| vwap_ema_cvd_engine.py | 476 | VWAP/EMA/CVD综合 | 需klines数据结构 |
| cvd_analyzer.py | 367 | CVD分析器 | CVDAnalyzer类·需CVD时间序列 |
| orderflow_absorption.py | 294 | 订单流吸收 | detect_absorption()·需订单流数据 |
| render_tv_card.py | 497 | TV卡渲染 | 独立工具脚本·可被管线引用 |
| backtest_runner.py | 713 | 回测(过拟合检测) | BTConfig类·需大量历史数据 |
| regime_backtest.py | 301 | 行情回测 | 独立工具·未接入auto_card |

## 不再需要接线 ⛔

| 引擎 | 原因 |
|------|------|
| trading_system.py | 已通过trade_exec_bridge间接访问 |
| position_sizer.py | 2行wrapper空壳·无实际逻辑 |
| event_ban_live.py | 2行wrapper空壳 |
| session_strategy.py | 2行wrapper空壳 |
| triple_confirm.py | 2行wrapper空壳 |

## 接线优先级建议

1. **risk_constitution.py** (P1) — 风控宪法，直接影响仓位决策
2. **five_model_matcher.py** (P1) — 多模型一致性确认
3. **backtest_runner.py** (P2) — 信号历史胜率背书
