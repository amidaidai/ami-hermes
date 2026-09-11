# CVD + SVP/ICT/VWAP/EMA Framework Example

This reference captures a useful pattern from a TradingView indicator review session.

## Pairing Pattern

A robust discretionary intraday framework can pair:

- Lower pane CVD: order-flow/volume-delta confirmation.
- Main chart SVP: POC, VAH, VAL, nPOC, value acceptance/rejection.
- VWAP: daily/weekly/monthly fair-value anchor plus standard-deviation bands.
- ICT session levels: Asia/London/New York highs/lows, sweeps, reclaims, rejections.
- EMA cloud: trend filter, usually fast 9/21 and slower 34/55.
- DMI/ADX table: trend-path confirmation, exhaustion/overheat, conflict state.

## Practical Interpretation

Use the main chart to define location and structure, then use CVD as confirmation:

| Structure | CVD Read | Interpretation |
|---|---|---|
| Break above VAH/VWAP | CVD makes new high | Better bullish acceptance |
| Break above VAH/VWAP | CVD flat/diverges | False breakout risk |
| Sweep low then reclaim | CVD stops making new lows | Possible absorption/repair |
| Break below VAL/VWAP | CVD makes new low | Better bearish acceptance |
| Selloff below value | CVD diverges | Seller exhaustion risk |

## Review Notes

- `ta.requestVolumeDelta()` and `request.security_lower_tf()` improve detail but create precision/performance tradeoffs.
- Object-heavy Pine scripts with many arrays, polylines, labels, lines, and tables can lag or hit TradingView object limits.
- Auto-degrade logic for volume profile precision is valuable and should be called out positively.
- A decision table with states such as trend continuation, value acceptance, sweep rejection, and conflict is useful, but scores should be described as confluence scores, not win probability.

## Suggested User Guidance

Recommend a five-step reading process:

1. Environment: VWAP side, VA side, EMA cloud.
2. Location: POC/VWAP balance, VAH/VAL edge, nPOC, session high/low.
3. Event: sweep, reclaim, rejection, acceptance, VWAP reclaim/loss.
4. Confirmation: CVD, DMI/ADX, relative volume, close location.
5. Execution: wait for retest/pullback/rejection and define invalidation.

## Default Performance Suggestions

For complex all-in-one Pine dashboards:

- Keep volume profile rows around 50-80 unless the chart remains responsive.
- Keep completed profile retention low, often 1.
- On 1m charts, reduce historical rendering and object-heavy labels.
- If lag appears, disable completed profiles, dense ICT labels, and extra weekly/monthly polyline rendering first.
