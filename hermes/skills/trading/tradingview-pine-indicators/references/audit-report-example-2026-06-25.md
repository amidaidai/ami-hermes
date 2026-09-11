# Audit Report Example: SVP+ICT+VWAP+EMA+CVD v8.1+ (2026-06-25)

Real-world example of a multi-community cross-audit of a mature Pine v5 overlay dashboard. Use this as a reference for output shape, issue severity, and community citations when auditing similar indicators.

## Audited File

- **Path**: `C:/Users/Administrator/.hermes-web-ui/upload/default/f94e16c6edfd7dfe.txt`
- **Lines**: 2392
- **Version tag**: v8.1 market-adaptive engine with action-panel HUD
- **Markets covered**: crypto, forex, metals, stocks, futures, indices, options, CFDs

## Search Matrix Used

| Platform | Query | Finding |
|----------|-------|---------|
| TradingView | `site:tradingview.com multi-asset dashboard best practice 2025` | LuxAlgo/AGPro 6-field single-cell standard |
| Reddit | `r/pinescript CVD divergence swing magnitude filter 1.5 ATR` | NikaQuant 3-condition gate consensus |
| Reddit / ICT | `ICT KillZone London New York forex gold crypto Asia session CVD` | Forex/metals Asia CVD is noise; KillZone ≠ Silver Bullet |
| GitHub/docs | `Pine Script request.security tuple bundle output series limit 64` | 40-call limit, composite-float encoding |
| Medium | `Pine Script multi-asset compatibility adaptive thresholds` | Betashorts `syminfo.mintick` + ATR normalization |
| TradingView docs | `Pine Script v6 vs v5 upgrade` | v5 still valid; no forced migration |

## 8-Dimension Rubric Applied

| # | Dimension | Rating | Reason |
|---|-----------|--------|--------|
| 1 | Core Structure | ⚠️ | VWAP anchor market-specialized; POC/day-pool color invisible on dark theme |
| 2 | Session/ICT | ⚠️ | `SHOW_OPEN_ONLY_ACTIVE` fix incomplete; H1 abbreviation corrupts SVP labels |
| 3 | CVD/Order Flow | ⚠️ | Missing 1.5×ATR swing filter; no quality gate; Asia CVD always on |
| 4 | Multi-Market | ⚠️ | `VP_MIN_TICK_MULT` fixed; SMT hardcoded exchange; VWAP anchor over-marketized |
| 5 | DMI/Decision | ✅ | A/B/C/X grading + market-adaptive thresholds stable |
| 6 | Action Panel | ⚠️ | 7 lines > 6; ticker prefix; ICT/CVD prefix duplication; no MTF bias row |
| 7 | Performance | ✅ | 35 outputs (<64, ~40 target), 9 request.* calls (<40) |
| 8 | Settings Hygiene | ⚠️ | `SHOW_DO_LINE=false`; ~150 lines dead code; groups dense |

## P0 Issues Found

1. **Action-panel prefix duplication**: `actionIctText` and `actionCvdText` already include `"ICT "`/`"CVD "`, which duplicate the row-template prefixes.
2. **Ticker in header**: `headerLine = "品种：" + syminfo.ticker + ...` wastes a line; chart already shows ticker.
3. **CVD divergence lacks swing-magnitude gate**: raw `cvdBearDiv`/`cvdBullDiv` only check new extreme + non-confirm.
4. **H1 abbreviation gate missing**: `updateLabel()` shrinks `高/低` to `H/L` for SVP labels too.
5. **`SHOW_OPEN_ONLY_ACTIVE` incomplete**: session-end levels not protected by `isSessionEnd` + 3-bar grace window.
6. **`#0F0F0F` POC/day-pool colors**: invisible on dark TV theme; confirm theme before changing.

## P1 Issues Found

1. Action panel should be 6 lines (merge 资金 into 确认, merge 定调 into 结论, drop ticker).
2. Asia CVD should auto-disable for forex/metals.
3. Add CVD quality gate (`cvdLtfSamples`, `cvdQualityOk`, `cvdEventFresh`).
4. `VP_MIN_TICK_MULT` market-adaptive floors (crypto 20, stock 30, forex 40, metal 50).
5. SMT cross-exchange matching (`f_is_btc_pair()`/`f_is_xau_pair()`).
6. `SHOW_DO_LINE` default should be `true`.
7. Dead-code cleanup (~150 lines of narrative/mini-text variables).

## P2 Issues Found

1. Add MTF bias arrows (`15m/1h/4h/1D`) to 结论 row.
2. Add day/week pool proximity hints to 结构 row.
3. Optional SVP extreme sweep lines (v9.3 pattern).
4. DMI standard/aggressive toggle (Wilder 14 vs 10).
5. Further compress Data Window diagnostics into fewer encoded plots.

## Community Citations

- **AGPro/LuxAlgo**: 6-field single-cell dashboard; no ticker; color-by-state; `：` labels.
- **NikaQuant Quantum Liquidity Map**: CVD divergence requires swing > 1.5×ATR.
- **ICT / r/InnerCircleTraders**: KillZone = London/NY Open; forex/metals Asia session low volume.
- **Betashorts**: `syminfo.mintick` + ATR normalization for multi-asset thresholds.
- **TradingView docs**: 64 output-series limit; `request.security` tuple bundling.

## Lesson: When "Community Advice" Does Not Apply

The simple rule "forex/metals must use daily VWAP" did **not** apply here because the indicator already has `SMART_HIDE_VWAP` + manual override + multi-TF confidence. The existing guard rails made the simpler rule over-optimization. This is a recurring pattern: community suggestions are inputs, not mandates; dashboard maturity gates whether they apply.
