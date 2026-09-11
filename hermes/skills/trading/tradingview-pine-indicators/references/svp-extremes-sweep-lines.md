# SVP Extreme Sweep Lines (v9.3+)

## When to Use
When adding SVP profile high/low extremes as ICT-style sweep lines that extend right from the profile end bar, share the global `levels[]` array, and participate in sweep detection, merged labels, and the sweep counter.

## 7-Layer Integration Checklist
Every new feature in this dashboard class must touch all seven layers. Miss one and you get `Undeclared identifier` or invisible features.

1. **Input** — `SHOW_SVP_EXTREMES` bool + `SVP_EXTREME_COLOR` + `SVP_LOOKBACK_DAYS` + `SVP_EXTREME_WIDTH` + `SVP_EXTREME_STYLE_IN` + `SVP_EXTREME_LABEL_SIZE`
2. **Persistent vars** — `var line svpHighLine/svpLowLine`, `var label svpHighLabel/svpLowLabel`, `var ICTLevel svpHighObj/svpLowObj`, `var float svpHighPrice/svpLowPrice`
3. **Visibility cleanup** — if `SHOW_SVP_EXTREMES` turned off, `f_delete_liquidity_pair()` + set all vars to `na`
4. **Level creation** — inside `isNewPeriod` block, AFTER `processAndRender()` but BEFORE `profileEngine := ...new()`:
   ```pine
   string svpHighName = f_svp_direction_name(true, time[1])  // "周三 高"
   string svpLowName = f_svp_direction_name(false, time[1])   // "周三 低"
   svpHighObj := f_make_liquidity_level(svpHighPrice, true, svpHighName, svpHighColor, 6, SVP_EXTREME_LABEL_SIZE, SVP_EXTREME_WIDTH, svp_style_str)
   svpLowObj := f_make_liquidity_level(svpLowPrice, false, svpLowName, svpLowColor, 6, SVP_EXTREME_LABEL_SIZE, SVP_EXTREME_WIDTH, svp_style_str)
   line.set_x1(svpHighObj.ln, endBar)  // start at profile end, not bar_index
   line.set_x1(svpLowObj.ln, endBar)
   ```
5. **Action panel** — `actionSvpPoolText` (SVP↑/SVP↓/近SVP高/近SVP低) appended to 结构 line
6. **Decision engine gates** — add `svpHighPrice/svpLowPrice` to `nearCvdLiquidity`, `nearAKeyLiquidity`, `supPrice`/`resPrice` chains
7. **Price axis** — NOT shown on right price axis per user preference (v9.3)

## `f_svp_direction_name()` — Anchor-Aware Naming

```pine
f_svp_direction_name(bool isHigh, int endTime) =>
    string dir = isHigh ? "高" : "低"
    string tf = targetProfileTF
    if tf == "D"
        f_day_name_from_time(endTime) + " " + dir  // "周三 高"
    else if tf == "W"
        "上周 " + dir  // "上周 高"
    else if tf == "M"
        "上月 " + dir  // "上月 高"
    else
        "SVP " + dir    // fallback
```

**Critical**: there MUST be a space between the day/anchor name and direction (`"周三 高"` not `"周三高"`). This user explicitly corrected this — ICT session labels use the same spacing pattern.

## `updateLabel()` SVP Detection

SVP labels participate in the same `updateLabel()` flow as ICT labels. To prevent H1 abbreviation (高→H, 低→L) from corrupting SVP labels, add an `isSvpPool` gate:

```pine
bool isSvpPool = (str.contains(name, " 高") or str.contains(name, " 低")) 
    and not isWeekPool and not isDayPool 
    and not str.contains(name, "亚洲盘") and not str.contains(name, "伦敦盘") 
    and not str.contains(name, "纽约盘")
string activeSize = ... : isSvpPool ? SVP_EXTREME_LABEL_SIZE : ICT_UNSWEPT_LABEL_SIZE
string sweptSize = isSvpPool ? size.small : ICT_SWEPT_LABEL_SIZE
```

