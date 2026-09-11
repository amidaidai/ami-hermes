# Pine Normalization + Community Refactor Pattern

Use when the user asks to normalize/refactor an existing mature Pine dashboard and explicitly wants community comparison first.

## Sequence

1. Search/community-check before editing: TradingView public scripts, Reddit/TradingView discussions, Pine docs, and known community patterns.
2. Preserve user anchor preferences and decision-engine weights unless they explicitly ask to change them. For this user's SVP/ICT/VWAP/EMA/CVD stack, do not casually change S-VWAP anchor, CVD anchor, SVP anchor, or A/B/C/X scoring.
3. Audit inputs by reference count before deleting anything:
   - `count == 1` means declared but unused: safe candidate.
   - `count == 2` usually means declared + consumed once: real control, do not delete by default.
   - Delete only display-only controls that do not feed scoring, execution, alerts, drawing, or price-axis logic.
4. Pine v5 cannot rely on newer `input.*(active=...)` settings-panel gray-out patterns. For v5, settings hygiene means deleting dead controls or grouping/renaming; do not import v6-only input behavior.
5. Keep the action panel one cell, no `plotshape()`, no extra table, no ticker in header.
6. If the user asks for a true 6-line action panel, count the header as one line. Assemble exactly:
   - header
   - `结论：`
   - `结构：`
   - `位置：`
   - `确认：`
   - `资金/核对：`
   - `执行：`
   This is seven conceptual fields but six visible line breaks after header consolidation; if strict six visible rows are required, merge `资金/核对` into the same row and keep only six content segments total.
7. Remove repeated direction/module prefixes:
   - Direction lives in `结论`; `执行` should say `等<level>承接/承压 · 失效:<condition>`.
   - Row template provides module context; avoid `ICT ICT...` or `CVD CVD...` duplication.

## Verification

- Re-run unused input scan and require no `count <= 1` input variables.
- Verify removed identifiers have zero residuals.
- Count output-like calls: `plot(` + `fill(` + `bgcolor(` + `table.new(`, keep under 64.
- Verify `plotshape=0`, `strategy=0`, bracket/parenthesis balance is zero.
- Sync Desktop `.txt` and upload copy; compare SHA before reporting.
- Final Pine syntax must still be compiled in TradingView Pine Editor; local text checks are not a compiler.
