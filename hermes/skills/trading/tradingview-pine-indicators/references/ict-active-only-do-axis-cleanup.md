# ICT Active-Only and DO Axis-Only Cleanup

Use this when the user says active session highs/lows should not appear before the session ends, or when Daily Open should appear only on the right price axis.

## Active Session High/Low Rule

Wrong pattern:
- Create high/low line objects at session start.
- Hide them with `color=na`, blank label text, or `label.style_none` while the session is active.
- Keep pushing those objects into `levels[]` immediately.

Why it is wrong:
- The chart still has high/low objects during the live session.
- Sweep/merge/cleanup logic may treat them as real levels.
- The user sees final-looking highs/lows before the session has ended.

Correct pattern:
1. On `justStarted`, initialize `sOpen/sHigh/sLow/sClose/sHighBar/sLowBar/startTime` only.
2. If `SHOW_OPEN_ONLY_ACTIVE` is false, create/update high/low objects during the session as usual.
3. If `SHOW_OPEN_ONLY_ACTIVE` is true, do not create high/low lines or labels while `isSession` is true.
4. Still update `sHigh/sLow` and their bar indexes internally during the active session.
5. On `not isSession and isSession[1]`, materialize the final high/low lines and labels from stored extrema, push them into `levels[]`, then mark `isActive=false`.
6. Merged-label logic should continue excluding active levels when open-only mode is enabled.

## Daily Open Axis-Only Rule

When the user wants DO as a right-axis price only:
1. Keep `var float dOpenToday = na`.
2. Update it on new day: `if ta.change(time("D")) != 0 -> dOpenToday := open`.
3. Initialize it on first bar if `na`.
4. Keep `axisDo = SHOW_AXIS_DO_LEVEL ? dOpenToday : na` and the final price-scale `plot()`.
5. Remove the chart-line object (`var line doLine`), line creation/update/delete code, `SHOW_DO_LINE`, `DO_WIDTH`, `DO_STYLE_IN`, and line-only color inputs if no longer used.
6. Use a fixed color or an existing axis-level color for the price-scale plot so no dead DO line styling inputs remain.

## Verification

After patching, grep for zero residuals:
- `SHOW_DO_LINE`
- `doLine`
- `DO_WIDTH`
- `DO_STYLE_IN`
- `activeSize`
- `levelMaxDuration`

Also verify:
- `SHOW_OPEN_ONLY_ACTIVE` defaults to the requested behavior.
- `axisDo` and `DO Price` price-scale plot still exist.
- `plotshape=0`, `strategy=0`, and output count remains under TradingView's 64 limit.
