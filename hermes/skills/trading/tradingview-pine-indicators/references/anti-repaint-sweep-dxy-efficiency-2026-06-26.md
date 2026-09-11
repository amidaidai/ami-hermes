# Anti-Repaint Sweep Protection, request.security Efficiency, Free-Account TVC Data

Session: 2026-06-26 (supplement). Three production hardening techniques discovered during final audit pass.

## 1. `barstate.isconfirmed` for Anti-Repaint Sweep Detection

### Problem
Sweep rejection confirmation uses `close` to check if price closed back inside the level:
```pine
isSwept := lvl.isHigh ? (high > lvl.price and close < lvl.price) : (low < lvl.price and close > lvl.price)
```
On a **real-time (unconfirmed) bar**, `close` changes with every tick. Price may wick above the level, then close below → `isSwept` triggers → next tick price spikes back up → the sweep disappears and reappears. This is **repainting** — the signal flashes on and off until the bar closes.

### Community Standard (TradingView Official Docs + Quantzee + ValorAlgo)
- Signals that use `close` on real-time bars ARE repainting signals
- `barstate.isconfirmed` is `true` on all historical bars AND on the last (closing) update of a real-time bar
- Adding `barstate.isconfirmed` as a gate means: only check the sweep condition when the bar's final close is known

### Fix
```pine
// Only confirm sweep on bar close — prevents real-time bar flickering
isSwept := barstate.isconfirmed and (lvl.isHigh ? (high > lvl.price and close < lvl.price) : (low < lvl.price and close > lvl.price))
```

### Rule
Any signal detection that reads `close` (or `high`/`low`) to make a **persistent state change** (like setting `lvl.swept = true`) should gate on `barstate.isconfirmed`. This prevents the signal from flickering on the real-time bar and only committing once the bar's final values are known.

### Caveats
- `barstate.isconfirmed` adds 1 bar of latency on real-time bars (signal appears when bar closes, not during the bar)
- On historical bars, `barstate.isconfirmed` is always `true` — no impact on backtesting
- Do NOT use `barstate.islast` for this — it's true on every real-time update, not just the closing one

---

## 2. `request.security` Tuple Merge — Save Call Quota

### Problem
Needed both `close` and `close[1]` from DXY to calculate daily change. Initial implementation used two separate `request.security` calls:
```pine
float dxyClose = request.security("TVC:DXY", timeframe.period, close)
float dxyPrev = request.security("TVC:DXY", timeframe.period, close[1])
```
This wastes 2 of the 40-call quota on the same symbol/timeframe.

### Fix — Tuple Unpacking
Pine v5+ supports returning multiple values from a single `request.security` call using a tuple:
```pine
[dxyClose, dxyPrev] = request.security("TVC:DXY", timeframe.period, [close, close[1]])
```
One call, two values. Saves 1 `request.security` slot.

### General Pattern
```pine
// Multiple expressions from the same symbol/timeframe → ONE call
[val1, val2, val3] = request.security(symbol, tf, [expr1, expr2, expr3])
```

### Rule
When you need 2+ values from the same symbol and timeframe, ALWAYS use tuple unpacking. Never make separate `request.security` calls to the same symbol/tf for different expressions.

### Pine Script Runtime Caveat
`request.security()` ALWAYS runs regardless of conditional blocks — even inside `if false`, the call executes on every bar (StackOverflow confirmed). You cannot conditionally skip it to save runtime. The only optimization is to merge calls to the same symbol.

---

## 3. Free-Account TVC Data Sources: DXY and VIX

### Compatibility
- `TVC:DXY` (US Dollar Index) and `TVC:VIX` (CBOE Volatility Index) are available on **free TradingView accounts** via the TVC data source
- No paid plan required to access these in `request.security()`
- Both return `na` on symbols where they don't apply (e.g., on crypto charts these are still accessible — DXY is useful for BTC/gold correlation)

### Usage for Multi-Market Panels
```pine
// DXY direction — for metals/forex panels
[dxyClose, dxyPrev] = request.security("TVC:DXY", timeframe.period, [close, close[1]])
float dxyChange = not na(dxyClose) and not na(dxyPrev) ? dxyClose - dxyPrev : 0.0
string dxyDirection = dxyChange > 0.05 ? "DXY↑利空" : dxyChange < -0.05 ? "DXY↓利多" : "DXY→中性"

// VIX — for stock/index/metals panels
float vixClose = request.security("TVC:VIX", timeframe.period, close)
string vixText = not na(vixClose) ? "VIX " + str.tostring(vixClose, "#.0") + (vixClose > 25 ? "高波" : vixClose < 15 ? "低波" : "中波") : ""
```

### Market-Specific Display
- **Crypto**: DXY negative correlation (BTC↑ when DXY↓) — show as "DXY↓利多" / "DXY↑利空"
- **Metals (XAU)**: Same DXY correlation — gold rises when DXY falls
- **Forex (EUR/GBP)**: DXY negative correlation — EUR rises when DXY falls
- **Stocks/Index**: VIX as volatility gauge — VIX>25 high volatility, VIX<15 low volatility

### Display Conditional
Only show DXY on metals/forex panels, only show VIX on stocks/metals panels:
```pine
string dxyHint = (marketMetal or marketForex) and dxyDirection != "" ? " · " + dxyDirection : ""
string vixHint = (marketStock or marketIndex or marketMetal) and vixText != "" ? " · " + vixText : ""
```

---

## 4. Alert Localization and Dynamic Price

### Pattern
In Pine v5, `alertcondition` message supports string concatenation with dynamic values:
```pine
alertcondition(alertLongA, "A多信号", "A多 入场" + (not na(replayPlanPrice) ? " @" + str.tostring(replayPlanPrice, format.mintick) : ""))
```

### Best Practices
1. **Chinese alert titles and messages** — user preference; English alerts like "Pro A Long" were corrected to "A多信号"
2. **Include price in alert message** — helps user know where the signal triggered without looking at the chart
3. **Edge-trigger alerts** — use `condition and not condition[1]` to fire once on transition, not every bar:
   ```pine
   bool alertKillZone = ENABLE_PRO_ALERTS and isKillZone and not isKillZone[1]
   ```
4. **Score-threshold alerts** — fire when score crosses a threshold:
   ```pine
   bool alertMagnetHigh = ENABLE_PRO_ALERTS and magnetScore >= 70 and magnetScore[1] < 70
   ```

---

## 5. Session Overlap Detection

### Pattern
Two session booleans ANDed together = overlap window:
```pine
bool londonNyOverlap = isLondon and isNY
bool asiaLondonOverlap = isAsia and isLondon
string sessionOverlapText = londonNyOverlap ? "伦纽重叠" : asiaLondonOverlap ? "亚伦重叠" : ""
```

### Display
Show in header line and confirmation line with ⚡ emoji:
```pine
string overlapHint = sessionOverlapText != "" ? " ⚡" + sessionOverlapText : ""
```

### Why It Matters
- London-NY overlap (typically 13:00-16:00 UTC) is the highest-liquidity window for forex
- Asia-London overlap marks the transition from Asian range to London manipulation
- Community sources: Dukascopy, Forex.com — "best time to trade forex is during session overlaps"

---

## Resource Impact After All Fixes

| Metric | Before | After | Limit |
|---|---|---|---|
| plot() | 31 | 31 | 64 |
| request.security | 9 | 8 | 40 |
| alertcondition | 10 | 13 | — |
| barstate.isconfirmed | 0 | 2 | — |

The DXY tuple merge saved 1 request.security call. The 2 `barstate.isconfirmed` usages protect sweep detection from repainting on real-time bars.