# Action Panel v9.0 — With Labels (User-Preferred)

The user explicitly prefers `：` (Chinese colon) as the row label separator, NOT `｜` (full-width pipe). This reference supersedes `references/action-panel-v90-no-labels.md` for this user's indicators.

## Final Structure (8 rows max)

```
品种：BTCUSDT · 看CVD+扫点 ⚡伦敦开盘  ← header
结论：A多 回踩                           ← grade
结构：SVP VAH上 · VWAP 上 · EMA 多 · 日↑ 周↑  ← SVP/VWAP/EMA + day/week pool
确认：ICT 扫周四亚高收回 · CVD 日买盘 · 5扫/7待  ← ICT event + CVD + sweep counter
资金：亚+15K 伦-3.2K 纽~0 亚主↑        ← session CVD
HTF✓ EMA✓ CVD✓ 位✓                     ← checklist (conditional)
定调：偏多 · 15m↑ 1h↑ 4h→ 1D↑ · DMI顺多 · 扫低回  ← multi-TF bias + DMI + structure
执行：多 VAL 67200等承接 · 多失效:破VWAP ← plan
```

## Row Construction Rules

### Header Line
```pine
string headerLine = "品种：" + syminfo.ticker + " · " + focusHint + actionKillZoneLine
```
- `focusHint` is market-adaptive: `看CVD+扫点` (crypto), `看ICT+SVP` (metals), `看VWAP+EMA` (forex), `看SVP+VWAP` (stocks/indices), `看综合` (other)
- `actionKillZoneLine` shows ` ⚡伦敦开盘` or ` ⚡纽约开盘` during KillZone only

### 结论 Line
```pine
string actionLine1 = "结论：" + actionStateText
```
- Compressed format: `A多 回踩`, `B空 轻仓`, `X 禁追`, `CVD不配多`, `等多 回踩`

### 结构 Line (v9.0+ with Day/Week Pool)
```pine
string actionLine2 = "结构：SVP " + actionValueText + " · VWAP " + actionVwapText + " · EMA " + actionEmaText + actionDayWeekSuffix
```
- Value texts strip module names: `"VAH上"` not `"SVP VAH上"`, `"上"` not `"VWAP上"`, `"多"` not `"EMA多"`
- Separator: ` · ` (middle dot, U+00B7), not `；` (Chinese semicolon)
- **Day/Week Pool Suffix** (appended automatically, v9.0+):
  - Compute `actionDayPoolText` from `prevDayHigh`/`prevDayLow` via `request.security("D", high[1], barmerge.gaps_on, barmerge.lookahead_on)`:
    - `日↑` = close > prev day high (breakout)
    - `日↓` = close < prev day low (breakdown)
    - `近日高` = within 0.8 ATR below day high (testing resistance)
    - `近日低` = within 0.8 ATR above day low (testing support)
    - Mid-range = not shown (no suffix)
  - Same pattern for week: `周↑` / `周↓` / `近周高` / `近周低`
  - Combined suffix: `actionDayWeekSuffix = actionDayPoolText != "" ? " · " + actionDayPoolText + (actionWeekPoolText != "" ? " " + actionWeekPoolText : "") : actionWeekPoolText != "" ? " · " + actionWeekPoolText : ""`

### 确认 Line (v9.0+ with Sweep Counter)
```pine
string actionLine3 = "确认：" + actionIctText + " · " + actionCvdText + (actionSweepSummary != "" ? " · " + actionSweepSummary : "")
```
- ICT: `ICT 扫周四亚高收回`, `ICT —` when no event
- CVD: `CVD 日买盘`, `CVD 日吸收 亚主`, `CVD 日顶背离`
- **Sweep Counter** (v9.0+, appended automatically):
  ```pine
  string actionSweepSummary = ""
  if SHOW_ICT_LEVELS and array.size(levels) > 0
      int sweptCount = 0
      int unsweptCount = 0
      int levelI = 0
      while levelI < array.size(levels)
          ICTLevel evLvl = array.get(levels, levelI)
          if evLvl.swept
              sweptCount := sweptCount + 1
          else if not evLvl.isHidden
              unsweptCount := unsweptCount + 1
          levelI := levelI + 1
      actionSweepSummary := str.tostring(sweptCount) + "扫/" + str.tostring(unsweptCount) + "待"
  ```
  - Output: `5扫/7待` (5 swept, 7 waiting) or empty when ICT is off
  - Iterates the global `levels[]` array, counting `swept`; `isActive` only means session still forming and must not be used as swept/waiting status

