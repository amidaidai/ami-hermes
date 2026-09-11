# Complete SVP Extremes Removal Checklist

## Context

When removing the SVP (Volume Profile) high/low extreme sweep lines from a multi-factor Pine Script dashboard. This is a display feature deeply integrated across settings, rendering, decision logic, and alerting. Must preserve `svpHighPrice`/`svpLowPrice` data values for support/resistance and CVD key-level proximity calculations.

## Key Distinction from Day/Week Liquidity Removal

- Day/week removal: kept `request.security()` data fetches for sup/res
- **SVP removal: the data assignment was inside the deleted pool creation block — must be re-injected elsewhere**
- Both: delete all rendering/display/settings, keep sup/res + CVD proximity logic

## Six-Layer Removal Checklist

### Layer 1: Settings Inputs (6 items)
```pine
// Remove from VP_ELEMENTS_GROUP
SHOW_SVP_EXTREMES
SVP_EXTREME_COLOR
SVP_EXTREME_WIDTH
SVP_EXTREME_STYLE_IN
SVP_EXTREME_LABEL_SIZE
SVP_LOOKBACK_DAYS
```

### Layer 2: Var Declarations (6 items — KEEP svpHighPrice/svpLowPrice)
```pine
// DELETE
var line svpHighLine = na
var line svpLowLine = na
var label svpHighLabel = na
var label svpLowLabel = na
var ICTLevel svpHighObj = na
var ICTLevel svpLowObj = na
// KEEP
var float svpHighPrice = na
var float svpLowPrice = na
```

### Layer 3: Style Var + Helper Simplification
```pine
// DELETE
svp_style_str = f_get_style(SVP_EXTREME_STYLE_IN)

// updateLabel: simplify isSvpPool/activeSize/sweptSize
// BEFORE:
bool isSvpPool = (str.contains(name, " 高") or str.contains(name, " 低"))
    and not str.contains(name, "亚洲盘") and not str.contains(name, "伦敦盘")
    and not str.contains(name, "纽约盘")
string activeSize = isSvpPool ? SVP_EXTREME_LABEL_SIZE : ICT_UNSWEPT_LABEL_SIZE
string sweptSize = isSvpPool ? size.small : ICT_SWEPT_LABEL_SIZE
// AFTER:
string activeSize = ICT_UNSWEPT_LABEL_SIZE
string sweptSize = ICT_SWEPT_LABEL_SIZE

// levelMaxDuration: drop priority 6 branch
// BEFORE: int levelMaxDuration = lvl.priority == 6 ? SVP_LOOKBACK_DAYS * 86400 * 1000 : max_duration
// AFTER:  int levelMaxDuration = max_duration
```

### Layer 4: Rendering Logic (~90 lines)
```pine
// SVP cleanup block
if barstate.islast and not SHOW_SVP_EXTREMES and (not na(svpHighObj) or not na(svpLowObj))
    f_delete_liquidity_pair(svpHighLine, svpLowLine, svpHighLabel, svpLowLabel, svpHighObj, svpLowObj)
    // ... all na := assignments

// SVP pool creation block (~40 lines)
// Inside the weekly period reset block:
if SHOW_SVP_EXTREMES and not na(profileEngine.maxProfilePrice) ...
    svpHighPrice := profileEngine.maxProfilePrice
    svpLowPrice := profileEngine.minProfilePrice
    // color matching, f_make_liquidity_level, line/label assignment
    // DELETE ENTIRE BLOCK
```

### Layer 5: Dead Functions (3 functions — after SVP these have zero callers)
```pine
f_remove_level_from_array(ICTLevel target)
f_delete_liquidity_pair(line hiLine, line loLine, label hiLabel, label loLabel, ICTLevel hiObj, ICTLevel loObj)
f_make_liquidity_level(float price, bool isHigh, string name, color col, int prio, string labelSize, int lineWidth, lineStyle)
```

### Layer 6: Action Panel + Alerts
```pine
// DELETE action panel SVP pool proximity (actionSvpPoolText, actionSvpSuffix)
// DELETE actionSvpSuffix from actionLine2
// DELETE sweep alert vars: svpHighNowSwept, svpLowNowSwept, svpHighWasSwept, svpLowWasSwept
// DELETE alertcondition(alertSvpHighSwept, ...)
// DELETE alertcondition(alertSvpLowSwept, ...)
```

## ⚠ CRITICAL: Data Reassignment Pitfall

`svpHighPrice` and `svpLowPrice` were set inside the deleted SVP pool creation block. After removal, they stay `na` forever, silently breaking:
- `supPrice` detection at `svpLowPrice`
- `resPrice` detection at `svpHighPrice`
- `nearCvdLiquidity` (still works via prevDay/Week but loses SVP input)
- `nearAKeyLiquidity` (same)

**Fix — re-inject at the barstate.islast process block:**
```pine
if barstate.islast and not na(profileEngine.minProfilePrice) and not na(currentProfileStart)
    profileEngine.processAndRender(currentProfileStart, bar_index, true)
    svpHighPrice := profileEngine.maxProfilePrice
    svpLowPrice := profileEngine.minProfilePrice
```

This captures the running Volume Profile's max/min on the last bar, maintaining sup/res ≈ internal support/resistance anchor detection.

## Verification
```bash
grep -c "SHOW_SVP_EXTREMES\|SVP_EXTREME_COLOR\|SVP_EXTREME_WIDTH\|SVP_EXTREME_STYLE_IN\|SVP_EXTREME_LABEL_SIZE\|SVP_LOOKBACK_DAYS\|svp_style_str\|svpHighObj\|svpLowObj\|svpHighLine\|svpLowLine\|svpHighLabel\|svpLowLabel\|isSvpPool\|actionSvpPoolText\|actionSvpSuffix\|svpHighNowSwept\|svpLowNowSwept\|svpHighWasSwept\|svpLowWasSwept\|alertSvpHighSwept\|alertSvpLowSwept\|f_delete_liquidity_pair\|f_make_liquidity_level\|f_remove_level_from_array" file.pine
# Expected: 0 for all removed identifiers

grep -c "svpHighPrice\|svpLowPrice" file.pine
# Expected: >0 — data values preserved for sup/res + CVD proximity
```

## Result
- Lines reduced: ~170
- Support/resistance + CVD key-level logic preserved
- Dead functions removed (3)
- Alerts removed (2)
- Action panel simplified
- Compiles clean on first add-to-chart
