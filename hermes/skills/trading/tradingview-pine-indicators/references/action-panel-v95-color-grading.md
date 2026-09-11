# v9.5 Action Panel Color Grading

## Final Design: White text + opaque backgrounds (2026-06-24, iterated 3x with user)

This user iterated the color scheme three times before settling:
1. First attempt: multi-color transparent backgrounds + conditional white/gray text → **user rejected** ("这个颜色应该是黑色，不然的话看不清啊")
2. Second attempt: black text + semi-transparent backgrounds → **user rejected** ("字好像有点难看清啊")
3. **Final (accepted)**: **white text on opaque backgrounds** — high contrast, thick color blocks, no ambiguity

The core insight: on TradingView's dark background, semi-transparent colors wash out and make text (black or white) hard to read. The solution is to make backgrounds MORE opaque (lower transparency) so the color block itself provides the contrast surface for white text.

### Priority-ordered ternary chain (final, accepted)

```pine
// v9.5: Adaptive action panel colors — opaque backgrounds + white text for max readability
color actionBgColor = lowLiquiditySession                      ? color.new(color.blue, 20) :
                      setupX                                    ? color.new(color.red, 25) :
                      cvdConflictLong or cvdConflictShort       ? color.new(color.orange, 20) :
                      displayLongA                              ? color.new(color.green, 8) :
                      displayShortA                             ? color.new(color.red, 8) :
                      setupLongB                                ? color.new(color.green, 22) :
                      setupShortB                               ? color.new(color.red, 22) :
                      setupLongC                                ? color.new(#00897B, 22) :
                      setupShortC                               ? color.new(#C62828, 22) :
                      trendLongScore >= trendShortScore + 2     ? color.new(color.green, 45) :
                      trendShortScore >= trendLongScore + 2     ? color.new(color.red, 45) :
                      color.new(color.gray, 65)
color actionTextColor = color.white
```

### Signal-to-color mapping (final, accepted)

| Priority | State | Color | Transparency | Visual |
|---|---|---|---|---|
| 1 | Low liquidity | `color.blue` | 20 | 🟦 Blue dormant, clear |
| 2 | X (no chase) | `color.red` | 25 | 🟥 Warning red |
| 3 | CVD conflict | `color.orange` | 20 | 🟧 Orange alert |
| 4 | A long | `color.green` | 8 | 🟩 Deep green (near-opaque, strongest buy) |
| 5 | A short | `color.red` | 8 | 🟥 Deep red (near-opaque, strongest sell) |
| 6 | B long | `color.green` | 22 | 🟩 Medium green |
| 7 | B short | `color.red` | 22 | 🟥 Medium red |
| 8 | C long | `#00897B` (teal) | 22 | 🔷 Teal-green (waiting) |
| 9 | C short | `#C62828` (dark red) | 22 | 🔶 Dark red (waiting) |
| 10 | Trend bias long | `color.green` | 45 | 🟩 Faint green hint |
| 11 | Trend bias short | `color.red` | 45 | 🟥 Faint red hint |
| 12 | Neutral/watch | `color.gray` | 65 | ⬜ Near-transparent, doesn't distract |

## Design Rules (final, user-validated)

1. **Text always `color.white`** — white on colored backgrounds = max contrast on dark TV theme.
2. **Backgrounds must be opaque enough**: A-grade at 8 transparency (near-solid), B/C at 22, trend hints at 45, neutral at 65+. The "faint hint" approach with black text failed because semi-transparent colors on dark backgrounds create muddy low-contrast surfaces.
3. **Priority order matters**: X/no-chase and CVD conflict checked BEFORE grade signals → warnings visually override trading plans.
4. **Low liquidity is first**: always show blue/dormant before checking trading signals.
5. **Never use `color.black` text** with transparent backgrounds on dark themes — the user explicitly rejected this twice.
6. **Use hex for non-standard colors**: `#00897B` (material teal-600), `#C62828` (material red-800).

## Iteration history (why this became the final design)

| Attempt | Text | Background approach | User verdict |
|---|---|---|---|
| v1 | `color.white` （深色背景）/ `color.gray`（浅色背景）| Semi-transparent (5-10) | ❌ "字好像有点难看清" |
| v2 | `color.black` | Medium-transparent (12-82) | ❌ "这个颜色应该是黑色...看不清" |
| v3 | `color.white` | Opaque (8-65) | ✅ Accepted |

The pattern: **opaque colored blocks + white text** wins. The "semi-transparent wash" aesthetic (common in other TV dashboards) doesn't work for this user's small font single-cell panel.
