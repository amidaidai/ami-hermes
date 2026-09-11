# v9.5 Compact Action Panel (6-line format)

Date: 2026-06-24 · Source: community audit of AGPro series + Reddit/TradingView best practices

## Community Standard (AGPro Gold Standard)

- AGPro Execution Window Planner: "compact decision dashboard, not a large command center"
- AGPro Trade Management Planner Elite: 6 fields (Mode · Entry · Invalidation · R · Target · Progress)
- Community consensus: no ticker name in dashboards (chart already shows it), 5-6 lines max
- TradingView official: "tables designed for compact data panels"

## v9.5 6-Line Format (down from 8)

```
1 KZ伦窗 · CVD+扫点                                        ← header: remove ticker, keep KZ + focus
2 结论：A多 偏多 · 4h多 1D多 · DMI顺多 · VAH上控             ← merge 定调 into 结论
3 结构：VA内 · VWAP上 · EMA多 · 近日高 · 3扫/2待             ← strip SVP prefix, sweep count moved here
4 确认：扫亚低收回 · CVD日买盘 亚主+ · SMT多背离               ← strip ICT/CVD prefix, compact funding merged
5 核对：HTF✓ EMA✓ CVD✓ 位✓ · 多68%                           ← calibration always appended
6 执行：等VAH承接 · 失效:破VWAP 62300                         ← remove direction prefix (already in 结论)
```

## Code Changes Summary

### headerLine (L2208-2210)
```pine
// OLD:
string focusHint = marketCrypto ? "看CVD+扫点" : ...
string headerLine = "品种：" + syminfo.ticker + " · " + focusHint + actionKillZoneLine

// NEW:
string focusHint = marketCrypto ? "CVD+扫点" : ...
string headerLine = actionKillZoneLine != "" ? actionKillZoneLine + " · " + focusHint : focusHint
```

### actionLine1 — merge 定调
```pine
// OLD:
string actionLine1 = "结论：" + actionStateText
// ... later: string actionLine5 = "定调：" + actionBiasWord + " · " + mtfBiasLine + ...

// NEW:
string actionLine1 = "结论：" + actionStateText + " " + actionBiasWord + " · " + mtfBiasLine + " · DMI" + dmiVerifyText + " · " + actionStructureVerdict_tone
```

### actionLine2 — strip SVP prefix, add sweep count
```pine
// OLD:
string actionLine2 = "结构：SVP " + actionValueText + " · VWAP " + actionVwapText + " · EMA " + actionEmaText + actionDayWeekSuffix + actionSvpSuffix

// NEW:
string actionLine2 = "结构：" + actionValueText + " · VWAP" + actionVwapText + " · EMA" + actionEmaText + actionDayWeekSuffix + actionSvpSuffix + (actionSweepSummary != "" ? " · " + actionSweepSummary : "")
```

### actionLine3 — strip ICT/CVD prefix, merge compact funding
```pine
// OLD:
string actionLine3 = "确认：" + actionIctText + " · " + actionCvdText + (smtBullDiv or smtBearDiv ? " · " + smtText : "") + (actionSweepSummary != "" ? " · " + actionSweepSummary : "")

// NEW:
string actionLine3 = "确认：" + str.replace(actionIctText, "ICT ", "") + " · CVD" + str.replace(actionCvdText, "CVD", "") + (smtBullDiv or smtBearDiv ? " · " + smtText : "") + (cvdLeadSession != "" ? " " + cvdDirectionHint : "")
```

### actionLine4 — remove direction prefix
```pine
// OLD:
lineAction := "多 等" + pullbackLevelText + "承接 · " + longInvalidText
lineAction := "空 等" + reboundLevelText + "承压 · " + shortInvalidText

// NEW:
lineAction := "等" + pullbackLevelText + "承接 · " + longInvalidText
lineAction := "等" + reboundLevelText + "承压 · " + shortInvalidText
```

### longInvalidText / shortInvalidText — remove 多/空 prefix
```pine
// OLD:
string longInvalidText = "多失效:" + invalidBaseText + " " + f_fmt_price(longInvalidPrice)
string shortInvalidText = "空失效:" + invalidBaseText + " " + f_fmt_price(shortInvalidPrice)

// NEW:
string longInvalidText = "失效:" + invalidBaseText + " " + f_fmt_price(longInvalidPrice)
string shortInvalidText = "失效:" + invalidBaseText + " " + f_fmt_price(shortInvalidPrice)
```

### Checklist — add calibration, remove ckCal
```pine
// OLD:
string ckCal = calDegradeLong or calDegradeShort ? "❌校准" : calWeak ? "⚠校准" : ""
actionChecklistText := ckHtf + " " + ckEma + " " + ckCvd + " " + ckLoc + (ckSmt != "" ? " " + ckSmt : "") + (ckCal != "" ? " " + ckCal : "")

// NEW:
actionChecklistText := "核对：" + ckHtf + " " + ckEma + " " + ckCvd + " " + ckLoc + (ckSmt != "" ? " " + ckSmt : "") + " · " + calibrationTextFull
```

### actionText assembly — 6-line
```pine
// OLD (8-9 lines):
string actionText = headerLine + "\n" + actionLine1 + "\n" + actionLine2 + "\n" + actionLine3 + "\n" + actionLineFunding + (actionChecklistText != "" ? "\n" + actionChecklistText : "") + "\n" + actionLine5 + "\n" + actionLine4

// NEW (5-6 lines):
string actionText = headerLine + "\n" + actionLine1 + "\n" + actionLine2 + "\n" + actionLine3 + (actionChecklistText != "" ? "\n" + actionChecklistText : "") + "\n" + actionLine4
```

## Deleted Variables

- `actionLine5` — merged into `actionLine1`
- `actionLineFunding` — compact version merged into `actionLine3`
- `ckCal` — replaced by `calibrationTextFull`

## Key Principles

1. **No ticker name**: Chart shows it, dashboard space is for decisions
2. **No module prefix duplication**: Row template provides "SVP"/"ICT"/"CVD" prefix pattern once, value text is bare
3. **Direction once**: 结论 carries direction, 执行 just describes action
4. **No orphaned lines**: Every line earns its space — old 资金/定调 were redundant with 确认/结论
5. **Community-aligned**: AGPro 6-field standard, no more than 6 visible lines