### 资金 Line (v8.1+)
```pine
string actionLineFunding = "资金：" + (SHOW_SESSION_CVD and cvdSessionSummary != "" ? cvdSessionSummary + cvdDirectionHint : SHOW_SESSION_CVD ? "—" : "关闭")
```
- `cvdSessionSummary`: `亚+15K 伦-3.2K 纽~0`
- `cvdDirectionHint`: ` 亚主↑` (dominant session + arrow: ↑buy ↓sell →flat)
- Falls back to `资金：—` or `资金：关闭`

### 定调 Line (v9.0+ — Multi-TF Bias)

**Multi-TF Bias Function** (placed near L815 after `htfBiasText`):
```pine
// Multi-TF bias — all periods at a glance for 定调
f_mtf_bias_str(string tf) =>
    [c, eF, eS, v] = request.security(syminfo.tickerid, tf, f_htf_pack(), ignore_invalid_symbol=true)
    not na(c) and c >= v and eF >= eS ? "↑" : not na(c) and c < v and eF < eS ? "↓" : not na(c) ? "→" : "—"
string mtfBiasLine = "15m" + f_mtf_bias_str("15") + " 1h" + f_mtf_bias_str("60") + " 4h" + f_mtf_bias_str("240") + " 1D" + f_mtf_bias_str("D")
```
- Reuses existing `f_htf_pack()` → `[close, ema(close,21), ema(close,55), sma(hlc3,50)]`
- Output: `15m↑ 1h↑ 4h→ 1D↑` — compact TF+bias in one string
- `↑`=bull (price≥VWAP & EMA21≥55), `↓`=bear, `→`=neutral, `—`=no data
- 4 `request.security()` calls — one per TF

**定调 Composition** (action panel section):
```pine
// Computed BEFORE actionLine1, using existing engine variables
string actionBiasWord = activeLongPlan or displayLongA or setupLongB or setupLongC ? "偏多"
    : activeShortPlan or displayShortA or setupShortB or setupShortC ? "偏空"
    : trendLongScore >= trendShortScore + 2 ? "偏多"
    : trendShortScore >= trendLongScore + 2 ? "偏空"
    : "观望"
string actionStructureVerdict_tone = sweptLowReclaimed ? "扫低回"
    : sweptHighRejected ? "扫高拒"
    : sweptLowNow ? "扫低中"
    : sweptHighNow ? "扫高中"
    : vwapExtendedUp ? "VWAP延"
    : vwapExtendedDn ? "VWAP压"
    : priceAboveVah ? "VAH上控"
    : priceBelowVal ? "VAL下控"
    : emaBull ? "EMA多排"
    : emaBear ? "EMA空排"
    : "等结构"
string actionLine5 = "定调：" + actionBiasWord + " · " + mtfBiasLine + " · DMI" + dmiVerifyText + " · " + actionStructureVerdict_tone
```
- Output: `定调：偏多 · 15m↑ 1h↑ 4h→ 1D↑ · DMI顺多 · 扫低回`
- `mtfBiasLine` replaces old single-HTFP `"D" + htfBiasText` — shows all four TFs at a glance
- User explicitly requested: "不是看多个周期一起吗？" — ALL periods visible in one row
- Place `f_mtf_bias_str()` + `mtfBiasLine` near L815 (after existing `htfBiasText`) so they're declared before use
- Place `actionBiasWord`, `actionStructureVerdict_tone`, `actionLine5` in action panel section before `actionLineFunding`

### 执行 Line
```pine
string actionLine4 = "执行：" + lineAction
```
- Active plan: `多 VAL 67200等承接 · 多失效:破VWAP 66880`
- X/conflict: `不追，等VWAP` or `低流动，等伦敦/纽约`

## Assembly (v9.0+ Order)
```pine
string actionText = headerLine + "\n" + actionLine1 + "\n" + actionLine2 + "\n"
    + actionLine3 + "\n" + actionLineFunding
    + (actionChecklistText != "" ? "\n" + actionChecklistText : "")
    + "\n" + actionLine5 + "\n" + actionLine4
```
Row order: header → 结论 → 结构 → 确认 → 资金 → [checklist] → 定调 → 执行

## Key Differences from v9.0-no-labels
- Row prefixes are KEPT (`结论：`, not bare `A多 回踩`)
- Separator is `：` (Chinese colon), not `｜` (pipe)
- `资金：` row is always present (not merged into condition row)
- `定调：` row is new in v8.1+
