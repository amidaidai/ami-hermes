# Weekly Liquidity Pools as ICT Sweep Lines

Use this reference when adding or fixing previous-week high/low (`上周 高/低`) liquidity pools in a Pine overlay indicator that already has ICT session levels.

## Problem Pattern

A weekly liquidity pool can be implemented as an `ICTLevel`, but still behave incorrectly if:

- It is hidden by generic `HIDE_SWEEPS_ON_HTF` logic after being swept.
- A distance filter deletes the weekly level after it has already been swept.
- Merged labels hard-force a size such as `size.tiny`, ignoring user-facing label inputs.
- `updateLabel()` applies the generic ICT label size instead of the weekly-pool label size.

For this user, weekly levels are structural evidence. Once swept, they should remain visible as a swept line rather than disappear.

## Durable Pattern

1. Keep weekly high/low as `ICTLevel` objects in the same `levels` array as ICT session levels so they share sweep detection, key-level checks, and CVD gating.
2. Add a proximity filter only for unswept weekly levels:
   - `showPrevWeekHigh = showWeekPool and abs(prevWeekHigh - close) <= currATR * WEEK_LIQUIDITY_SHOW_ATR`
   - `showPrevWeekLow = showWeekPool and abs(prevWeekLow - close) <= currATR * WEEK_LIQUIDITY_SHOW_ATR`
3. When a weekly level is already swept, do not remove it just because it is now outside the distance filter:
   - remove only when `not showPrevWeekHigh and not na(prevWeekHighObj) and not prevWeekHighObj.swept`
   - same for low.
4. On sweep, preserve weekly swept lines even on H1+ when normal ICT swept lines are hidden:
   - `keepSweptLine = str.contains(lvl.name, "上周")`
   - hide only when `HIDE_SWEEPS_ON_HTF and isH1OrHigher and not keepSweptLine`
5. Swept formatting should match ICT:
   - line color faded, dashed style, `line.set_x2(..., bar_index)`
   - label updated through the same `updateLabel(..., isSwept=true)` path.

## Label Sizing Rules

For this user:

- Generic unswept ICT labels default to `size.small`.
- Generic swept labels default to `size.tiny`.
- Weekly unswept labels use `WEEK_LIQUIDITY_LABEL_SIZE`, default `size.small`.
- Weekly swept labels use `ICT_SWEPT_LABEL_SIZE`, default `size.tiny`.
- Merged unswept labels should follow `ICT_UNSWEPT_LABEL_SIZE`; do not hard-force `size.tiny` unless the user explicitly asks for always-compact labels.

Suggested `updateLabel()` sizing branch:

```pine
bool isH1 = timeframe.in_seconds() == 3600
bool isWeekPool = str.contains(name, "上周")
string activeSize = isWeekPool ? WEEK_LIQUIDITY_LABEL_SIZE : isH1 ? size.tiny : ICT_UNSWEPT_LABEL_SIZE
string sweptSize = ICT_SWEPT_LABEL_SIZE
string sz = isSwept ? sweptSize : activeSize
```

## Verification Checklist

- `//@version=5` remains unchanged unless a version migration is intentional.
- `alertcondition()` count is unchanged.
- Only one live table cell remains if the indicator uses the single action-panel pattern.
- `上周 高/低` levels are present in the ICT level array.
- Unswept weekly levels can be distance-filtered independently for high and low.
- Swept weekly levels persist as faded dashed lines with tiny labels.
- No dead `if false` compatibility blocks remain.
- No very long Pine lines (`>320` chars) are introduced.
