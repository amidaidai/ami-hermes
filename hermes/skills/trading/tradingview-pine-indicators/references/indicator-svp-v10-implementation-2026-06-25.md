# SVP v10 Implementation Notes (2026-06-25)

Session context: user uploaded `指标svp.txt`, asked for a comprehensive web-audit, then directed follow-up fixes:
- Confirmed TradingView white theme (so `#0F0F0F` POC/day-pool lines remain visible and were not changed).
- Reported previous-day/previous-week high/low pools were not displaying.
- Asked to keep full `亚高/亚低/伦高/伦低/纽高/纽低` labels; do not abbreviate `高/低` to `H/L`.
- Requested full optimization based on the audit.

This reference captures the exact code changes applied so future iterations can copy/paste/adapt them.

---

## 1. Day/Week Liquidity Pool Independence

### Problem
`showDayPool` / `showWeekPool` were gated by `allowDrawIct`, which depends on `show_ict_lines` (`tf < 4H`). On 4H+ timeframes the day/week pools were never created even when the user enabled them.

### Fix
Remove the `allowDrawIct` gate from pool creation, and make the `levels[]` maintenance loop run whenever `SHOW_ICT_LEVELS` is on (so pools are swept/extended even when ICT session lines are not drawn).

Before:
```pine
bool showDayPool = allowDrawIct and SHOW_DAY_LIQUIDITY and not na(prevDayHigh) and not na(prevDayLow)
bool showWeekPool = allowDrawIct and SHOW_WEEK_LIQUIDITY and not na(prevWeekHigh) and not na(prevWeekLow)
```

After:
```pine
bool showDayPool = SHOW_DAY_LIQUIDITY and not na(prevDayHigh) and not na(prevDayLow)
bool showWeekPool = SHOW_WEEK_LIQUIDITY and not na(prevWeekHigh) and not na(prevWeekLow)
```

Change the levels-maintenance block:
```pine
// before
if SHOW_ICT_LEVELS and show_ict_lines
    ...

// after
if SHOW_ICT_LEVELS
    ...
```

Change the global cleanup block:
```pine
// before
if barstate.islast and (not SHOW_ICT_LEVELS or not show_ict_lines)

// after
if barstate.islast and not SHOW_ICT_LEVELS
```

Keep `mergedLabels` block guarded by `SHOW_ICT_LEVELS and show_ict_lines` because label merging is only needed for ICT session lines.

---

## 2. H1 Label Abbreviation Gate

### Problem
`updateLabel()` replaced ` 高` with `H` and ` 低` with `L` on H1 charts, but this also corrupted SVP labels like `周三 高` → `周三H`.

### Fix
Remove the `高/低 → H/L` replacement. Keep only the session-name abbreviation (`亚洲盘 → 亚`, `伦敦盘 → 伦`, `纽约盘 → 纽`).

```pine
if isH1
    if str.contains(name, "亚洲盘")
        dispName := str.replace(name, "亚洲盘", "亚")
    else if str.contains(name, "伦敦盘")
        dispName := str.replace(name, "伦敦盘", "伦")
    else if str.contains(name, "纽约盘")
        dispName := str.replace(name, "纽约盘", "纽")
```

---

## 3. Compact 6-Line Action Panel (v10)

### Structure
```
header:     看CVD+扫点 ⚡伦敦开盘
结论：     A多 回踩 · 偏多 · 15m↑ 1h↑ 4h→ 1D↑ · 顺多 · 偏强修复
结构：     VAH上 · VWAP延 · EMA多
确认：     周四亚高收回 · 日买盘 亚+15K 伦-3.2K 纽~0
核对：     HTF✓ EMA✓ CVD✓ 位✓
执行：     等VAL 67200承接 · 多失效:破VAL 67000
```

### Key code snippets

Remove ticker from header:
```pine
// before
string headerLine = "品种：" + syminfo.ticker + " · " + focusHint + actionKillZoneLine
// after
string headerLine = focusHint + actionKillZoneLine
```

Strip module prefixes from value builders:
```pine
string actionIctText = sweptLowReclaimed ? lastEventName + "收回" :
     sweptHighRejected ? lastEventName + "拒绝" :
     sweptLowNow ? "扫" + ictEventName :
     sweptHighNow ? "扫" + ictEventName :
     lastEventName != "无新事件" ? lastEventName : "—"

string actionCvdText = cvdAnchorLabel + cvdStateText + cvdSessionSuffix
if cvdAbsorbBuyQualified
    actionCvdText := cvdAnchorLabel + "吸收" + cvdSessionSuffix
else if cvdDistributeSellQualified
    actionCvdText := cvdAnchorLabel + "派发" + cvdSessionSuffix
...
```

