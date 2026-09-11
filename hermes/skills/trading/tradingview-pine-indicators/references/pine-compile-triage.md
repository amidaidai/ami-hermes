# Pine compile triage: dashboard indicators

Use this reference when a Pine indicator compiles in stages after large dashboard edits.

## Durable Pine pitfalls from SVP/ICT dashboard work

1. **Declaration order is semantic.** Pine scripts are single-pass: a variable used at line N must already be declared above line N. If adding derived dashboard text such as `tfRoleRec`, `magnetDir`, `rrText`, or target/stop strings, place it after every dependency is declared and calculated. Common failure: `Undeclared identifier 'marketCrypto'` when a market-specific string is inserted before `marketCrypto/marketMetal/...` bools.

2. **`alertcondition()` messages must be const strings.** The `message` argument cannot concatenate series values (`str.tostring(close)`, dynamic labels, score variables, symbol-dependent text). Keep messages static, e.g. `"A多 入场"`, and expose dynamic context through table rows, labels, Data Window plots, or separate alert conditions. If dynamic messages are needed, use Pine alert mechanisms that support series strings, not `alertcondition()`.

3. **Hoist stateful TA calls out of conditionals.** Warnings like `ta.highest should be called on each calculation` usually mean `ta.highest()`/`ta.lowest()` sits inside a ternary or scoped branch. Compute it unconditionally first, then choose `na` with a ternary:
   - Good: `rawHigh = ta.highest(src, len)` then `safeHigh = enabled ? rawHigh : na`.
   - Bad: `enabled ? ta.highest(src, len) : na`.

4. **Move blocks, not individual lines, when fixing dependency order.** R:R / Magnet target text depends on nearest-level scan results. Keep this sequence: initialize nearest vars → scan `levels` array and assign nearest price/dist/name/score → calculate `magnetDir`, `magnetTargetText`, `rrRatio`, `rrText`, stop/entry text → build action panel and alerts.

5. **After every Pine edit, run a textual dependency audit before handing back.** Check for uses before declarations of newly introduced identifiers, dynamic `alertcondition` messages, and conditional TA calls. TradingView is the final compiler, but these three checks catch most dashboard-edit regressions.

## Preferred response pattern when user reports TradingView compile errors

- Treat the error list as authoritative; map each line to a class of Pine issue.
- Fix all reported compile blockers before giving the file back.
- Do not claim the indicator is fully fixed until TradingView compilation confirms it; say what was patched and what still needs paste-compile verification.
