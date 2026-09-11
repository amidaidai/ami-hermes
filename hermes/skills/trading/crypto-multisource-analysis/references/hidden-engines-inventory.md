# 隐藏引擎清单 — 2026-06-29 深度审计

23,114行Python总代码中，11个引擎5,300+行已编写但未接入任何cron或管线。

## 引擎清单

| 引擎 | 行数 | 功能 | 源码路径 | 状态 |
|------|:--:|------|------|:--:|
| trading_system.py | 980 | 交易执行系统 v9.5 | `scripts/trading_system.py` | 未接cron |
| risk_constitution.py | 739 | 风险宪法·Kelly仓位·连续亏损熔断 | `scripts/risk_constitution.py` | 未接cron |
| five_model_matcher.py | 569 | 五模型入场生成器 | `scripts/five_model_matcher.py` | 未接 |
| scoring_engine.py | 511 | 14分机器评分引擎 v1 | `scripts/scoring_engine.py` | 未接（管线用v2） |
| vwap_ema_cvd_engine.py | 476 | VWAP/EMA/CVD综合引擎 | `scripts/vwap_ema_cvd_engine.py` | 未接 |
| dmi_decision.py | 368 | DMI决策引擎 | `scripts/dmi_decision.py` | 未接 |
| cvd_analyzer.py | 367 | CVD综合分析器 | `scripts/cvd_analyzer.py` | 未接 |
| orderflow_absorption.py | 294 | 订单流吸收/分布检测 | `scripts/orderflow_absorption.py` | 未接 |
| render_tv_card.py | 497 | TV卡渲染引擎 | `scripts/render_tv_card.py` | 未接 |
| backtest_runner.py | 713 | 回测引擎(过拟合检测/手续费/时段) | `scripts/backtest_runner.py` | 未接 |
| regime_backtest.py | 301 | 行情回测引擎 | `scripts/regime_backtest.py` | 未接 |
| **合计** | **5,815** | | | |

## 已接入管线（仅BTC）

BTC有专用集成管线 `pipeline_integration.py`（340行），串联以下模块：
- pipeline_2022.py — 2022模型管线
- fvg_detector.py — FVG检测
- order_block.py — OB检测
- scoring_engine_v2.py — 多因子评分v2（注意：v1未接，v2是不同引擎）
- event_calendar.py — 事件日历

非BTC资产走 `pipeline_router.py`（135行）声明式路由，19步骤。

## 接线优先级

P1（激活已有代码，零新增）：
1. scoring_engine.py → 接入BTC管线（替代或联合v2）
2. dmi_decision.py → 接入BTC管线
3. cvd_analyzer.py → 接入BTC管线
4. backtest_runner.py → 每日复盘cron调用
5. risk_constitution.py → 风控决策前硬检查
6. trading_system.py → 下单前执行

P2（需要少量适配）：
7. five_model_matcher.py → 扩展为多模型ensemble
8. vwap_ema_cvd_engine.py → 接入TV数据读取
9. orderflow_absorption.py → 接入CVD管线
10. render_tv_card.py → 统一卡渲染出口
11. regime_backtest.py → 回测管线
