# Pro Dashboard Upgrade Pattern

Session pattern: after merging CVD into an SVP/ICT/VWAP/EMA overlay dashboard, the user wanted to keep all existing features but make the dashboard more actionable and ensure nPOC price-axis labels only show untouched levels.

## Upgrade Goals

- Preserve the existing indicator framework rather than replacing it.
- Add execution-oriented summaries: setup grade and operation posture.
- Add alerts for high-signal states only.
- Add CVD absorption/distribution, not just slope and divergence.
- Add performance/visual controls so the dashboard stays usable on lower timeframes.
- Add right-price-axis `nPOC Price` that disappears after touch.

## Setup Grade Pattern

Derive grade variables from existing trend/reversal scores plus CVD and overextension checks:

```pine
bool setupLongA = trendLongScore >= 8 and trendLongScore >= trendShortScore + 2 and cvdBullConfirm and priceAboveS and not dmiHot
bool setupShortA = trendShortScore >= 8 and trendShortScore >= trendLongScore + 2 and cvdBearConfirm and priceBelowS and not dmiHot
bool setupLongB = trendLongScore >= 6 and trendLongScore >= trendShortScore + 2 and cvdLongOk and not setupLongA
bool setupShortB = trendShortScore >= 6 and trendShortScore >= trendLongScore + 2 and cvdShortOk and not setupShortA
bool setupLongC = reversalLongScore >= 6 and reversalLongScore >= reversalShortScore + 2
bool setupShortC = reversalShortScore >= 6 and reversalShortScore >= reversalLongScore + 2
bool setupX = dmiHot or vwapExtendedUp or vwapExtendedDn or structureConflict

string setupGradeText = setupX ? "X" : setupLongA ? "A多" : setupShortA ? "A空" : setupLongB ? "B多" : setupShortB ? "B空" : setupLongC ? "C反多" : setupShortC ? "C反空" : "C等待"
string actionText = setupX ? "禁追/观望" : setupLongA or setupLongB ? "可等多头触发" : setupShortA or setupShortB ? "可等空头触发" : setupLongC ? "反多等确认" : setupShortC ? "反空等确认" : "等确认"
```

Add table rows for `等级` and `操作` near the existing `倾向`/`计划` rows.

## Alert Pattern

Keep alerts selective:

```pine
alertcondition(ENABLE_PRO_ALERTS and setupLongA, title="Pro A级偏多", message="{{ticker}} {{interval}} A级偏多：等待多头触发/回踩确认")
alertcondition(ENABLE_PRO_ALERTS and setupShortA, title="Pro A级偏空", message="{{ticker}} {{interval}} A级偏空：等待空头触发/反抽确认")
alertcondition(ENABLE_PRO_ALERTS and (sweptLowReclaimed and (cvdBullDiv or cvdAbsorbBuy)), title="Pro 下扫修复", message="{{ticker}} {{interval}} 下扫修复：CVD底背离/下方吸收")
alertcondition(ENABLE_PRO_ALERTS and (sweptHighRejected and (cvdBearDiv or cvdDistributeSell)), title="Pro 上扫拒绝", message="{{ticker}} {{interval}} 上扫拒绝：CVD顶背离/上方派发")
alertcondition(ENABLE_PRO_ALERTS and setupX, title="Pro 禁追/冲突", message="{{ticker}} {{interval}} 禁追或结构冲突：等待重新确认")
```

## CVD Absorption / Distribution Pattern

Use CVD movement versus price compression over a lookback window:

```pine
float cvdAbsPriceRange = ta.highest(high, CVD_ABSORB_LEN) - ta.lowest(low, CVD_ABSORB_LEN)
float cvdAbsMove = cvdValue - nz(cvdValue[CVD_ABSORB_LEN])
float cvdAbsAvgDelta = ta.sma(math.abs(cvdBarDelta), CVD_ABSORB_LEN)
bool cvdAbsorbBuy = SHOW_CVD_CONFIRM and cvdAbsPriceRange <= currATR * CVD_ABSORB_PRICE_ATR and cvdAbsMove < -cvdAbsAvgDelta * CVD_ABSORB_DELTA_MULT and close >= ta.lowest(low, CVD_ABSORB_LEN) + cvdAbsPriceRange * 0.45
bool cvdDistributeSell = SHOW_CVD_CONFIRM and cvdAbsPriceRange <= currATR * CVD_ABSORB_PRICE_ATR and cvdAbsMove > cvdAbsAvgDelta * CVD_ABSORB_DELTA_MULT and close <= ta.lowest(low, CVD_ABSORB_LEN) + cvdAbsPriceRange * 0.55
cvdStateText := cvdDistributeSell ? "上方派发" : cvdAbsorbBuy ? "下方吸收" : cvdStateText
```

Then include absorption/distribution in reversal scoring and sweep alerts.

## Active-Only nPOC Price Axis

The key rule: the price-axis plot must source from the latest `NakedPOC` where `active == true`; touched nPOCs must not remain on the price scale.

```pine
if np.active
    bool touched = bar_index > np.startBar and (high >= np.price and low <= np.price)
    if touched
        np.active := false
        line.set_x2(np.ln, bar_index)
        line.set_color(np.ln, color.new(NPOC_COLOR, 100))
    else
        line.set_x2(np.ln, bar_index)
```

Then:

```pine
float show_npoc_val = na
if array.size(npocList) > 0
    int i = array.size(npocList) - 1
    while i >= 0
        NakedPOC n = array.get(npocList, i)
        if n.active
            show_npoc_val := n.price
            break
        i -= 1

float axisNpoc = SHOW_AXIS_VP_LEVELS and SHOW_NPOC ? show_npoc_val : na
float axisNpocPlot = (SHOW_RIGHT_PRICE_AXIS and SHOW_AXIS_VP_LEVELS and SHOW_NPOC) ? axisNpoc : na
plot(axisNpocPlot, title="nPOC Price", color=NPOC_COLOR, show_last=1, display=display.price_scale)
```

## Verification Checklist

- Confirm a new Pro file is saved instead of overwriting the previous enhanced version.
- Confirm Pine version remains compatible with the base script.
- Confirm table row count matches added rows.
- Confirm nPOC price-axis plot exists and reads only active nPOCs.
- Confirm touched nPOCs set `active := false`.
- Confirm alerts are guarded by an enable input.
- Remind the user that final syntax validation must happen in TradingView Pine Editor.
