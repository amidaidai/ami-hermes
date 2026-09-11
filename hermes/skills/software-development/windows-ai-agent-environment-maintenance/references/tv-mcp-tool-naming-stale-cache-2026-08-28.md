# TV MCP Tool Naming + Stale Cache — 2026-08-28 Session Transcript

## Symptom 1: tool_call fails with "not a deferrable tool"
```
tool_call(name="mcp_tradingview_data_get_pine_tables", arguments={"study_filter":"SVP+ICT+VWAP+CVD"})
→ {"error": "'mcp_tradingview_data_get_pine_tables' is not a deferrable tool.
   If it appears in the model-facing tools list already, call it directly instead of via tool_call."}
```
Then calling it directly as a function:
```
mcp_tradingview_data_get_pine_tables(...)
→ Tool 'mcp_tradingview_data_get_pine_tables' does not exist.
  Available tools: ... (no mcp_tradingview_* listed)
```
Result: single-underscore name is dead. Tool Search reveals the double-underscore name:
```
tool_search("tradingview chart get state timeframe study values pine tables")
→ mcp__tradingview__chart_get_state
→ mcp__tradingview__data_get_pine_tables
→ mcp__tradingview__data_get_study_values
```
**Working form:** `tool_call(name="mcp__tradingview__data_get_pine_tables", arguments={...})`.

## Symptom 2: stale cross-session cache gives a wrong price
Initial turn read TV `data_get_study_values` on `BINANCE:BTCUSDT.P` and produced a full card saying BTC ≈ 64,218 (date "7月12日"). Live Binance tick in the same session:
```
curl -s "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT" → {"price":"79674.64000000"}
```
→ TV figure (64K) was stale by ~20K. `chart_get_state` still reported the correct symbol/resolution (15), so the source looked valid — the indicator math was simply left over from a previous cached state.

## Fix that worked
1. Anchor the live price with Binance spot + fapi tick (cheap curl, no MCP dependency).
2. Force TV refresh: `python scripts/tv_live_dump.py --symbol BTCUSDT --verbose` → refreshes `tv_live.json` + `tv_live_BTCUSDT.json`.
3. Re-read `study_values` / `pine_tables` after the refresh; the refreshed values (79.6K VWAP / POC 79.6K / VAH 80.1K / nPOC 78.4K) matched Binance.
4. Re-derive BJT time from the fresh tick timestamp, not from the stale cache header.

## Why the card was wrong
The 64K card reused stale session context because I trusted TV `study_values` without the cross-check. Lesson: **always anchor a live price before quoting any TV indicator level**, and treat any TV figure that's off by an order of magnitude as stale — refresh before re-reading.

## Also fixed in the same session
The pipeline for a lightweight "看一下X" card: TV 15m main-execution action grid + sub-indicator (Volume Aggregated) + Binance OI/funding/LS/taker via curl + full screenshot. On the 15m layer the action grid said "转空·CHoCH↓·等BOS" while the sub-indicator said "价涨+OI升·新多扩仓 共振3/4" — a real main/sub misalignment; the light card must surface that conflict rather than force a direction.
