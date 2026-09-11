# TV Data Staleness & Forced Refresh Workflow

## The Problem

TV MCP `data_get_study_values` can return **stale data** when the chart session has been idle. TradingView's indicator calculations are cached per session — a chart opened before a significant market event (daily candle rollover, major price spike) keeps old indicator values until forced to recalculate. `chart_get_state` may report the correct symbol/timeframe but `study_values` returns numbers from hours ago.

### Real-world example (2026-07-04 00:01 BJT)

```
Initial 15m read:  S VWAP=61,809, POC=61,932, VAL=61,576  ← stale pre-midnight
Actual price:      62,500+ (big US-session rally had occurred)
After TF cycle:    S VWAP=62,676, POC=62,794, VAL=62,573  ← correct
```

The stale data made the first analysis card completely wrong — showing price at 61,922 in value area when actually price was 62,500+ post-rally.

## Detection

After reading `study_values`, cross-check against:

1. **Binance spot price** via `mcp_binance_get_price` — if VWAP or key levels are >0.5% different from current price, suspect staleness
2. **DO (Daily Open)** in study_values — if it matches yesterday's close instead of today's open, chart hasn't rolled over
3. **Klines** via `mcp_binance_get_klines(symbol, "15m", 5)` — compare close prices to VWAP/POC/VAH/VAL

## Forced Refresh Procedure

**Do not just re-read the same timeframe.** The indicator cache must be jolted by cycling:

```
1. chart_set_timeframe("D")       → wait 3-5s
2. chart_set_timeframe("240")     → wait 3-5s  (4h)
3. chart_set_timeframe("60")      → wait 3-5s  (1h)
4. chart_set_timeframe("5")       → wait 3-5s  (5m)
5. chart_set_timeframe("15")      → wait 3-5s  ★ back to execution TF
6. data_get_study_values()        → should now be fresh
```

Each `chart_set_timeframe` triggers TV to recalculate indicators for that resolution. Cycling through all TF layers forces a full recalculation on the final read.

## When to Suspect Staleness

| Trigger | Check | Action |
|:--------|:------|:-------|
| Price moved >0.5% since last read | Compare Binance price | Cycle all TF |
| New daily candle just started (past midnight BJT) | DO matches old close | Cycle all TF |
| Big volume candle on klines | Volume spike visible | Cycle all TF |
| Chart was idle >10min (other tasks running) | No chart_tools calls | Cycle all TF |
| After `chart_set_symbol` | New symbol, old data persists | Cycle 2-3 TF |
| After TV MCP crash recovery | Restarted session may return cached data | Cycle all TF |

## Prevention

- **Always begin multi-TF collection from D downwards** (D→4h→1h→15m→5m), not by reading the execution TF first. The D→4h→1h cycle warms up the calculation engine.
- **Never trust a single `study_values` read** — always cross-check against Binance price and klines.
- **After any TV MCP crash or `tv_launch` recovery**, cycle through 2-3 timeframes before reading execution TF data.
- **First analysis of every session**: always include a full D→4h→1h→15m→5m cycle, even if only the execution TF is needed for output.

## Relationship to TV MCP Crash Recovery

Staleness ≠ crash/wedge:
- Crash/wedge = MCP server or CDP connection broken → `tv_launch(kill_existing=true)` + wait
- Staleness = MCP responds fine but data is old → TF cycling
- Both can coexist: after crash recovery the chart may come back with stale data, requiring both `tv_launch` AND TF cycling

See `tv-mcp-crash-recovery-2026-06-30.md` for crash recovery flow.
