# Session note: BTC v9.6 execution template learning

This session refined the TradingView analysis workflow from a system-only upgrade into a template-and-system synchronized workflow.

## Durable lesson

When upgrading the trading execution stack, do not stop after changing scripts, monitor cards, risk gates, or logs. Always check and update the active analysis template too:

- `references/indicator-pair-execution-template.md`
- monitor script expectations
- risk gate output fields
- trade plan/event/review log schema

The user explicitly noticed when the system layer was upgraded but the analysis template itself had not been reviewed.

## v9.6 model checklist requirement

For the five fixed models, future BTC/ETH/XAU analyses should include or internally verify:

1. 入场前检查
2. 触发条件
3. 确认条件
4. 失效条件
5. 监控位写法
6. 复盘标签

The five fixed models remain:

- VWAP反抽
- VAH/VAL回收
- POC拒绝
- 扫流动性回收
- 突破接受

If a setup does not satisfy its checklist, output `B等待` or `X禁做`, not an improvised A setup.

## BTC run pattern captured

A proper BTC run under this skill should:

- load the execution template first;
- gather multi-source prices and derivatives;
- mark data quality A/B/C;
- score the setup;
- run the risk gate;
- write `source_snapshot.json`, `monitor_levels.json`, and `trade_plans.jsonl`;
- verify the written files before final response;
- present the result as a Chinese vertical execution card.
