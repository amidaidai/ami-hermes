# Multi-Timeframe Linked Action Panel Pattern

Use this reference when improving a Pine right-top action panel for a mature multi-market dashboard. It captures a user correction from a v10 SVP/ICT/VWAP/EMA/CVD iteration: the panel must not merely label the current chart as `5m/15m执行`, `1h/4h结构`, or `1D背景`. Those labels are obvious and waste decision space. The panel must explain how the current timeframe links to higher and lower timeframes.

## Community principle

Top-down / MTFA consensus:

- HTF / background timeframe = map and directional bias: what side is preferred.
- MTF / structure timeframe = setup and route: where the market has to break, reclaim, pull back, or reject.
- LTF / execution timeframe = trigger: when to enter after the structure plan is confirmed.

The action panel should therefore display **role + chain + current HTF bias + execution handoff**, not a static timeframe taxonomy.

## Preferred header wording

Avoid:

```pine
"层级：" + tfRole + " · 5m/15m执行·1h/4h结构·1D背景"
```

Prefer:

```pine
string htfArrow = htfBull ? "↑" : htfBear ? "↓" : "→"
string execTfText = marketMetal ? "5m" : (marketStock or marketIndex) ? "5m" : "5m/15m"
string structTfText = marketMetal ? "15m/1h" : (marketStock or marketIndex) ? "15m/1h" : "1h/4h"
string bgTfText = marketCrypto ? "1D" : marketMetal ? "4h/1D" : marketForex ? "1D" : "4h/1D"
string tfDutyText = tfRole == "执行" ? "低周触发" : tfRole == "结构" ? "本级定结构" : "高周定方向"
string linkMapText = "高周" + bgTfText + "→结构" + structTfText + "→执行" + execTfText
string headerLine = "联动：" + tfDutyText + " · " + linkMapText + " · 当前高周" + htfTfLabel + htfArrow + " · " + focusHint
```

Examples:

- `联动：低周触发 · 高周1D→结构1h/4h→执行5m/15m · 当前高周4h↑ · 看CVD+资金`
- `联动：本级定结构 · 高周1D→结构1h/4h→执行5m/15m · 当前高周1D↓ · 看CVD+扫点`
- `联动：高周定方向 · 高周1D→结构1h/4h→执行5m/15m · 当前高周1W↑ · 看CVD+扫点`

## Linked plan line

The plan must stay at the bottom of the panel. It should be linked across timeframes:

```pine
string mtfConflictText = activeLongPlan and htfBear ? " · 高周逆风降级" : activeShortPlan and htfBull ? " · 高周逆风降级" : ""
string linkedPlanText = tfRole == "执行" ? lineAction + " · 上看结构" + structTfText + " 下按本K确认" :
     tfRole == "结构" ? longPlanText + " / " + shortPlanText + " · 高周" + htfTfLabel + htfArrow + " · 去" + execTfText + "等触发" :
     (htfBull ? "只做多头结构，等" + structTfText + "回踩" : htfBear ? "只做空头结构，等" + structTfText + "反抽" : "高周中性，等结构先破边")
string actionLinePlan = "计划：" + linkedPlanText + " · " + failoverText + mtfConflictText
```

Meaning:

- Execution chart: execute only after the current candle confirms, while still checking the structure timeframe.
- Structure chart: provide both long and short route plans, then hand off entry to the execution timeframe.
- Background chart: do not fabricate an entry; define the preferred side and wait for MTF structure.
- If the active side conflicts with HTF bias, append `高周逆风降级`.

## Panel ordering

For this user, keep `计划：` last:

1. 联动
2. 结论
3. 结构
4. 确认
5. 关键
6. 评估
7. 计划

## Additional HUD wording corrections from the same iteration

- `磁吸` must name the exact pool/level, not only score/direction. Use `磁吸上方:上周 高 64200 分82` and `磁吸下方:周二 低 61500 分76`.
- Replace vague `风险：位置3/确认5/延展0` with an evaluative checklist line containing total score, stop, R:R, target magnet, and components, e.g. `评估：总分7/10 · 止损62100(1.4ATR) · R:R 2.1R · 目标磁吸82↑ · 位置3/3 确认4/5 R:R分2/2 延展扣1`.
- Do not use obvious/timeframe-only prose such as `等5m/15m执行` or `等1h/4h结构`; say what is handed off and why.

## Verification grep

```bash
grep -c 'string headerLine = "联动："' file.txt
grep -c '高周逆风降级' file.txt
grep -c 'actionLine6 + "\\n" + actionLine5' file.txt  # confirms plan is after evaluation
grep -c '层级：\|等5m/15m执行\|等1h/4h结构' file.txt  # should be 0 in rendered strings
```
