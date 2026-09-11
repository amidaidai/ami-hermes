# Structured monitor levels v2

Use this reference when an analysis card updates `data/monitor_levels.json` or when monitor scripts need to emit actionable alerts.

## Why

The monitor should behave like an execution assistant, not a price-only notifier. A level must say what the trader should do, when the idea expires, and what invalidates it.

## Preferred shape

```json
{
  "schema_version": 2,
  "symbol": "BTCUSDT",
  "analysis_cycle": "2026-06-16T00:00:00+08:00",
  "levels": [
    {
      "name": "R1_retest",
      "level": 66370.0,
      "side": "resistance",
      "type": "retest_short",
      "action": "反抽失败提醒",
      "priority": "high",
      "expires": "90m",
      "invalid_if": "5m close above 66517"
    }
  ]
}
```

## Required fields

- `level_confidence`: key-level confidence object, separate from price-source confidence. Recommended shape: `{ "grade": "B", "score": 74, "label": "结构共振", "basis": ["1h结构位", "VWAP回踩", "失效线明确"], "missing": ["订单流确认"] }`.
- `level`: numeric trigger price.
- `side`: `support` or `resistance`.
- `type`: execution model, such as `retest_short`, `breakout_accept`, `sweep_reclaim`, `vwap_retest`.
- `action`: short actionable instruction for the alert card.
- `priority`: `low`, `medium`, `high`, or `urgent`.
- `expires`: validity window, usually next 5m/15m setup window or `90m`.
- `invalid_if`: explicit invalidation condition, preferably a candle close rule.

## Compatibility rule

Monitor scripts should keep reading legacy maps such as `{ "R1": 66370 }`, but all new analysis writes should use `levels: []`. If only legacy data is present, degrade gracefully and omit action/invalid_if rather than inventing them.

## Alert content rule

Every structured alert should include:

- price and crossed/approached level;
- action;
- invalidation condition;
- priority;
- last analysis cycle if available.

Do not emit generic “near key level” alerts when structured fields exist.
