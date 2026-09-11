# TV→Script Decode Chain: Action Panel v2 (Data Window export removed)

**Context (2026-06-27):** The production SVP v10 主指标 removed its Data Window
encoding export (`plot(display=display.data_window)` for grade/score/CVD/magnet)
to free TradingView's 64-plot quota. Source ends with the comment:
`// Data Window 编码导出已移除（无外部系统读取），以释放 TradingView 64 绘图配额。`

This **silently broke** every script that decoded the old Data Window fields.
The break is invisible: scripts run, write partial/no output, and the automated
cards go half-blind while live MCP analysis still works.

## What changed in the indicator

| Old (removed) | Now available |
|---|---|
| Data Window titles `CVD Value`, `CVD Slope`, `POC Price`, `VAH Price`, `VAL Price`, `Weekly VWAP Data`, `Monthly VWAP Data`, `DO Price` | **Gone from study_values** |
| Decision table rows `等级`, `处理` | **Never existed in action panel v2** |
| — | study_values still has `S VWAP`, `EMA 9/21/34/55` (lines 992, 1080-1083) |
| — | POC/VAH/VAL recoverable from `pine_labels` (text contains POC/VAH/VAL) |
| — | Action panel v2 rows: `结论 / 方向 / 进场 / 止损 / 目标 / 核对 / 磁吸↑ / 磁吸↓` |

**Grade lives inside `结论`**, e.g. `结论 = "A多 回踩"`. There is NO standalone
`等级`/`处理` row. Derive grade by substring on 结论; treatment = the action
phrase after the grade token.

## The three decode-chain bugs (all fixed path-B = scripts adapt, zero TV quota)

1. **Wrong CDP collection.** `fetch_tv_data.cjs` step 6 read tables from
   `dwglabels.get('tables')`. The MCP's own `getPineTables` reads from
   `dwgtablecells` / `tableCells`. Table.new() cells live in `dwgtablecells`.
   **Fix:** mirror the MCP — iterate `pc.dwgtablecells.get('tableCells')`,
   collect `{tid,row,col,t}` cells, rebuild rows as `{col0:label, col1:value}`.

2. **Looked for non-existent rows.** Both cjs and `tv_bridge_wrapper.py` searched
   for `等级`/`处理`. **Fix:** map action-panel labels
   (`结论/方向/进场/止损/目标/磁吸↑/磁吸↓`) to named JSON fields
   `tv_conclusion/tv_direction/tv_entry/tv_stop/tv_target/tv_magnet_up/tv_magnet_down`,
   then derive `tv_grade` from 结论.

3. **Quality gate required gone fields.** cjs gate required `cvd, poc, vah, val`
   → threw every run → **no file written at all**. **Fix:** hard-require only what
   the chart still supplies (`vwap, ema9`); POC/VAH/VAL recovered from labels are
   soft (warn, don't fail); CVD is sourced independently from Binance aggTrades
   (`scripts/cvd_aggtrades.py`, A-grade tick CVD) — the indicator never needed to
   supply it.

## CDP target-probe pattern (TradingView Desktop / Electron)

Desktop TV exposes several `file:///...index.html` page targets with no
"tradingview"/"chart" in title or URL — title/URL matching fails. **Probe each
page target** for the live chart API and pick the first with a chart widget:

```js
const withTimeout = (p, ms, tag) => Promise.race([
  p, new Promise((_, rej) => setTimeout(() => rej(new Error('probe timeout @'+tag)), ms))]);
for (const t of targets) {
  if (t.type !== 'page') continue;
  let probe = null;
  try {
    probe = await withTimeout(CDP({ port: 9222, target: t.id }), 4000, 'connect');
    await withTimeout(probe.Runtime.enable(), 3000, 'enable');     // ← can hang if another client holds it
    const r = await withTimeout(probe.Runtime.evaluate({
      expression: `(function(){try{return !!(window.TradingViewApi&&window.TradingViewApi._activeChartWidgetWV&&window.TradingViewApi._activeChartWidgetWV.value()&&window.TradingViewApi._activeChartWidgetWV.value()._chartWidget);}catch(e){return false;}})()`,
      returnByValue: true }), 3000, 'eval');
    if (r?.result?.value === true) { target = t; await probe.close(); break; }
  } catch (e) { /* skip */ }
  finally { if (probe && !target) { try { await probe.close(); } catch (e) {} } }
}
```

**Per-probe timeout is mandatory.** A chart target already held by another CDP
client (e.g. the running Hermes MCP server) hangs forever on `Runtime.enable()`.
Without the timeout the bridge hangs indefinitely; with it, the bridge fails fast
(~6s) and reports the contention instead. Symptom of contention: both the bridge
AND `node src/cli/index.js state` fail identically with
`Cannot read properties of undefined (reading '_activeChartWidgetWV')`.

## Consumer shim (auto_card.py)

`auto_card.py`'s `_apply_tv_dmi_override` still keys on a `等级` row. Rather than
rewrite the consumer, the TV-merge block reassembles the bridge's new fields into
the legacy rows the consumer expects:

```python
_dmi_rows = [
  f"等级 | {_tv_raw['tv_grade']}",
  f"处理 | {_tv_raw.get('tv_treatment') or _tv_raw.get('tv_conclusion') or '?'}",
  f"背景 | {_tv_raw.get('tv_direction') or '?'}",
  f"位置 | {_tv_raw.get('tv_entry') or '?'}",
  f"执行 | 进:{...} 损:{...} 标:{...}",
]
engine_data["_tv_pine"] = {"studies": _study_vals,
  "tables": [{"name": "SVP+ICT+VWAP+EMA+CVD", "tables": [{"rows": _dmi_rows}]}]}
```

`_parse_tv_dmi_table` → `_apply_tv_dmi_override` then maps grade → status
(A多→A做多/long/A, A空→A做空/short/A, B多→B等待/long/B, …, X→X禁做/wait).

## Files touched & regression test

- `tools/tradingview-mcp/fetch_tv_data.cjs` — step-6 reader, output fields, gate, target probe (gitignored on disk)
- `scripts/tv_bridge_wrapper.py` — dropped broken `等级/处理` re-read
- `hermes/scripts/auto_card.py` — TV-merge shim
- `tests/test_tv_action_panel_decode.py` — locks the Python decode chain (10 cases: all grades + real-value round-trip + empty guard)

## Diagnostic recipe for "automated card shows null / wrong grade"

1. Read the production indicator's action-panel section — confirm row labels
   (`结论/进场/止损/目标`), NOT `等级/处理`.
2. `grep` the indicator for `display.data_window` — if the export was removed,
   any script reading study-value titles like `CVD Value`/`POC Price` is dead.
3. Check the bridge's table reader uses `dwgtablecells`, not `dwglabels.tables`.
4. Check the quality gate doesn't hard-require fields the indicator no longer exports.
5. Live MCP works but scripts don't → it's a decode-layer break, not a TV/chart problem.
6. Both bridge and MCP CLI `state` fail identically → CDP target contention, not code.
