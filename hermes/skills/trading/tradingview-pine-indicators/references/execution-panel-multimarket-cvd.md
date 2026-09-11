# Multi-Market Execution Panel Pattern

Session-derived pattern for a single TradingView overlay indicator shared across multiple markets.

## What the panel should show

Use one top-right cell or panel, not a floating label spread across the chart.

Preferred line order:
1. Market focus + current state + ICT event
2. SVP / VWAP / EMA / CVD compact states
3. Action + invalidation / no-trade note

## Market emphasis by asset class

- Crypto: emphasize CVD, sweep/reclaim, VWAP extension, absorption/distribution.
- Forex: emphasize VWAP, EMA, and structure more than raw CVD.
- Metals (XAU/XAG): emphasize ICT sweeps, SVP value zones, VWAP acceptance, and CVD only at key levels.
- Stocks / indices: emphasize SVP + VWAP + EMA; CVD is supportive, not primary.

## CVD integration rule

- Treat CVD as a confirmer at key levels, not a standalone directional source.
- Show `CVD多 / CVD空 / 吸收多 / 派发空 / 底背离 / 顶背离` in the panel.
- If a bullish plan conflicts with bearish CVD evidence, downgrade the plan to `多减弱 / 不追 / 等CVD修复`.
- If a bearish plan conflicts with bullish CVD evidence, downgrade analogously.

## ICT integration rule

- Show the latest ICT event in compressed form: `扫高`, `扫低`, `扫高拒绝`, `扫低收回`.
- Keep sweeps tied to execution: a sweep only matters when it is near a meaningful SVP/VWAP level.

## Minimal wording template

```text
市场主看因子｜状态｜ICT事件｜关键位+动作
SVP状态/VWAP状态/EMA状态/CVD状态
做多/做空/不追｜失效或等待条件
```

## Why this pattern works

Community consensus repeatedly favored:
- value/structure tools first (`SVP`, `VWAP`)
- ICT sweep context second
- CVD as a confirmation layer
- short execution wording over dense dashboards

The goal is to make the user know, in one glance:
- what is happening
- what to watch
- whether to act
- what would invalidate the idea
