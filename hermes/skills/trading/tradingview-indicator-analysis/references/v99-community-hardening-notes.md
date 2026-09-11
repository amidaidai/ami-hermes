# v9.9 社区化硬化笔记

## 触发场景

当棠溪要求“多角度看社区”“全部优化到9.9”“继续进化交易系统”时，不要只输出审计意见；应按“联网调研 → 本地审计 → 可落地补强 → 同步运行目录 → 重启验证 → 卡片汇报”的闭环执行。

## 社区/权威实践提炼

1. 交易日志不能只统计胜率；必须追踪 R 倍数、Expectancy、MAE、MFE、最大回撤、连续亏损和出场质量。
2. 告警系统不能“触发就推”；必须有过期数据、异常跳价、重复告警、冷却、预算、心跳和健康体检。
3. 黄金分析不能套用加密 Funding/OI；必须保留 DXY、美债收益率、GC 期货和事件风险宏观层。
4. AI Agent 交易系统必须按最小权限思路治理：cron 尽量 no-agent，网页内容不能直接污染长期 memory/skill/cron，高权限 profile 后续应隔离。
5. 风控不可自动升权；即使统计达标，也必须等待棠溪人工批准。

## 已沉淀的 9.9 组件

- `scripts/黄金宏观.py`：刷新 DXY、US10Y、US02Y、GC=F，写入 `data/xau_macro_context.json`，并嵌入 XAU source snapshot。
- `scripts/模型统计.py`：按模型统计交易数、胜率、总R、平均R、最大回撤、亏损串、MAE、MFE、出场质量和治理建议。
- `scripts/安全审计.py`：检查 default profile 高权限工具面、信号巡检 cron no-agent、secrets 目录和交易自动化安全建议。
- `scripts/系统体检.py`：刷新派生层后汇总心跳、历史快照、黄金宏观、模型统计、安全审计、主动监控品种和复盘样本，输出 `data/system_health_score.json`。
- `scripts/成交复盘.py`：复盘参数应支持 `--model`、`--mae-r`、`--mfe-r`、`--exit-quality`，让模型统计能识别出场质量和潜在执行泄漏。
- `scripts/信号巡检.py`：1分钟 no-agent 巡检应定时刷新黄金宏观、模型统计、安全审计和系统体检，而不是只转发告警。

## 验证清单

```bash
python -m py_compile scripts/行情守望.py scripts/信号巡检.py scripts/trading_system.py scripts/黄金宏观.py scripts/模型统计.py scripts/系统体检.py scripts/安全审计.py scripts/成交复盘.py
python scripts/安全审计.py
python scripts/模型统计.py
python scripts/系统体检.py
python scripts/成交复盘.py --plan-id TEST --symbol BTCUSDT --pnl 0 --r 0 --model VWAP反抽 --mae-r -0.4 --mfe-r 1.2 --exit-quality 按计划 --dry-run
python -m hermes_cli.main cron list --all
```

重启监控后必须确认：

- `data/monitor_heartbeat.json` 为 `status: running`。
- `data/system_health_score.json` 显示 `enabled_symbols` 只包含 `BTCUSDT` 和 `XAUUSD`。
- `data/security_audit.json` 已生成。
- `信号巡检` cron 仍为 `every 1m`、`no-agent`、last run ok。

## 汇报边界

可以说“9.9 架构级系统”或“9.9 架构”，但不要声称“实证 9.9 满分”，除非真实复盘样本达到策略治理门槛。当前硬门槛是：每个模型至少 20 笔真实复盘样本，且平均R、最大回撤、连续亏损和纪律表现达标，仍需棠溪手动批准升权。
