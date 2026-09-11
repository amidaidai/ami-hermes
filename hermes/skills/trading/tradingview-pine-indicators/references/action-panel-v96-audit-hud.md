# Action Panel v9.6 Audit HUD Pattern

Use this when auditing or improving an already-mature SVP/ICT/VWAP/EMA/CVD Pine indicator whose right-top action panel is too terse to execute from.

## Trigger

- User asks for a full audit of an uploaded Pine indicator.
- The script already has a compact one-cell action panel.
- Community research points to HUD-style dashboards: profile/VWAP/CVD context, readable score, nearest levels, and calibration feedback.

## Community-Aligned Principles

- Keep one right-top `table` cell; do not add chart markers or a second table.
- Do not repeat ticker name in the header.
- Add execution context, not more raw indicators.
- Show nearest actionable levels directly in the panel.
- Treat CVD as confirmation/quality, not a standalone trade trigger.
- Preserve calibration feedback so the trader sees whether recent signals are working.
- Prefer black text on colored backgrounds for this user.
- Remove visual-noise outputs such as session `bgcolor()` unless the user explicitly wants background shading.

## Panel Line Budget

Preferred v9.6 line set:

1. Header: `KZ · focus` or just market-adaptive focus.
2. `结论：` setup state + bias + `多/空` score + reversal score + DMI state.
3. `结构：` VA state + VWAP state + EMA state + structure verdict + SVP/pool + sweep count.
4. `位置：` nearest upper/lower actionable level with prices + MTF arrows.
5. `确认：` ICT event + CVD state/quality + SMT + leading session.
6. `核对：` HTF/EMA/CVD/location checklist + calibration.
7. `执行：` active plan + concrete execution/invalidation sentence.

## Minimal Patch Shape

Add these variables after `actionValueText/actionVwapText/actionEmaText` and before any `actionLine*` use:

```pine
string actionScoreText = "多" + str.tostring(trendLongScore) + "/空" + str.tostring(trendShortScore) + " · 反" + str.tostring(reversalLongScore) + "/" + str.tostring(reversalShortScore)
string actionNearText = "上" + f_price_text(resName, resPrice) + " 下" + f_price_text(supName, supPrice)
string actionPlanText = activeLongPlan ? longPlanText : activeShortPlan ? shortPlanText : longPlanText + " / " + shortPlanText
```

Then assemble:

```pine
string actionLine1 = "结论：" + actionStateText + " " + actionBiasWord + " · " + actionScoreText + " · DMI" + dmiVerifyText
string actionLine2 = "结构：" + actionValueText + " · VWAP" + actionVwapText + " · EMA" + actionEmaText + " · " + actionStructureVerdict_tone + actionSvpSuffix + (actionSweepSummary != "" ? " · " + actionSweepSummary : "")
string actionLine3 = "位置：" + actionNearText + " · " + mtfBiasLine
string actionLine4 = "确认：" + str.replace(actionIctText, "ICT ", "") + " · CVD" + str.replace(actionCvdText, "CVD", "") + (smtBullDiv or smtBearDiv ? " · " + smtText : "") + (cvdLeadSession != "" ? " " + cvdDirectionHint : "")
string actionLine5 = "执行：" + actionPlanText + " · " + lineAction
string actionText = headerLine + "\n" + actionLine1 + "\n" + actionLine2 + "\n" + actionLine3 + "\n" + actionLine4 + (actionChecklistText != "" ? "\n" + actionChecklistText : "") + "\n" + actionLine5
color actionTextColor = color.black
```

## Visibility / Noise Fixes Often Found During This Audit

- Change invisible dark-theme defaults like `POC_COLOR = #0F0F0F` to visible mid-tones such as `#78909C`.
- Default `SHOW_OPEN_ONLY_ACTIVE` to `false` when the user expects live session high/low labels.
- Default `SHOW_DO_LINE` to `true` when DO is an important structural reference.
- Remove or disable `bgcolor()` session shading for this user; KillZone/session context belongs in text and levels, not background paint.

## Verification

Run text-level checks because there is no local TradingView compiler:

- `bgcolor(` count should be `0` if removing session shading.
- `color.white` count should be `0` for black-text panel preference.
- Invisible defaults such as `#0F0F0F` should be absent.
- Each `string actionLine1` through `string actionLine5` should appear exactly once.
- `actionScoreText` must be declared before `actionLine1`.
- Parentheses and bracket balances should be zero.
- Count output-like calls with `plot(` + `fill(` + `bgcolor(` + `table.new(` and keep well under TradingView's 64-series limit.
- Final syntax still must be verified in TradingView Pine Editor.
