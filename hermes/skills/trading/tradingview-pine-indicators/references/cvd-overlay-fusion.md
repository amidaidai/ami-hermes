# CVD Overlay Fusion Pattern

Session pattern: the user provided two TradingView indicators: a Pine v6 CVD pane using `TradingView/ta/8` and a Pine v5 overlay dashboard combining SVP, ICT session levels, VWAP, EMA clouds, and DMI table logic. The useful durable technique was not the exact file, but the compatibility-safe fusion approach.

## Problem

- Source CVD script was `//@version=6` and used `ta.requestVolumeDelta()` from `TradingView/ta/8`.
- Target overlay dashboard was `//@version=5` and already heavy: arrays, polylines, labels, tables, lower-timeframe SVP.
- Directly importing/plotting CVD into overlay could cause version incompatibility and price-scale compression.

## Approach

1. Keep the target overlay at Pine v5.
2. Add a dedicated CVD input group:
   - enable/disable CVD confirmation
   - auto/manual anchor timeframe
   - auto/manual lower timeframe
   - slope length
   - divergence lookback
   - scoring weight
3. Reimplement approximate CVD with a local delta function:

```pine
f_cvd_delta() =>
    float upVol = close > open ? volume : close < open ? 0.0 : volume * 0.5
    float dnVol = close < open ? volume : close > open ? 0.0 : volume * 0.5
    upVol - dnVol
```

4. Use `request.security_lower_tf()` only when the selected CVD lower timeframe is below the chart timeframe.
5. Reset cumulative CVD on the selected anchor timeframe:

```pine
bool cvdReset = ta.change(time(cvdAnchorTf)) != 0
var float cvdValue = 0.0
cvdValue := cvdReset ? cvdBarDelta : nz(cvdValue[1]) + cvdBarDelta
```

6. Derive compact states for the dashboard table:
   - `顺多确认`
   - `顺空确认`
   - `买盘回升`
   - `卖盘回落`
   - `顶背离`
   - `底背离`
   - `中性`
7. Integrate CVD into existing logic:
   - Add a `CVD` row to the status table.
   - Add CVD confirmation/divergence to score adjustments.
   - Add CVD divergence to conflict logic.
   - Add `cvdLongOk` / `cvdShortOk` gates to validated structure states.
8. Expose `cvdValue` and `cvdSlope` via `display.data_window` only.

## Verification

- Confirm indicator title changed.
- Confirm CVD group and inputs exist.
- Confirm `request.security_lower_tf()` call exists for CVD.
- Confirm table row references `cvdStateText`.
- Confirm validation logic includes CVD gates.
- Confirm scores are clamped after negative adjustments.
- Confirm output file exists and starts with the intended Pine version.
- Tell the user TradingView Pine Editor remains the final syntax validator.

## Pitfall

If adding negative score adjustments, avoid leaving scores below zero before display. Clamp each score with:

```pine
score := math.min(math.max(score, 0), 10)
```