Swept SVP labels = `size.small` (user preference).

## Session Color Matching (D-Anchor Only)

Capture previous session extremes when sessions end:
```pine
var float prevSessAsiaHigh/Low = na
var float prevSessLondonHigh/Low = na  
var float prevSessNYHigh/Low = na

// After manageSession calls:
if stAsia.ended
    prevSessAsiaHigh := stAsia.sHigh
    prevSessAsiaLow := stAsia.sLow
// ... same for London, NY
```

At SVP level creation, match with tolerance:
```pine
float svpTol = math.max(syminfo.mintick * 4, math.abs(close) * 0.00005)
if targetProfileTF == "D"
    if f_near(svpHighPrice, prevSessNYHigh, svpTol) → COLOR_NY
    else if f_near(svpHighPrice, prevSessLondonHigh, svpTol) → COLOR_LONDON
    else if f_near(svpHighPrice, prevSessAsiaHigh, svpTol) → COLOR_ASIA
    else → SVP_EXTREME_COLOR (#555555)
```

## Backtrack
- `SVP_LOOKBACK_DAYS = 1` (separate from ICT_LOOKBACK_DAYS)
- In cleanup loop: `lvl.priority == 6 ? SVP_LOOKBACK_DAYS * 86400 * 1000 : max_duration`
- `ICT_LOOKBACK_DAYS` also defaults to `1` per user preference (v9.3)

## Auto-Merge with ICT Labels
SVP levels pushed to `levels[]` via `f_make_liquidity_level()` automatically participate in:
- Sweep detection: `lvl.isHigh ? (high > lvl.price) : (low < lvl.price)`
- Sweep counter: `N扫/M待` in action panel 确认 line
- Merged labels at `barstate.islast`: sorted by price, merged within threshold
- Cleanup: removed when exceeding 1-day max duration
## Pitfalls

- **Timing**: Read `profileEngine.maxProfilePrice` BEFORE `profileEngine := ...new()` replaces the engine reference. `f_clearVpData` clears arrays but scalar fields survive until reassignment.
- **x1 positioning**: `line.set_x1(svpHighObj.ln, endBar)` — must set to profile end bar, not `bar_index` (which is the NEW period's first bar).
- **Color**: User rejected `color.black` (invisible on dark theme), uses `#555555` dark gray. Session-matched colors take priority on D anchor.
- **No price axis**: User explicitly does NOT want SVP extremes on the right price scale. Removed all `axisSvp*` variables and plots.

## SVP Sweep Alerts (v9.3+)

Edge-detection pattern: track sweep state transition with persistent vars, not the steady-state `swept` flag.

```pine
// SVP sweep alerts — detect edge when SVP extreme gets swept
var bool svpHighWasSwept = false
var bool svpLowWasSwept = false
bool svpHighNowSwept = not na(svpHighObj) and svpHighObj.swept
bool svpLowNowSwept = not na(svpLowObj) and svpLowObj.swept
bool alertSvpHighSwept = ENABLE_PRO_ALERTS and svpHighNowSwept and not svpHighWasSwept
bool alertSvpLowSwept = ENABLE_PRO_ALERTS and svpLowNowSwept and not svpLowWasSwept
if barstate.islast
    svpHighWasSwept := svpHighNowSwept
    svpLowWasSwept := svpLowNowSwept

alertcondition(alertSvpHighSwept, "Pro SVP High Swept", "SVP high swept")
alertcondition(alertSvpLowSwept, "Pro SVP Low Swept", "SVP low swept")
```

Key: `svpHighObj` gets recreated each SVP period, so `.swept` resets to `false`. The `svpHighWasSwept` tracker catches the transition from false→true. Reset happens naturally when `svpHighObj` is recreated at the next `isNewPeriod`.
