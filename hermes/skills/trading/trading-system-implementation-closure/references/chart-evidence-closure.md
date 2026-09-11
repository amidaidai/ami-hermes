# Chart evidence closure

## Purpose

Use this reference when a trading system must incorporate the full TradingView chart, not only an action table. The chart is evidence; `FinalVerdict` remains the only execution authority.

## Minimum normalized record

```json
{
  "status": "verified | partial | identity_mismatch | unavailable",
  "identity": {"symbol": "...", "timeframe": "...", "studies": []},
  "price_context": {"last_price": 0, "open": 0, "high": 0, "low": 0, "close": 0},
  "levels": [],
  "ict": {
    "fvg": [], "ob": [], "liquidity": [], "structure_labels": [],
    "objects_readable": true
  }
}
```

## Required sequence

1. Read chart state and verify exact symbol and timeframe.
2. After a symbol/timeframe switch, wait for recalculation and read state again.
3. Read price/quote, OHLC if available, action tables, Data Window, lines, boxes, and labels.
4. Normalize chart evidence with the current capture timestamp; do not use file mtime as market evidence.
5. Mark `partial` when the screenshot shows/possibly shows ICT objects but the structured object read is empty or incomplete.
6. Pass the record into `FinalVerdict`; `partial`/`unavailable` means WAIT at most, and identity mismatch means NO-GO.
7. Capture the full screenshot only after identity and evidence reads, and bind the screenshot path to the same run.

## BTC timeframe rule

`D → 4h → 1h → 15m → 5m` is the analysis order. `15m` is the execution layer; `5m` is the trigger layer. A current 5m chart must not be used to claim 15m confirmation. The collector should accept an explicit `expected_timeframe="15m"` and fail closed on mismatch.

## ICT evidence checklist

- Price bar: last price, current OHLC, day high/low, price-axis location.
- Value structure: VAH, VAL, POC, nPOC, VWAP, and distance from price.
- FVG: direction, upper/lower bounds, CE, quality, mitigated/active state.
- OB/Breaker: direction, bounds, quality, mitigated/active state.
- Structure events: BOS, MSS, CHoCH direction and bar age.
- Liquidity: prior highs/lows, equal highs/lows, session/day/week levels, swept/reclaimed state.
- Order flow: CVD, volume, OI, taker/funding and cross-source freshness.

If only the action grid has ICT text but boxes/labels cannot be read, preserve the text as indicator evidence but mark chart evidence `partial`; do not infer that the full visual chart has been machine-verified.

## Acceptance matrix

| Chart state | Allowed output |
|---|---|
| `verified` + SVP/AggVol/data gates pass | Continue normal FinalVerdict evaluation |
| `partial` or visual-only | Directional context and manual observation only; no GO-A |
| `identity_mismatch` | NO-GO; do not overwrite last good cache |
| `unavailable`/stale | WAIT/NO-GO according to existing freshness gates |
