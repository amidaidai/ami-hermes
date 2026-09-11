# 多品种运行时 v9.6

## 已接入

- `scripts/trading_system.py`：读取 `data/symbol_templates.json`，按品种识别资产、市场、杠杆、默认风险和数据源。
- `scripts/smart_monitor.py`：支持 `monitor_levels.json` 的 `symbols` 多品种结构；每个品种独立 `plan_id`、周期、价格、levels、状态。
- `data/monitor_levels.json`：支持 `schema: monitor_levels_multi_v1`，当前可同时放 BTCUSDT、ETHUSDT、XAUUSD 等块。

## 风控继承

- BTC/ETH 默认从模板继承 `default_risk_usd: 3`，最高仍受账户单笔 10U 限制。
- SOL/BNB/XAU/USOIL/SPX 默认轻仓 2U。
- `risk_gate(..., requested_risk=template_risk_limit(symbol))` 会把品种默认风险压入最终风险闸门。

## 数据源分层

- 加密品种：Binance 现货 + Binance 合约 mark/index/Funding/OI/多空/Taker。
- 非加密品种：不套用 Funding/OI；`source_snapshot` 写入“非加密品种，不套用Funding/OI；按模板查看宏观/事件背景”。
- 非加密实时价格若不可用，只能用 `price_at_analysis` 临时兜底，质量为 C；监控应设置 `monitor_enabled: false`，避免假实时告警。

## 多品种 monitor_levels 结构

```json
{
  "schema": "monitor_levels_multi_v1",
  "symbols": {
    "BTCUSDT": {"plan_id": "...", "analysis_cycle": "...", "levels": []},
    "ETHUSDT": {"plan_id": "...", "analysis_cycle": "...", "levels": []},
    "XAUUSD": {"monitor_enabled": false, "disabled_reason": "实时价格源待接入"}
  }
}
```

## 验证命令

```bash
python -m py_compile scripts/trading_system.py scripts/smart_monitor.py scripts/check_monitor_events.py scripts/multi_symbol_templates.py
python scripts/trading_system.py snapshot --symbol BTCUSDT
python scripts/trading_system.py snapshot --symbol ETHUSDT
python scripts/trading_system.py snapshot --symbol XAUUSD
```

## 注意

- 非加密品种优先走金十 Quote 直接 MCP HTTP 调用；不可再用 `price_at_analysis` 假装实时。
- 监控价格层必须写入多源置信度：加密至少 Binance现货 + CoinGecko + Binance合约Mark/Index，非加密若只有金十 Quote 则标记 `C级 · 55% · 单源`，不能显示成 A 级。
- 非加密价格源：金十 Quote 为主；Yahoo Chart 作为第二源时必须走 Clash 代理（默认 `http://127.0.0.1:7897`，优先读取 `HTTPS_PROXY/HTTP_PROXY`），避免直连超时。无第二源时标记 `C级 · 单源`，不假装多源确认。
- 触发后如果活跃关键位少于2个、同轮多位触发或紧急触发，写入 `data/structure_refresh_requests.jsonl` 并在 `monitor_levels.json` 标记 `needs_structure_refresh`。`信号巡检.py` 会调用 `scripts/智能更新结构.py` 纯脚本重算近端结构，补回4个活跃位并清理 pending 队列。
- `行情守望.py` 负责 10s 级实时守望；`信号巡检.py` 只做 1m 守护检查，不承担实时性。
- 非加密品种接入金十/TradingView 实时价格前，不要让监控自动触发真实告警。
