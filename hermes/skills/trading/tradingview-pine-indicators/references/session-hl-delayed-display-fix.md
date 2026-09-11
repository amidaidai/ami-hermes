# Session H/L Delayed Display Fix (2026-06-25)

## Problem
When `SHOW_OPEN_ONLY_ACTIVE=true`, session high/low labels were supposed to appear after the session ends. Four defects prevented this:

1. **Merge hides labels**: `barstate.islast` merge block at L1251 `label.set_style(lvl.lb, style_none)` hides all individual labels, including the ones just created at session end.
2. **Merged label displacement**: Merge labels created at midpoint positions, and if a level was excluded from merge, it disappeared entirely.
3. **Instant sweep**: If price had already crossed the session H/L by the time the session ended, the level was immediately marked swept (40% opacity → invisible).
4. **cutoffTime drift**: `f_cutoff_ms` used `time` (bar open time) instead of `timenow` (wall clock) on real-time bars, causing off-by-one-bar cutoff errors.

## Fix (6 changes applied)

### 1. ICTLevel UDT: add `isSessionEnd` field
```pine
type ICTLevel
    ...
    bool isHidden
    bool isSessionEnd = false  // NEW
```

### 2. SessionState UDT: add `sEndBar` field
```pine
type SessionState
    ...
    string dayName = ""
    int sEndBar = na          // NEW
    bool ended = false
```

### 3. Session start: initialize `sEndBar`
```pine
if justStarted
    st.ended   := false
    st.sEndBar := na          // NEW
```

### 4. Session end: record bar and mark levels
```pine
if not isSession and isSession[1]
    st.ended := true
    st.sEndBar := bar_index   // NEW
    if allowDraw and SHOW_OPEN_ONLY_ACTIVE ...
        st.lvlHighObj := ICTLevel.new(..., true)   // last arg: isSessionEnd=true
        st.lvlLowObj  := ICTLevel.new(..., true)
```

### 5. Sweep protection window (3-bar grace)
```pine
if isSwept and lvl.isSessionEnd
    int tfSec = timeframe.in_seconds()
    float barsPassed = tfSec > 0 ? (time - lvl.createdAt) / 1000.0 / tfSec : 999
    if barsPassed <= 3.0
        isSwept := false
```

### 6. Merge block: skip session-end levels
```pine
// Original: hides ALL individual labels → replaces with merged
// Fixed: session-end levels keep original labels
if not lvl.swept and not lvl.isHidden 
   and (not lvl.isActive or not SHOW_OPEN_ONLY_ACTIVE) 
   and not lvl.isSessionEnd              // NEW gate
    label.set_style(lvl.lb, label.style_none)
    ...
else if lvl.isSessionEnd and not lvl.swept and not lvl.isHidden
    line.set_x2(lvl.ln, bar_index)       // extend line
    updateLabel(...)                      // refresh label
```

### Bonus: plot() fallback lines (indestructible)
```pine
plot(plotAsiaHigh, "亚洲盘 高", color=COLOR_ASIA, linewidth=ICT_LINE_WIDTH, trackprice=true, display=display.pane)
// ... plus 5 more for AsiaLow, LondonHigh/Low, NYHigh/Low
```

### Bonus: f_cutoff_ms real-time fix
```pine
f_cutoff_ms(int lookbackDays) =>
    int refTime = barstate.islast and barstate.isrealtime ? timenow : time
    int base = refTime - (lookbackDays * 86400 * 1000)
```

## DST Verification
- `Asia/Shanghai` → UTC+8 year-round, no DST ✓
- `Europe/London` → IANA handles BST(UTC+1)/GMT(UTC+0) automatically ✓
- `America/New_York` → IANA handles EDT(UTC-4)/EST(UTC-5) automatically ✓
- Session overlap: London 08:00 BST=Beijing 15:00 (summer) / 08:00 GMT=Beijing 16:00 (winter)
- Cutoff uses `timenow` on real-time bar to prevent off-by-one-bar drift