Add MTF bias function:
```pine
f_mtf_bias_str() =>
    string tfs[] = array.from("15", "60", "240", "D")
    string labels[] = array.from("15m", "1h", "4h", "1D")
    string out = ""
    for i = 0 to array.size(tfs) - 1
        string tf = array.get(tfs, i)
        [c, e21, e55, v] = request.security(syminfo.tickerid, tf, f_htf_pack(), ignore_invalid_symbol=true)
        bool bull = not na(c) and c >= v and e21 >= e55
        bool bear = not na(c) and c < v and e21 < e55
        string arrow = bull ? "↑" : bear ? "↓" : not na(c) ? "→" : "—"
        out := out + (i > 0 ? " " : "") + array.get(labels, i) + arrow
    out
```

Build sentiment line (defined after `activeLongPlan` / `activeShortPlan` to avoid single-pass error):
```pine
string mtfBiasText = USE_HTF_FILTER ? f_mtf_bias_str() : ""
string actionBiasWord = activeLongPlan ? "偏多" : activeShortPlan ? "偏空" : "观望"
string actionStructureVerdict_tone = stateText
string actionSentimentText = actionBiasWord + " · " + (USE_HTF_FILTER ? mtfBiasText + " · " : "") + dmiVerifyText + " · " + actionStructureVerdict_tone
```

Assemble 6 lines:
```pine
string actionLine1 = "结论：" + actionStateText + " · " + actionSentimentText
string actionLine2 = "结构：" + actionValueText + " · VWAP" + actionVwapText + " · EMA" + actionEmaText
string actionLine3 = "确认：" + actionIctText + " · " + actionCvdText + (SHOW_SESSION_CVD and cvdSessionSummary != "" ? " · " + cvdSessionSummary + cvdDirectionHint : "")
string actionLine4 = "核对：" + ""
if activeLongPlan or activeShortPlan
    string ckHtf = htfAllowLong and htfAllowShort ? "HTF✓" : "HTF✗"
    string ckEma = (activeLongPlan and emaBull) or (activeShortPlan and emaBear) ? "EMA✓" : "EMA✗"
    string ckCvd = (activeLongPlan and cvdBullConfirmQualified) or (activeShortPlan and cvdBearConfirmQualified) ? "CVD✓" : "CVD✗"
    string ckLoc = nearAKeyLevel ? "位✓" : nearCvdKeyLevel ? "位~" : "位✗"
    string ckSmt = smtBullDiv or smtBearDiv ? "SMT⚠" : ""
    actionLine4 := "核对：" + ckHtf + " " + ckEma + " " + ckCvd + " " + ckLoc + (ckSmt != "" ? " " + ckSmt : "")
string actionLine5 = "执行：" + lineAction

string actionText = headerLine + "\n" + actionLine1 + "\n" + actionLine2 + "\n" + actionLine3 + (actionLine4 != "核对：" ? "\n" + actionLine4 : "") + "\n" + actionLine5
```

Use `+/-/~` for CVD dominant session hint:
```pine
string cvdDirectionHint = SHOW_SESSION_CVD and cvdLeadSession != "" ? " " + cvdLeadSession + (cvdLeadSlope > 0 ? "+" : cvdLeadSlope < 0 ? "-" : "~") : ""
```

---

## 4. CVD Enhancements

### 4.1 1.5×ATR divergence swing filter
```pine
float cvdDivSwingMag = ta.highest(high, CVD_DIVERGENCE_LEN) - ta.lowest(low, CVD_DIVERGENCE_LEN)
bool cvdBearDivRaw = SHOW_CVD_CONFIRM and high >= ta.highest(high, CVD_DIVERGENCE_LEN)[1] and cvdValue < ta.highest(cvdValue, CVD_DIVERGENCE_LEN)[1]
bool cvdBullDivRaw = SHOW_CVD_CONFIRM and low <= ta.lowest(low, CVD_DIVERGENCE_LEN)[1] and cvdValue > ta.lowest(cvdValue, CVD_DIVERGENCE_LEN)[1]
bool cvdDivSwingOk = cvdDivSwingMag > 1.5 * currATR
bool cvdBearDiv = cvdBearDivRaw and cvdDivSwingOk
bool cvdBullDiv = cvdBullDivRaw and cvdDivSwingOk
```

### 4.2 Quality gate
```pine
int cvdLtfSamples = cvdUseLowerTf ? array.size(cvdLowerDeltas) : 1
bool cvdHasVolume = not na(volume) and volume > 0
bool cvdSampleOk = cvdLtfSamples >= 3
bool cvdQualityOk = cvdHasVolume and cvdSampleOk
```

