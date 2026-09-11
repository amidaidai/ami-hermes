# Trade Controls + CVD Alignment Pattern

Use this when iterating the user's SVP/ICT/VWAP/EMA/CVD overlay and they ask whether the right-top action panel is truly controlled by trade parameters, or whether a separate CVD pane matches the main indicator.

## Trigger

- User asks if the right-top action panel has real trade-control parameters.
- User asks to audit whether inputs are actual controls or dead settings.
- User provides a separate CVD pane and asks if it matches the main indicator.
- User wants community-style optimization for accuracy and market adaptation.

## Right-Top Action Panel Controls

The action panel should not only be a display toggle and font-size control. Add real controls that can change the panel conclusion and/or grade:

- `ALLOW_LONG_TRADES`: blocks long A/B/C plans when false.
- `ALLOW_SHORT_TRADES`: blocks short A/B/C plans when false.
- `MIN_TRADE_RR`: if planned reward/risk is below threshold, downgrade to `不做`.
- `MAX_STOP_ATR`: if invalidation distance exceeds ATR threshold, downgrade to `不做`.
- `SHOW_TRADE_CONTROL_LINE`: toggles an explicit control line in the panel.

Recommended panel language:

- `结论｜...`
- `结构｜SVP...；VWAP...；EMA...`
- `确认｜ICT...；CVD...`
- `交易控制：通过/RR不足/止损过宽｜RR x.xx｜止损 x.xxATR`
- `执行｜做多/做空/不追/不做...`

## Implementation Notes

1. Apply long/short enable switches before setup grade booleans:
   - `setupLongA/B/C = ALLOW_LONG_TRADES and ...`
   - `setupShortA/B/C = ALLOW_SHORT_TRADES and ...`
2. Compute plan/invalidation distances after `activeLongPlan/activeShortPlan` and invalidation prices exist:
   - `replayStopDistance = abs(close - replayInvalidPrice)`
   - `replayPlanDistance = abs(close - replayPlanPrice)`
   - `replayRRUnit = replayPlanDistance / replayStopDistance`
   - `replayStopAtr = replayStopDistance / currATR`
3. Derive guards:
   - `tradeRrBlocked = MIN_TRADE_RR > 0 and replayRRUnit < MIN_TRADE_RR`
   - `tradeStopBlocked = replayStopAtr > MAX_STOP_ATR`
   - `tradeControlBlocked = tradeRrBlocked or tradeStopBlocked`
4. Insert `tradeControlBlocked` after `setupX` and before CVD conflict/actionable plans in the panel priority chain.
5. Include trade-control state in `actionBgColor` so invalid trade plans visibly turn red.
6. Export `Replay Stop ATR` and `Trade Control Blocked` to Data Window for replay/audit.

## CVD Pane Alignment

Official TradingView CVD panes often use Pine v6:

```pine
import TradingView/ta/8
[openVolume, maxVolume, minVolume, lastVolume] = ta.requestVolumeDelta(lowerTimeframe, anchorInput)
plotcandle(openVolume, maxVolume, minVolume, lastVolume, "CVD")
```

The user's overlay is Pine v5, so it cannot directly import the v6 library or use the same helper. The overlay should keep its v5-compatible lower-timeframe approximate delta and expose CVD via Data Window / panel text.

Explain clearly:

- The side pane is true/official CVD visualization.
- The overlay CVD is execution CVD: directionally aligned, but not numerically identical.
- Use the official side pane for visual confirmation.
- Use the overlay CVD for decisions because it is gated by SVP/VWAP/ICT key levels, absorption/distribution, divergence, and trade controls.

## Community Optimization Summary

Community patterns around CVD + VWAP + Volume Profile + ICT converge on:

- Do not trade CVD alone; use it only at key levels.
- Require liquidity sweep/reclaim, VWAP/VA acceptance, or POC/VAH/VAL proximity for high-grade signals.
- Add explicit risk controls (RR and ATR stop distance) to execution panels.
- Keep official CVD in a lower pane when available, but avoid plotting oscillator values on an overlay price chart.
- Prefer execution wording over abbreviations: state why, what to wait for, and where invalidation sits.

## Verification Checklist

- New trade-control inputs have reference count > 1.
- `unused_input_count` is zero after changes.
- Exactly one `table.new()` and one `table.cell()` remain for the right-top action cell.
- Five alertconditions remain unless the user asks to change alert scope.
- No FVG/OB subsystem is reintroduced unless explicitly requested.
- No long Pine lines (>320 chars) remain.
