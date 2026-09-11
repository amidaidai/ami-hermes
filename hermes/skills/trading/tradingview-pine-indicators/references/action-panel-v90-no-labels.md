# v9.0 No-Label Action Panel Pattern (2026-06-24)

## Evolution

v8.x action panel used labeled rows:
```
加密：CVD+扫点优先 ⚡伦敦开盘
结论｜A多：回踩做多
结构｜SVP：站上VAH，偏强；VWAP：价格在上方；EMA：多头排列
确认｜ICT：扫亚低后收回；CVD：主D关键位吸收，伦敦主导
条件｜HTF✓ EMA✓ CVD✓ 位✓
CVD分时｜亚+15.6K 伦-8.2K 纽~0
执行｜做多，VAL 63850等承接；多失效:破VWAP 63120
```

v9.0 removes ALL row label prefixes. Community professional indicators don't waste space on labels — they let position and color carry the semantic role. Result is 6 lines max with higher information density:

```
BTCUSDT · 加密 ⚡伦敦开盘
A多 回踩
VAH上 · VWAP上 · EMA多
ICT 扫亚低收回  CVD 日吸收 伦主
HTF✓ EMA✓ CVD✓ 位✓  亚+15.6K 伦-8.2K 纽~0
多 VAL 63850等承接 · 多失效:破VWAP 63120
```

## Key Changes from v8.x

### Row label removal
- Drop `结论｜`, `结构｜`, `确认｜`, `执行｜`, `条件｜`, `CVD分时｜`
- Line 1 = ticker + market tag + KillZone marker (header)
- Line 2 = grade + action posture
- Line 3 = structure state (VAH/VWAP/EMA)
- Line 4 = confirmation (ICT + CVD on same line)
- Line 5 = checklist + session CVD (merged to save space)
- Line 6 = entry plan + invalidation

### Separator change
- `；` (Chinese semicolon) → ` · ` (middle dot with spaces)
- Module states joined by ` · `: `VAH上 · VWAP上 · EMA多`
- ICT and CVD on same line separated by double space: `ICT ...  CVD ...`

### Signal text compression
- `A多：回踩做多` → `A多 回踩`
- `B多：轻仓等多` → `B多 轻仓`
- `C反多：站回再做` → `C多 等站回`
- `多头减弱：CVD不配合` → `CVD不配多`
- `降级：低流动性` → `X 低流动`
- `禁追：位置不划算` → `X 禁追`

### CVD label simplification
- `主D关键位吸收` → `日吸收` ("关键位" already in conditions row)
- `买盘跟随` → `买盘` (drop redundant "跟随")
- `底背离修复，近关键位` → `底背离` (drop modifier)
- Anchor: `cvdAnchorTf == "D" ? "日" : "W" ? "周" : "M" ? "月"` (not `f_tf_label()`)
- Session dominant: `亚洲主导` → `亚主`, `伦敦主导` → `伦主`, `纽约主导` → `纽主`

### CVD session row merged
- `CVD分时｜亚+15.6K 伦-8.2K 纽~0` independent row → appended to condition row
- Both condition checklist and session CVD fit on one line

### Header row improvement
- Added `syminfo.ticker` prefix: `BTCUSDT · 加密 ⚡伦敦开盘`
- Market tag shortened: `加密` not `加密：CVD+扫点优先`
- `marketTag` variable replaces verbose `marketFocusText`

## Implementation Code

### Header
```pine
string marketTag = marketCrypto ? "加密" : marketForex ? "外汇" : marketMetal ? "金属" : (marketStock or marketIndex) ? "股票" : "通用"
string tickerShort = syminfo.ticker
string actionKillZoneLine = isKillZone ? " ⚡" + killZoneLabel : ""
string headerLine = tickerShort + " · " + marketTag + actionKillZoneLine
```

**Pitfall**: `actionKillZoneLine` must be defined BEFORE `headerLine` (Pine single-pass). Define it right after `killZoneLabel` at ~L983, not later in the action panel section.

