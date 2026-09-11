# Complete Day/Week Liquidity Removal Checklist

## Context

When removing a deeply-integrated display feature from a multi-factor Pine Script dashboard, every layer must be audited to avoid compilation errors (`Undeclared identifier`) and runtime errors.

## Four-Layer Removal Checklist

### Layer 1: Settings Inputs (13 items)
```pine
// Remove from SESSIONS_GROUP
SHOW_DAY_LIQUIDITY
SHOW_WEEK_LIQUIDITY
COLOR_DAY_LIQUIDITY
DAY_LIQUIDITY_WIDTH
DAY_LIQUIDITY_STYLE_IN
COLOR_WEEK_LIQUIDITY
WEEK_LIQUIDITY_WIDTH
WEEK_LIQUIDITY_STYLE_IN
DAY_LIQUIDITY_LABEL_SIZE
WEEK_LIQUIDITY_LABEL_SIZE
WEEK_LIQUIDITY_KEEP_DAYS
WEEK_LIQUIDITY_SHOW_ATR
// Remove from VP_ELEMENTS_GROUP
SHOW_AXIS_LIQUIDITY_LEVELS
```

### Layer 2: Global Declarations (12 + style vars)
```pine
// var declarations
prevDayHighLine, prevDayLowLine, prevDayHighLabel, prevDayLowLabel
prevDayHighObj, prevDayLowObj
prevWeekHighLine, prevWeekLowLine, prevWeekHighLabel, prevWeekLowLabel
prevWeekHighObj, prevWeekLowObj
// style vars
day_liquidity_style_str, week_liquidity_style_str
```

### Layer 3: Rendering Logic
```pine
// Pool variables (~8 lines)
newDayPool, newWeekPool, showDayPool, showWeekPool
weekDayDedupThreshold, weekHighDuplicatesDay, weekLowDuplicatesDay
showPrevWeekHigh, showPrevWeekLow

// Day pool creation/cleanup (~30 lines)
if showDayPool and (newDayPool or na(prevDayHighObj) or na(prevDayLowObj)) ... 
if not showDayPool and (not na(prevDayHighObj) or not na(prevDayLowObj)) ...

// Week pool creation/cleanup + sweep tracking (~45 lines)
if showWeekPool and (newWeekPool or ...) ...
prevWeekHighSwept, prevWeekLowSwept
cleanup branches for unswept week levels

// ICT cleanup gate (6 locations)
show_ict_lines or showDayPool or showWeekPool → show_ict_lines
str.contains(lvl.name, "上周") → delete branch
keepSweptLine → delete

// Merge label branching
mergedWeekPool, mergedDayPool → delete
mergeSize ternary → simplify to ICT_UNSWEPT_LABEL_SIZE

// Action panel pool proximity (~26 lines)
actionDayPoolText, actionWeekPoolText, actionDayWeekSuffix → delete block
actionLine2 → remove actionDayWeekSuffix reference

// Right axis (~5 lines + 1 plot)
axisPrevDayHigh, axisPrevDayLow, axisPrevWeekHigh, axisPrevWeekLow → delete
axisLiquidityEncoded → delete
plot(axisLiquidityEncoded, ...) → delete
```

### Layer 4: Data Window Plots
Remove the axleiquidityEncoded plot. Output count drops by 1.

## Preserve / Remove Decision Rule
- If the user asks only to hide chart drawings, preserve `request.security()` calls for `prevDayHigh`, `prevDayLow`, `prevWeekHigh`, `prevWeekLow` because they still feed internal support/resistance and key-level proximity scoring.
- If the user says to delete/remove previous-day or previous-week levels outright, remove hidden decision influence too: delete the `request.security()` calls, support/resistance candidates, `nearCvdLiquidity`, `nearAKeyLiquidity`, action-panel pool suffixes, and all day/week identifiers. Verify residual count is zero for `prevDay`, `prevWeek`, `DAY_LIQUIDITY`, and `WEEK_LIQUIDITY`.
- Preserve all SVP/VWAP/EMA/CVD/ICT session functionality unless explicitly requested otherwise. In particular, do not delete SVP extremes or SVP price data when removing day/week pools.

## Verification
```bash
grep -c "SHOW_DAY_LIQUIDITY\|SHOW_WEEK_LIQUIDITY\|showDayPool\|showWeekPool\|prevDayHighObj\|prevWeekHighObj\|actionDayPool\|actionWeekPool" file.pine
# Expected: 0 for all removed identifiers
grep -c "svpHighPrice\|svpLowPrice\|SHOW_SVP_EXTREMES" file.pine
# Expected: >0 — SVP extremes untouched
```

## Result
- Lines reduced: ~150
- Output series reduced: 1 (25→24)
- Compiles clean on first add-to-chart after verification

## Editing Approach

The Hermes `patch` tool fails with "Escape-drift detected" on Pine Script content containing literal `\"` sequences (tooltips, `str.replace()` calls). When removing a feature with 10+ changed lines across the file, prefer `terminal` with a Python script that reads lines, marks ranges to skip, handles inline modifications, and writes back:

```python
# Pattern: read lines, build to_skip set, process line-by-line
to_skip = set()
# Add line index ranges (0-based) for complete-deletion blocks
for i in range(settings_start, settings_end): to_skip.add(i)
# For inline modifications, check line content and rewrite
if 'old_pattern' in line:
    line = 'new content\n'
```

After the Python pass, follow with individual `patch` calls for remaining single-line residuals, then verify zero residuals with `grep -c`. This avoids the escape-drift deadlock entirely for bulk edits.

## Preserved Internal Data

`prevDayTime` (from `request.security("D", time[1], ...)`) is kept because `f_day_name_from_time(prevDayTime)` is used in support/resistance nearest-price naming even after display logic is removed. The data feeds `supName`/`resName` labels like `周三高`/`周三低` in the internal decision engine — these do not appear on chart but influence the `nearCvdLiquidity` and `nearAKeyLiquidity` proximity checks.
