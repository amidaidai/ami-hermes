# No-Table Dashboard Variant Pattern

Use when the user asks to delete/remove the on-chart table from a Pine overlay dashboard, but the script also uses that table's variables as part of a decision engine.

## Goal

Create a clean chart version with no `table.*` output or table settings, while preserving:
- DMI/decision scoring
- A/B/C/X grade state
- CVD confirmation and divergence logic
- high-timeframe filters
- `alertcondition()` signals
- Data Window diagnostics such as CVD values

## Safe Removal Steps

1. Search for all table-specific constructs before editing:
   - `table.`
   - `table.new(`
   - `SHOW_*TABLE`
   - `TABLE_VIEW_MODE`
   - table position/font/color inputs
   - table helper functions such as `f_*_cell`, `f_*_pos`, `f_*_size`
2. Split table settings from engine settings:
   - Remove only display controls such as table position, font, cell colors, compact/detail mode, and show-table toggles.
   - Keep engine controls such as HTF filter, acceptance bars, key-level gating, grade stability, ADX/DI thresholds, and CVD key-level filters.
3. Delete helper functions and variables used only for rendering the table.
4. Delete the `if barstate.islast` table rendering block entirely.
5. Keep computed decision strings/variables if they feed alerts, data-window output, external TV bridge reads, or future diagnostics.
6. Save as a new versioned file such as `*_no_table.pine` unless the user explicitly asks to overwrite the original.

## Verification

Run text-level checks after writing the new file:

```text
no table api: `table.` not in source and `table(` not in source
no table variables: old table prefix not in source, e.g. `DMI_TABLE`
decision grade kept: `setupGradeText` exists
alerts kept: `alertcondition(` exists
cvd diagnostics kept: `CVD Value` and `CVD Slope` exist when applicable
htf filter kept: `USE_HTF_FILTER` exists when applicable
```

Also search for user-facing stale settings like `表格位置`, `表格字体`, `表头背景`, `单元格背景`, and `显示决策表`.

## Pitfalls

- Do not remove the decision engine just because the table is called a “decision table”. In mature SVP/ICT/VWAP/EMA/CVD dashboards, the table is often only the display layer; the grade and alert logic should survive.
- Do not leave dead table inputs in the TradingView Settings panel. A clean settings panel is part of the deliverable.
- Pine has no local compiler in Hermes; text checks are useful but final syntax must still be compiled in TradingView Pine Editor.
