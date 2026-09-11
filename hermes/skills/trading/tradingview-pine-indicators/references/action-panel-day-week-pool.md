# Action Panel Day/Week Pool Proximity Pattern (2026-06-24)

Append compact day/week liquidity pool proximity labels to the `结构：` line in the top-right action panel table.

## Data Source

```pine
float prevDayHigh = request.security(syminfo.tickerid, "D", high[1], barmerge.gaps_on, barmerge.lookahead_on)
float prevDayLow  = request.security(syminfo.tickerid, "D", low[1],  barmerge.gaps_on, barmerge.lookahead_on)
float prevWeekHigh = request.security(syminfo.tickerid, "W", high[1], barmerge.gaps_on, barmerge.lookahead_on)
float prevWeekLow = request.security(syminfo.tickerid, "W", low[1], barmerge.gaps_on, barmerge.lookahead_on)
```

**Critical**: Use `barmerge.gaps_on` (NOT `gaps_off`) — with `gaps_off`, the value is `na` most of the time on intraday charts. `gaps_on` forward-fills to every bar. Use `lookahead_on` because the previous period's bar is always completed.

## Proximity Computation

Insert before `actionLine2` definition:

```pine
string actionDayPoolText = ""
if SHOW_DAY_LIQUIDITY and not na(prevDayHigh) and not na(prevDayLow)
    float dayNearAtr = currATR * 0.8
    if close > prevDayHigh
        actionDayPoolText := "日↑"       // breakout above yesterday's high
    else if close < prevDayLow
        actionDayPoolText := "日↓"       // breakdown below yesterday's low
    else if prevDayHigh - close <= dayNearAtr
        actionDayPoolText := "近日高"    // approaching resistance
    else if close - prevDayLow <= dayNearAtr
        actionDayPoolText := "近日低"    // testing support

string actionWeekPoolText = ""
if SHOW_WEEK_LIQUIDITY and not na(prevWeekHigh) and not na(prevWeekLow)
    float weekNearAtr = currATR * 0.8
    if close > prevWeekHigh
        actionWeekPoolText := "周↑"
    else if close < prevWeekLow
        actionWeekPoolText := "周↓"
    else if prevWeekHigh - close <= weekNearAtr
        actionWeekPoolText := "近周高"
    else if close - prevWeekLow <= weekNearAtr
        actionWeekPoolText := "近周低"

string actionDayWeekSuffix = actionDayPoolText != "" ? " · " + actionDayPoolText + (actionWeekPoolText != "" ? " " + actionWeekPoolText : "") : actionWeekPoolText != "" ? " · " + actionWeekPoolText : ""
```

## Append to Structure Line

```pine
string actionLine2 = "结构：SVP " + actionValueText + " · VWAP " + actionVwapText + " · EMA " + actionEmaText + actionDayWeekSuffix
```

## Visibility Logic

| Condition | Label | Meaning |
|-----------|-------|---------|
| `close > prevDayHigh` | `日↑` | Breakout above yesterday's high |
| `close < prevDayLow` | `日↓` | Breakdown below yesterday's low |
| Near day high (≤0.8 ATR) | `近日高` | Testing resistance |
| Near day low (≤0.8 ATR) | `近日低` | Testing support |
| Mid-range (default) | _(hidden)_ | No key boundary nearby |
| Same logic for week | `周↑`/`周↓`/`近周高`/`近周低` | |

Only shows when `SHOW_DAY_LIQUIDITY`/`SHOW_WEEK_LIQUIDITY` is enabled and data is not `na`.

## Pitfalls

- **`currATR` must be defined before this block** — it's typically `ta.atr(14)` defined at the top of the script. Pine is single-pass sequential.
- **Don't duplicate the `WEEK_LIQUIDITY_SHOW_ATR` filter** for the action panel — the chart rendering already handles distance filtering. The action panel shows position relative to week levels regardless of distance (week breakout is always relevant).
- **The suffix is only `" · " + text` when appended** — the format `" · " + dayText + " " + weekText` matches the existing ` · SVP ... · VWAP ...` visual style.
