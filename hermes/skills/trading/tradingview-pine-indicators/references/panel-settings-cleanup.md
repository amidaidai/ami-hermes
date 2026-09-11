# SVP/ICT/VWAP/EMA/CVD Panel & Settings Cleanup Pattern

Use this reference when iterating this user's TradingView Pine overlay dashboards after adding liquidity pools, CVD guards, and a compact action panel.

## User-facing preferences captured

- The right-top action panel must read like professional trading guidance, not terse abbreviations.
- Preferred panel shape: market focus + `结论` + `结构` + `确认` + `执行`.
- Use direct Chinese execution language: e.g. `A多：回踩做多`, `禁追：位置不划算`, `多头减弱：CVD不配合`, `执行｜不追，等CVD重新配合`.
- Keep panel font configurable via an input; default can be `size.normal` when readability matters.
- Settings panel should be ordered by indicator modules: `市场 → SVP → ICT → VWAP → EMA → CVD → 执行/风控`.
- Every `input.*` must control live behavior. Run an unused-input scan and remove or wire any declared-only setting.

## Liquidity pool drawing rules

- 前日高/低 should default to black (`#0F0F0F`) and expose independent color, width, and style controls.
- 上周高/低 should expose independent color, width, and style controls; do not simply reuse ICT line width/style.
- 上周高/低 should avoid duplicate clutter when near 前日高/低. Add a small price-threshold dedupe before drawing week pools.
- If week pools have an ATR-distance display filter, hide/remove only unswept far pools; once swept, keep a faded dashed sweep line as evidence.
- For Pine safety, never access fields on a possibly-`na` user-defined object inside a compound `and` condition. Assign guarded booleans first:
  - initialize `bool prevWeekHighSwept = false`
  - only if `not na(prevWeekHighObj)`, set `prevWeekHighSwept := prevWeekHighObj.swept`
  - then use `prevWeekHighSwept` in removal logic.

## Action panel pattern

Prefer this structure over one long compressed row:

```pine
string actionLine1 = "结论｜" + actionStateText
string actionLine2 = "结构｜" + actionValueText + "；" + actionVwapText + "；" + actionEmaText
string actionLine3 = "确认｜" + actionIctText + "；" + actionCvdText
string actionLine4 = "执行｜不做，等明确触发"
string actionText = marketFocusText + "\n" + actionLine1 + "\n" + actionLine2 + "\n" + actionLine3 + "\n" + actionLine4
```

Good state text examples:

- `A多：回踩做多`
- `A空：反抽做空`
- `B多：轻仓等多`
- `禁追：位置不划算`
- `降级：低流动性`
- `多头减弱：CVD不配合`
- `空头减弱：CVD不配合`

## Verification checklist

Run text-level checks after each versioned output:

- `//@version=5` still present.
- `alertcondition(` count remains the expected count, usually 5 for this dashboard family.
- Exactly one `table.new(` and one `table.cell(` for the single-cell right-top panel.
- No unwanted FVG strings if the user did not request FVG.
- No very long lines (`>320` chars) because Pine parser/debuggability suffers.
- `unused_input_count == 0` using a regex scan over `input.*` variables.
- Confirm `ACTION_PANEL_SIZE` and liquidity style inputs are referenced beyond declaration.
