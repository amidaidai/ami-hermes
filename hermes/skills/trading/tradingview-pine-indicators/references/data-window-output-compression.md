# Data Window Output Compression Pattern (2026-06-25)

## Problem
TradingView Free plan limits scripts to 64 output series (plots + fills + bgcolors). Mature multi-factor dashboards easily accumulate 30-50 diagnostic Data Window plots that serve external script consumption rather than visual chart use.

## Pattern: Encode Multiple Values Into Single `plot()`

Use digit-space multiplication to pack multiple related values into one encoded float. External wrapper scripts decode with integer division and modulo.

### Before (wasteful — 7 individual plots)
```pine
plot(replaySideCode, title="Replay Side Code", display=display.data_window, ...)
plot(replayGradeCode, title="Replay Grade Code", display=display.data_window, ...)
plot(replayPlanPrice, title="Replay Plan Price", display=display.data_window, ...)
plot(replayInvalidPrice, title="Replay Invalid Price", display=display.data_window, ...)
plot(replayStopEncoded, title="Replay Stop", display=display.data_window, ...)
plot(replayPlanDistance, title="Replay Plan Distance", display=display.data_window, ...)
```

### After (efficient — 2 encoded plots)
```pine
// Replay packed: SideCode*1e6 + GradeCode*1e4 + ΔPrice*100
float replayPacked = not na(replayPlanPrice) ? 
    (replaySideCode * 1000000 + replayGradeCode * 10000 + math.round((replayPlanPrice - close) * 100)) : na
plot(replayPacked, title="Replay (Side*1e6+Grade*1e4+ΔPrice*100)", display=display.data_window, ...)

// Stop distance + Scores
float replayStopEncoded = not na(replayStopDistance) and not na(replayStopAtr) ? 
    replayStopDistance * 100 + replayStopAtr : na
plot(replayStopEncoded, title="Stop Dist*100+ATR", display=display.data_window, ...)
```

## Encoding Rules

1. **Document the decode formula in the plot title** so wrapper scripts know how to unpack
2. **Keep related values together** — replay metrics in one, CVD metrics in another
3. **Use magnitude-safe multipliers** — SideCode ( max ~9) × 1e6 doesn't collide with GradeCode (max ~3) × 1e4
4. **Remove entirely** values that can be inferred from other plots (e.g., SMT Div can go into Session CVD encoded)
5. **Target: <40 total raw `plot()` calls** to leave room for lines/labels/polylines (which are separate limits)

## Series-Color Doubling Rule (2026-06-26, critical)

**A `plot()` with a series (dynamic) color counts as 2 plot slots, not 1.** TV's docs: *"Uses two plot counts for the close and color series."*

### What is a "series color"?
- **Series (counts ×2):** `color=SOME_INPUT_COLOR` where the input is `input.color()` — because `input.color()` returns a `series color` in Pine v5. Also `color=condition ? color.a : color.b` (conditional expression).
- **Constant (counts ×1):** `color=color.red`, `color=#FF0000`, `color.new(color.red, 50)` — literal color references.

### Why this matters
A mature dashboard with 33 `plot()` calls can consume 50+ TV plot slots if most plots use `color=<input_variable>`. This is the #1 cause of "too many plots (N). The limit is 64" errors — the grep count looks fine (30-40) but TV's internal count is 60-70.

### Estimation formula
```
TV_plot_count = (series_color_plots × 2) + (const_color_plots × 1) + fill_count + bgcolor_count
```
If > 60, merge encoded Data Window plots before delivery.

### Concrete merge example (2026-06-26)
4 separate plots → 1 encoded:
```pine
// BEFORE — 4 plots (4 slots)
plot(magnetNearestPrice, ...)
plot(magnetNearestDist, ...)
plot(ictSweptCount, ...)
plot(ictActiveCount, ...)

// AFTER — 1 plot (1 slot)
float magnetIctEncoded = magnetEncoded + ictCountEncoded / 1e5
plot(magnetIctEncoded, title="Magnet+ICT (Mag*1e6+DistA*1e3+ICT/1e5)", ...)
```
Also merged 2 Replay plots → 1: `Side*10 + Grade`. Net: 6→2 plots, saving 4-8 TV slots.

## Actual Savings (棠溪 SVP+ICT+VWAP+EMA+CVD)

| Category | Before | After | Savings |
|----------|--------|-------|---------|
| CVD diagnostics | 3 plots | 1 encoded | -2 |
| WVWAP + MVWAP Data Window | 2 plots | 1 encoded | -1 |
| Replay diagnostics | 6 plots | 2 encoded | -4 |
| SMT Div | 1 standalone | merged into Session CVD | -1 |
| **Total Data Window** | **15** | **7** | **-8** |

Overall: 37→29 plot() calls, total outputs 40→32 (50% margin under 64 limit).