### CVD anchor label
```pine
string cvdAnchorLabel = cvdAnchorTf == "D" ? "日" : cvdAnchorTf == "W" ? "周" : cvdAnchorTf == "M" ? "月" : cvdAnchorTf
```

### CVD session dominant
```pine
string cvdLeadSession = ""
if SHOW_SESSION_CVD and cvdLeadAbs != 0
    if math.abs(cvdAsiaSlope) == cvdLeadAbs
        cvdLeadSession := "亚主"
    else if math.abs(cvdLondonSlope) == cvdLeadAbs
        cvdLeadSession := "伦主"
    else
        cvdLeadSession := "纽主"
string cvdSessionSuffix = cvdLeadSession != "" ? " " + cvdLeadSession : ""
```

### Structure row
```pine
string actionValueText = priceAboveVah ? "VAH上" : priceBelowVal ? "VAL下" : priceInVA ? "VA内" : ""
string actionVwapText = vwapExtendedUp ? "VWAP延" : vwapExtendedDn ? "VWAP延下" : nearS ? "VWAP均" : priceAboveS ? "VWAP上" : priceBelowS ? "VWAP下" : ""
string actionEmaText = emaBull ? "EMA多" : emaBear ? "EMA空" : "EMA缠"
string actionStructText = (actionValueText != "" ? actionValueText + " · " : "") + (actionVwapText != "" ? actionVwapText + " · " : "") + actionEmaText
```

### Signal text
```pine
string actionStateText = "观望"
if lowLiquiditySession
    actionStateText := "X 低流动"
else if setupX
    actionStateText := "X 禁追"
else if displayLongA
    actionStateText := "A多 回踩"
else if displayShortA
    actionStateText := "A空 反抽"
// ...
```

### Action assembly (no row labels)
```pine
string actionLine1 = actionStateText
string actionLine2 = actionStructText
string actionLine3 = actionIctText + "  " + actionCvdText
string actionLine4 = lineAction
```

### Session CVD merged into condition row
```pine
string actionChecklistText = ""
if activeLongPlan or activeShortPlan
    // ... checklist items ...
    actionChecklistText := ckHtf + " " + ckEma + " " + ckCvd + " " + ckLoc + (ckSmt != "" ? " " + ckSmt : "")
string actionSessionCvdLine = SHOW_SESSION_CVD and cvdSessionSummary != "" ? cvdSessionSummary : ""
// Both on same line in actionText concatenation
```

## `f_fmt_cvd()` Numeric Formatter

```pine
f_fmt_cvd(float v) =>
    float absV = math.abs(v)
    if absV < 1
        "~0"
    else if absV >= 1e6
        (v > 0 ? "+" : "-") + str.tostring(math.round(absV / 1e5) * 0.1, "0.0") + "M"
    else if absV >= 1e3
        (v > 0 ? "+" : "-") + str.tostring(math.round(absV / 1e2) * 0.1, "0.0") + "K"
    else
        (v > 0 ? "+" : "-") + str.tostring(math.round(absV))
```

Usage: `"亚" + f_fmt_cvd(cvdAsiaAcc)` → `"亚+15.6K"` or `"亚-8.2K"` or `"亚~0"`

## Pitfall: Declaration Order for KillZone Label

`actionKillZoneLine` was defined at the action panel section (~L2297) but referenced by `headerLine` at the start of the action panel section (~L2208). Pine's single-pass execution means `headerLine` saw `actionKillZoneLine` as undeclared.

**Fix**: Define `actionKillZoneLine` immediately after `killZoneLabel` at the Session CVD block (~L983), before any references:

```pine
bool isKillZone = SHOW_KILLZONE and (inKillZoneLondon or inKillZoneNY)
string killZoneLabel = inKillZoneLondon ? "伦敦开盘" : inKillZoneNY ? "纽约开盘" : ""
string actionKillZoneLine = isKillZone ? " ⚡" + killZoneLabel : ""  // ← HERE, before any reference
```

Then the duplicate definition at the action panel section must be removed.
