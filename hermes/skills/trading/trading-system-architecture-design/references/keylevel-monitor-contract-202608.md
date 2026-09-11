# 关键位监控契约（2026-08）

## 单一来源

```text
TV MCP候选采集 → keylevels_candidates.json（候选池）
→ 人工批准 → keylevels_config.json（唯一监控源）
→ keylevel_guard.py（单实例）
→ trigger_{symbol}.json（事件）
→ keylevel_analysis_dispatcher.py
→ auto_card.py --quick
→ decision_loop.FinalVerdict
```

`monitor_levels.json` 与 `btc_ref_levels.json` 是历史/参考缓存，不得作为当前监控配置或最终裁决输入。

## 配置字段

每个批准位建议包含：

```json
{
  "name": "价值区·VAL",
  "price": 78400,
  "enabled": true,
  "source": "tradingview_mcp",
  "valid_until": "2026-08-29T12:00:00+08:00",
  "tv_symbol": "BINANCE:BTCUSDT.P"
}
```

`enabled=false` 或 `valid_until/expires_at` 已过期的位不进入轮询。

## 事件字段

监控穿越只产生事件，不产生交易方向：

```json
{
  "event_id": "BTCUSDT-VAL-...",
  "event_type": "keylevel_cross",
  "event_class": "price_cross_only",
  "symbol": "BTCUSDT",
  "tv_symbol": "BINANCE:BTCUSDT.P",
  "level_price": 78400,
  "cross_direction": "up",
  "direction": "neutral",
  "analysis_required": true,
  "analysis_mode": "quick",
  "analysis_status": "pending",
  "config_revision": "...",
  "level_source": "keylevels_config"
}
```

`cross_direction` 仅描述价格穿越方向。只有重新读取 TradingView 主/触发周期与实时衍生品数据后，FinalVerdict 才能输出 `GO-A/GO-B/WAIT/NO-GO`。

## 调度与幂等

- dispatcher 只消费 `analysis_status=pending`。
- 默认调用 `auto_card.py SYMBOL --quick`。
- 不自动下单；推送必须显式传入 `--push`。
- 成功标记 `analyzed`，失败标记 `failed`，保留 `event_id` 与错误摘要。
- 监控守护的状态文件必须从磁盘恢复，避免重启后重复触发。
- 看门狗检查精确实例数：0个重启，1个正常，多于1个先收敛。

## TradingView采集

完整候选采集覆盖 `D→4h→1h→15m→5m`。每次 `set_timeframe` 后先调用 `chart_get_state` 校验品种和周期，再读取 OHLCV、study values、lines、labels、boxes、tables。任何校验失败，该周期标记失败，不得静默采用上一周期数据。