Then gate all qualified signals:
```pine
bool cvdAbsorbBuyQualified = cvdQualityOk and cvdAbsorbBuy and (not REQUIRE_KEY_LEVEL_FOR_CVD_CONFIRM or nearCvdKeyLevel)
bool cvdDistributeSellQualified = cvdQualityOk and cvdDistributeSell and (not REQUIRE_KEY_LEVEL_FOR_CVD_CONFIRM or nearCvdKeyLevel)
bool cvdBullConfirmQualified = cvdQualityOk and cvdBullConfirm and (not REQUIRE_KEY_LEVEL_FOR_CVD_CONFIRM or nearCvdKeyLevel or acceptanceBullOk)
bool cvdBearConfirmQualified = cvdQualityOk and cvdBearConfirm and (not REQUIRE_KEY_LEVEL_FOR_CVD_CONFIRM or nearCvdKeyLevel or acceptanceBearOk)
bool cvdBearDivQualified = cvdQualityOk and cvdBearDiv and (not FILTER_CVD_DIVERGENCE_BY_KEY_LEVEL or nearCvdKeyLevel)
bool cvdBullDivQualified = cvdQualityOk and cvdBullDiv and (not FILTER_CVD_DIVERGENCE_BY_KEY_LEVEL or nearCvdKeyLevel)
```

### 4.3 Asia channel market adaptation
```pine
bool cvdUseAsiaChannel = not MARKET_ADAPTIVE_ENGINE or marketCrypto
float cvdAsiaBar = cvdUseAsiaChannel and isAsia ? cvdBarDelta : 0.0
```

And adapt the summary:
```pine
string cvdAsiaText = not SHOW_SESSION_CVD or not cvdUseAsiaChannel ? "" : "亚" + f_fmt_cvd(cvdAsiaAcc)
string cvdSessionSummary = SHOW_SESSION_CVD ? (cvdUseAsiaChannel ? cvdAsiaText + " " : "") + cvdLondonText + " " + cvdNYText : ""
```

---

## 5. Multi-Market Parameter Layer

### 5.1 VP_MIN_TICK_MULT
```pine
float finalVpMinTickMult = MARKET_ADAPTIVE_ENGINE ?
    (marketCrypto ? VP_MIN_TICK_MULT :
     marketStock ? math.max(VP_MIN_TICK_MULT, 30) :
     marketForex ? math.max(VP_MIN_TICK_MULT, 40) :
     marketMetal or marketFutures or marketIndex ? math.max(VP_MIN_TICK_MULT, 50) :
     VP_MIN_TICK_MULT) : VP_MIN_TICK_MULT
```

Use it inside `processAndRender`:
```pine
float minStep = syminfo.mintick * finalVpMinTickMult
```

### 5.2 SMT cross-exchange helpers
```pine
string stdTickerUpper = str.upper(stdTicker)

f_is_btc_pair(string t) =>
    str.contains(t, "BTCUSDT") or str.contains(t, "BTC/USDT") or
    str.contains(t, "BTCUSD") or str.contains(t, "XBTUSDT") or str.contains(t, "XBTUSD")

f_is_xau_pair(string t) =>
    str.contains(t, "XAUUSD") or str.contains(t, "XAU/USD") or str.contains(t, "GOLD")
```

Use in SMT branches:
```pine
if SMT_PAIR_MODE == "BTC/ETH"
    smtTicker := f_is_btc_pair(stdTickerUpper) ? "BINANCE:ETHUSDT" : stdTicker
else if SMT_PAIR_MODE == "XAU/DXY"
    smtTicker := f_is_xau_pair(stdTickerUpper) ? "TVC:DXY" : stdTicker
...
else
    if marketCrypto and f_is_btc_pair(stdTickerUpper)
        smtTicker := "BINANCE:ETHUSDT"
    else if marketMetal and f_is_xau_pair(stdTickerUpper)
        smtTicker := "TVC:DXY"
```

---

## 6. Default Setting Change

`SHOW_DO_LINE` default changed from `false` to `true`:
```pine
bool SHOW_DO_LINE = input.bool(true, "显示日线开盘价线条 (DO)", group=DO_GROUP)
```

---

## 7. Dead Code Removed

Removed independent definitions that were no longer consumed by the v9.5+ action panel:
- `trendMiniText`
- `volumeMiniText`
- `eventMiniText`
- `cvdMiniText`
- `structureShortText`
- `planShortText`
- `focusedPlanText`

Note: `stateText`, `watchText`, `invalidText`, `nowAdviceText`, `directionGuideText`, `actionGuideText`, `detailText`, `cardLine1-3` still exist in this version because they feed `stateText` → `actionStructureVerdict_tone` and `invalidText`/`watchText` → `lineAction`. A deeper dead-code pass can remove the latter group if the user no longer needs them.

---

## 8. Verification Commands

```bash
# Output series count
grep -cE "^\s*.*\bplot\b|^\s*.*\bfill\b|^\s*.*\bbgcolor\b|^\s*table\.new" svp_v10.txt

# Zero residuals after feature removal
grep -c "removedIdentifier" svp_v10.txt

# Python sanity check
python -c "import re; t=open('svp_v10.txt').read(); print(t.count('(')-t.count(')'), t.count('{')-t.count('}'))"
```

This version produced **35 output series** (31 plots + 2 fills + 1 bgcolor + 1 table), safely under TV's 64 limit and near the community 40 target.
