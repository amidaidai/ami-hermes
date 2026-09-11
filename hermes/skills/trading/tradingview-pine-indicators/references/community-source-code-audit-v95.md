# Community-Informed Pine Source Audit Pattern

Use when the user asks to audit an uploaded TradingView Pine indicator against X/Reddit/TradingView/GitHub/community consensus, without necessarily editing the file.

## Workflow

1. Load `tradingview-pine-indicators`, `tradingview-indicator-analysis`, and a web/search skill when available.
2. Read the uploaded Pine source and run a structural scan before making claims:
   - Pine version and `indicator()` limits.
   - Counts of `plot()`, `fill()`, `bgcolor()`, `table.new()`, `alertcondition()`.
   - Counts and line numbers for `request.security()` and `request.security_lower_tf()`.
   - Presence/absence of `plotshape()`, `strategy.*`, trade-control remnants, FVG/OB/MSS/displacement terms.
   - Residual identifiers after feature removal: when deleting a feature, grep every removed family (`prevDay`, `prevWeek`, `DAY_LIQUIDITY`, `WEEK_LIQUIDITY`, action-panel suffix vars, hidden CVD/key-level gates) and require zero residuals unless explicitly preserved.
   - Presence of CVD quality/freshness controls (`cvdQuality`, min lower-timeframe samples, signal half-life) and forward calibration feedback (`calLong`, `calShort`, hit-rate warnings). Missing these is a P1/P2 audit deduction even when base CVD logic exists.
   - Defaults for known visibility/color traps: `POC_COLOR`, `SHOW_OPEN_ONLY_ACTIVE`, `SHOW_DO_LINE`, `actionTextColor`, `bgcolor()`.
3. Search community sources in parallel:
   - TradingView/LuxAlgo/PineCoders for VP/VWAP/Pine limitations.
   - Reddit `r/TradingView` for Pine dashboard, VP, `security_lower_tf`, and performance pitfalls.
   - X search for current order-flow consensus around VWAP/CVD/liquidity sweep/ICT/VP.
   - GitHub for open Pine/dashboard implementations only as pattern inspiration, not as proof of profitability.
4. Synthesize community consensus into a short model, then compare the source line-by-line against that model.
5. Output P0/P1/P2 recommendations, not a generic essay. For each issue, cite the source file line and the community reason.

## Consensus Model for This Indicator Class

For SVP/ICT/VWAP/EMA/CVD dashboards, the strongest community-backed sequence is:

`HTF bias → liquidity sweep → displacement/MSS/acceptance → VWAP/VP value retest → CVD absorption/divergence confirmation → price-aware invalidation`

Volume Profile provides value context (`POC/VAH/VAL/HVN/LVN`), VWAP gives institutional fair-value bias, EMA/DMI provide trend filter, and CVD should confirm at key levels rather than create standalone direction.

## User-Specific Audit Rules

- Do not recommend adding chart clutter (`bgcolor()`, `plotshape()`, marker spam). If `bgcolor()` is present, flag it as a visual-clutter regression unless the user explicitly asked for it.
- Do not re-add trade controls or strategy-only logic. Keep the script as `indicator()`, not `strategy()`.
- The user dislikes FVG/OB modules in this dashboard. If community consensus mentions FVG/OB, translate the useful part into a lightweight `displacement/MSS/acceptance` filter instead of adding FVG/OB drawings.
- For live action panels, preserve the compact single-cell panel. Prefer white text on opaque state-colored backgrounds, `size.small`, Chinese colon labels, and no ticker name in the header.
- Flag default visibility traps: near-black POC on dark charts, `SHOW_OPEN_ONLY_ACTIVE=true`, `SHOW_DO_LINE=false`, and black action-panel text.
- Treat CVD as approximate unless backed by lower-timeframe samples and volume. A good script should expose CVD quality/sample state and avoid upgrading A/B signals when quality is weak or stale.

## Recommended Output Shape

- `社区共识`: 3-5 bullets summarizing what X/Reddit/TradingView/GitHub agree on.
- `源码优点`: concrete positives already implemented.
- `P0`: compile/visibility/visual-regression issues that should be fixed first.
- `P1`: decision-engine improvements such as displacement/MSS/acceptance gating, CVD/SMT key-level gating, and ADX no-chase refinements.
- `P2`: maintainability and panel hygiene.
- Finish with a score and the next version theme, e.g. `v9.6: no-bgcolor, white action text, MSS/displacement filter, safer defaults`.
