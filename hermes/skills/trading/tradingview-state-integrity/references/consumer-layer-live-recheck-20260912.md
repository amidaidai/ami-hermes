# 消费层现场复核记录（2026-09-12）

## 已验证的稳定路径

1. 先用 `chart_set_symbol`/`chart_set_timeframe`，再用 `chart_get_state` 读回真实 symbol、resolution 和 studies。
2. 切换后若 `data_get_pine_tables`、values 或对象接口为空，不把空结果解释为“该周期没有指标”；在身份仍正确时做有界重试。
3. 采集开始和结束各做一次 identity gate，结束时同时检查 symbol 与 timeframe。期间被 cron 或其他任务抢图时，丢弃本轮组合结果并保留旧缓存为 stale。
4. `data lines` 返回 `horizontal_levels`，`data boxes` 的规范化集合可能叫 `zones`，`data labels` 返回文字/价格。无标签的 box 只能保存为 `zone`，禁止猜成 FVG、OB 或 Breaker。
5. quote 要保留完整 payload。TradingView quote 必须核对 `symbol`、`exchange`、`type`、description；BTC 永续应为 Binance/swap。Binance Futures `/fapi/v1/ticker/24hr` 和 `/fapi/v1/premiumIndex` 可补 24h high/low、mark/index/funding，并记录跨源价差。
6. 旧测试桩可能只提供标量 `read_quote` 或没有新 state/object 函数；兼容回退只能服务旧桩，生产现场仍必须使用完整 payload 和最终身份校验。

## 实测边界

- `verified` 表示身份、周期、studies、价格栏和至少一种结构化证据通过，不表示 FVG/OB/BOS/MSS 每个子类型均已非空。
- SVP 主表可能短暂空读；即使 source code 具有 StructPack，仍以现场 Data Window/对象读回为准。
- 共享图表被后台任务切换时，CLI 可能返回 `success`，但后续 state 已是另一个周期；因此固定 sleep + 单次检查不够。
- 只要 Binance 或 TradingView 报价身份不匹配，不能用数量级看似相近的数据继续拼缓存。

## 回归命令

```bash
python -m pytest tests/ -q
python scripts/indicator_source_audit.py
python scripts/tv_indicator_alignment_check.py
python -m pytest tests/test_tv_data_bridge_symbol_gate.py tests/test_chart_evidence.py tests/test_chart_evidence_rendering.py -q
```

验收要求：全量测试通过、两份 Pine 契约对齐、现场截图使用 `region=full`，并在截图前最后一次确认目标 symbol/resolution。