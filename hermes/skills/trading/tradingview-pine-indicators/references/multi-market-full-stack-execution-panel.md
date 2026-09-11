# Multi-Market Full-Stack Execution Panel Pattern

Use this pattern when refining a TradingView overlay that combines SVP/Volume Profile, VWAP, ICT session liquidity, EMA trend filtering, and CVD/order-flow confirmation for multiple markets.

## User-facing UX preference

- Prefer a single `table.new(position.top_right, 1, 1)` execution panel over chart-attached `label.new()` for live action guidance; labels near candles can obstruct price action.
- Keep the panel compact and actionable. It should answer: current state, which liquidity/structure event matters, which key level to watch, whether CVD agrees, and what to do/where it fails.
- For this user, do not reduce the system to CVD-only. Treat the indicator as a five-factor stack: `SVP + VWAP + ICT + EMA + CVD`.
- Avoid restoring a large table/HUD unless explicitly requested. A one-cell table with 2-3 short lines is preferred.

## Recommended panel shape

```pine
// line 1: market focus + state + ICT event + key level action
// line 2: SVP/VWAP/EMA/CVD compact state
// line 3: execution or no-trade instruction + invalidation
string actionText = actionLine1 + "\n" + actionLine2 + "\n" + actionLine3
var table actionPanel = table.new(position.top_right, 1, 1, border_width=1)
if barstate.islast
    if SHOW_ACTION_PANEL
        table.cell(actionPanel, 0, 0, actionText, text_color=actionTextColor, bgcolor=actionBgColor, text_size=ACTION_PANEL_SIZE, text_halign=text.align_left)
    else
        table.clear(actionPanel, 0, 0, 0, 0)
```

Example output:

```text
主看:ICT/SVP｜A多｜扫低收回｜VWAP 67120承接
SVP上方/VWAP上/EMA多/CVD多
做多｜多失效:破VWAP 66880
```

## Multi-market focus rules

Use one core engine, but change the explanatory priority by market:

- Crypto: `主看:CVD/扫点` — CVD and liquidity sweeps are more useful; keep wider VWAP/ATR thresholds.
- Forex: `主看:VWAP/EMA` — spot/CFD CVD is weaker; downweight CVD and emphasize VWAP, EMA, and session context.
- Metals: `主看:ICT/SVP` — liquidity sweeps, value-area acceptance/rejection, and VWAP reactions matter most.
- Stocks/indices: `主看:SVP/VWAP/EMA` — emphasize volume profile, VWAP, open/session structure, and trend filter.
- Generic/futures: `主看:SVP/VWAP/ICT/EMA/CVD` unless symbol-specific behavior suggests otherwise.

## CVD usage

- CVD is a confirmer, not a standalone signal source.
- Gate CVD confirmation/divergence/absorption to key levels: VAH/VAL/POC/nPOC/VWAP/sweep proximity.
- If a long plan has bearish CVD conflict (`top divergence` or `distribution/sell absorption`), downgrade the panel to `多减弱` and show `不追｜等CVD修复`.
- If a short plan has bullish CVD conflict (`bottom divergence` or `absorption buy`), downgrade to `空减弱` and show `不追｜等CVD修复`.
- If the user also uses TradingView's official CVD v6 pane (`ta.requestVolumeDelta()`), explain that the overlay's v5 lower-timeframe approximation should match directionally but not numerically.

## ICT usage

- ICT must appear in the execution panel when this full-stack indicator is used. Include compact event text such as `扫低收回`, `扫高拒绝`, `扫低`, `扫高`, or `无新扫`.
- Current session high/low sweeps are useful, but the next high-value enhancement is prior-day/prior-week liquidity pools: PDH/PDL/PWH/PWL. These are broadly supported across ICT, futures, crypto, and forex communities.
- Consider a minimal FVG feature only if it stays sparse: most recent 1-2 valid imbalances, used as context rather than a signal trigger. Avoid drawing many boxes.

## Pine pitfalls learned

- Do not create multiline string literals by inserting real line breaks inside quotes. Use escaped `"\n"` in concatenation.
- Long nested ternaries with Chinese strings are fragile. Prefer intermediate strings and `if/else` assignments for execution-panel logic.
- After replacing labels with a table, remove stale inputs such as `SHOW_ACTION_LABEL`, `ACTION_LABEL_OFFSET`, and `ACTION_LABEL_SIZE`.
- Verify text-level invariants after editing: one `table.new(position.top_right, 1, 1)`, one `table.cell`, expected alertcondition count, no stale action-label refs.

## Community synthesis

Across X, Reddit OrderFlow/Daytrading, TradingView public scripts, GitHub Pine/volume-profile repos, and Bookmap education, the durable consensus is:

- Volume Profile/SVP provides auction structure: POC, VAH, VAL, HVN/LVN/nPOC.
- VWAP provides fair-value bias and pullback/reversion reference.
- ICT liquidity sweeps identify where stops/liquidity were taken.
- EMA/DMI are filters, not primary structure.
- CVD/delta confirms absorption, exhaustion, or divergence at key levels.
- The best live panel should translate confluence into an execution phrase, not list every raw indicator.