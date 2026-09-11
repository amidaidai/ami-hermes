# Action Panel: 资金 + 定调 Row Pattern (v8.1, 2026-06-24)

## Purpose

Two new rows added below `确认：` in the single-cell action panel:

```
BTCUSDT · 看CVD+扫点 ⚡伦敦开盘    ← header
结论：A多 回踩                       ← grade + action
结构：SVP VAH上 · VWAP 上 · EMA 多  ← SVP/VWAP/EMA snap
确认：ICT 扫周四亚高收回 · CVD 日买盘 ← ICT event + CVD anchor
资金：亚+15K 伦-3.2K 纽~0 亚主↑     ← session CVD 3-channel + dominant direction
定调：偏多 · D多 · DMI顺多 · VWAP上控 ← bias verdict: HTF + DMI + key structure
HTF✓ EMA✓ CVD✓ 位✓                  ← checklist (only when active plan)
执行：多 VAL 67200等承接 · 多失效:破VWAP ← plan + invalidation
```

## 资金行 Construction

```pine
string actionLineFunding = "资金：" + (SHOW_SESSION_CVD and cvdSessionSummary != "" ? cvdSessionSummary + cvdDirectionHint : SHOW_SESSION_CVD ? "—" : "关闭")
```

Where `cvdDirectionHint` is:
```pine
string cvdDirectionHint = SHOW_SESSION_CVD and cvdLeadSession != "" ? " " + cvdLeadSession + (cvdLeadSlope > 0 ? "↑" : cvdLeadSlope < 0 ? "↓" : "→") : ""
```

Logic: takes the session CVD 3-channel summary (`亚+15K 伦-3.2K 纽~0`), appends the dominant session (`亚主`/`伦主`/`纽主`) + direction arrow (`↑` buy-dominant / `↓` sell-dominant / `→` neutral).

When session CVD is disabled: shows `资金：关闭`.
When session CVD is on but all zero: shows `资金：—`.

## 定调行 Construction

```pine
string actionLineNarrative = "定调：" + narrativeText
```

`narrativeText` composes 4 segments separated by ` · `:
1. **Bias direction**: `偏多`/`偏空`/`观望` — derived from grade/score
2. **HTF context**: `D多`/`W空`/`D震荡` — from `htfBiasText`
3. **DMI momentum**: `DMI顺多`/`DMI顺空`/`DMI走弱`/`DMI过热` — from `dmiVerifyText`
4. **Key structure note** (priority order): swept reclaim/reject > VWAP position > value area position > EMA trend

Examples:
| Scenario | 定调行 |
|----------|--------|
| A级多头，DMI顺向 | `定调：偏多 · D多 · DMI顺多 · VWAP上控` |
| 扫低收回，未确认 | `定调：偏多 · W震荡 · DMI待定 · 扫低收回` |
| X禁追 | `定调：观望 · D多 · DMI过热 · 过热延展禁追` |
| 结构冲突 | `定调：观望 · D空 · DMI走弱 · 多空冲突等确认` |

## Order in actionText

```pine
string actionText = headerLine + "\n" + actionLine1 + "\n" + actionLine2 + "\n" + actionLine3 + "\n" + actionLineFunding + "\n" + actionLineNarrative + (actionChecklistText != "" ? "\n" + actionChecklistText : "") + "\n" + actionLine4
```

资金行 and 定调行 replace the old `actionSessionCvdLine` (which was conditionally appended between checklist and execution). The old variable should be removed.
