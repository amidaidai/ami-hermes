# CVD Quality + v9.6 HUD Hardening

Use this when optimizing a mature Pine v5 overlay dashboard after a community audit, especially when the script already has key-level-gated CVD but lacks quality controls.

## Trigger

- User says to "加强 / 继续优化" after an audit.
- Existing dashboard already combines SVP / ICT / VWAP / EMA / CVD.
- CVD is approximate TradingView lower-timeframe delta and should not freely upgrade scores.

## CVD quality guard pattern

Add user-facing inputs under the CVD group:

- `CVD_QUALITY_GUARD` default `true`
- `CVD_MIN_LTF_SAMPLES` default around `3`
- `CVD_SIGNAL_HALFLIFE_BARS` default around `8`

After `request.security_lower_tf()`:

- `cvdLtfSamples = cvdUseLowerTf ? array.size(cvdLowerDeltas) : 1`
- `cvdHasVolume = not na(volume) and volume > 0`
- `cvdSampleOk = not cvdUseLowerTf or cvdLtfSamples >= CVD_MIN_LTF_SAMPLES`
- `cvdQualityOk = not SHOW_CVD_CONFIRM or not CVD_QUALITY_GUARD or (cvdHasVolume and cvdSampleOk)`
- `cvdQualityText = 关 / Q关 / 估算弱 / 样本少 / Q✓`

Gate these with `cvdQualityOk`:

- `cvdBullConfirm`, `cvdBearConfirm`
- `cvdBullDiv`, `cvdBearDiv`
- absorption / distribution qualified signals
- score upgrades and CVD conflict logic via the qualified variables
- sweep-repair / sweep-reject alerts

Add freshness:

- `cvdSignalAge = nz(ta.barssince(cvdBullConfirm or cvdBearConfirm or cvdBullDiv or cvdBearDiv), CVD_SIGNAL_HALFLIFE_BARS + 1)`
- `cvdEventFresh = not CVD_QUALITY_GUARD or cvdSignalAge <= CVD_SIGNAL_HALFLIFE_BARS`
- qualified confirmation/divergence requires `cvdEventFresh`
- stale but otherwise detected signal displays `信号旧`, not an upgrade.

Expose one encoded diagnostic plot, not multiple outputs:

- `CVD Quality (OK*100+LTF samples)`

## v9.6 HUD compacting pattern

Keep one `table.new(position.top_right, 1, 1)` cell. Do not add chart markers or a second table.

Prefer six lines:

1. header: market focus only, no ticker name (`看CVD+扫点`, `看ICT+SVP`, etc.) plus KillZone suffix if active
2. `结论：` state + bias + trend/reversal scores + DMI
3. `结构：` SVP / VWAP / EMA + verdict + sweep count
4. `位置：` nearest resistance/support + MTF arrows
5. `确认：` ICT event + CVD state + quality text + SMT warning if present
6. `资金：` session CVD + lead session + `核对：` HTF/EMA/CVD/location + `执行：` plan/invalidation

For this user, row labels keep Chinese colon `：`, not pipe separators. Remove ticker from the header because TradingView already shows it.

## Alert hardening

When quality guard exists, alerts must use qualified signals only:

- `alertSweepLowRepair = ... (cvdBullDivQualified or cvdAbsorbBuyQualified)`
- `alertSweepHighReject = ... (cvdBearDivQualified or cvdDistributeSellQualified)`

Never let raw weak CVD absorption/distribution trigger a high-signal alert.

## Verification checklist

Run text-level checks before delivery:

- removed day/week display identifiers still have zero residuals when that feature was deleted
- `plotshape=0`, `strategy=0`
- output estimate (`plot + fill + bgcolor + table.new`) stays below 64; aim under 40
- desktop file and upload copy have identical hash/size
- required anchors exist: `CVD_QUALITY_GUARD`, `cvdQualityOk`, `cvdEventFresh`, `CVD Quality (OK*100+LTF samples)`, `string headerLine = focusHint`
- no old `品种：` header or old `actionLine5` remains

Local checks do not replace TradingView Pine Editor compilation.