# Compact Dashboard Community Standards (2026-06-24)

Collected from TradingView community research on Pine Script dashboard table design patterns.

## AGPro Series Gold Standard

AGPro Labs indicators are the most popular TradingView premium decision-panel series. Their design philosophy (quoted verbatim):

- "compact decision dashboard, **not a large command center**" — excerpt from Execution Window Planner description
- "shortened labels so the chart feels cleaner" — excerpt from Daily Trade Plan Generator changelog
- "Reduced panel weight by replacing the older full dashboard with a compact decision panel" — from AGPro v2 changelog
- Panel fields: **Plan Mode · Entry · Invalidation · Current R · Next Target · Progress** (6 fields max)
- "The first row uses the standard AGPro merged blue header row" — consistent visual language

## Community Consensus Principles

### 1. Do NOT show ticker name
The chart already displays the ticker in the top-left. Showing it again in the dashboard is universally considered wasted space. Reddit and TradingView community consensus: no ticker name in dashboards.

### 2. Limit to 5-6 lines max
Community dashboards average 5-6 informational rows. Beyond 7 lines the panel starts competing with chart candles for visual real estate. AGPro uses 6 fields. Joeyscooking's Multi-Indicator Dashboard uses 5 rows.

### 3. Group by decision phase, not by indicator module
Bad: "SVP VA内 · VWAP 上 · EMA 多 · ICT扫亚低 · CVD日买盘 · SMT多背离"
Good: "结论: A多 · 结构: VA内 VWAP上 EMA多 · 确认: 扫亚低 CVD买盘"

Group evidence (structure/confirmation) under logical headers, not per-indicator names.

### 4. Single-cell table with \n is best practice
TradingView official docs: "table objects were designed for compact data panels — small boxes with 10–30 cells". Single-cell multi-line `\n` approach IS the intended design pattern — not a workaround.

### 5. Abbreviate, don't spell out
AGPro uses "R:" not "Risk:", "TP:" not "Target:". TradingView indicators universally use compact labels. Full-length labels (e.g. `SVP VA内 · VWAP价格延展上方`) waste panel width and force text wrapping.

### 6. Color-code by state, not by indicator
AGPro backgrounds change by Plan Mode (active/inactive/warning). Background color should reflect decision urgency, not which indicator is firing.

## Action Panel Line Budget

Community-optimal allocation for multi-factor dashboard:

| Line | Content | Community Source |
|---|---|---|
| Header | Session timing + market focus hint | AGPro "merged blue header row" |
| 结论 | Grade + directional bias + DMI | AGPro "Plan Mode" |
| 结构 | Key price levels proximity | AGPro "Entry" / "Current R" |
| 确认 | Sweep/CVD/SMT events | AGPro "Progress" |
| 核对 | Checklist + calibration | AGPro "Invalidation" |
| 执行 | Action + invalidation price | AGPro "Target" |

**6 lines total.** The original v9.0 8-line format (with separate 资金 and 定调 rows) exceeds community-optimal density. Session CVD (资金) should fold into 确认 since both describe order-flow state. 定调 (bias verdict) should merge into 结论 since both describe directional posture.
