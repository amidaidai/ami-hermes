# Community Audit Scoring Framework (2026-06-24)

## When to Use
When the user asks for a community benchmarking audit of a multi-market TradingView Pine Script dashboard. Use web_search + web_extract across multiple sources (TradingView scripts, Reddit, GitHub, X) to compare against community best practices.

## 10-Dimension Rubric

| # | Dimension | Weight | Community Standard |
|---|-----------|--------|-------------------|
| 1 | 模块覆盖度 | 10 | SVP+VWAP+EMA+ICT+CVD+DMI+SMT+MTF = full stack |
| 2 | CVD 质量门控 | 10 | quality guard + freshness + key-level gate + halflife |
| 3 | 多市场适配 | 10 | adaptive params per market, focus hints, differentiated weights |
| 4 | 决策引擎 | 10 | A/B/C/X grades + stable bars + conflict detection |
| 5 | 行动面板 | 10 | ≤8 rows, one concept per row, compact readable |
| 6 | 扫线系统 | 10 | shared array, merged labels, sweep counter, multi-source |
| 7 | 前向校准 | 10 | hit rate tracking, feedback into decision system |
| 8 | 告警系统 | 10 | alertcondition for all high-signal states |
| 9 | 参数控制 | 10 | grouped inputs, all controls actually used |
| 10 | 图表整洁度 | 10 | single table, no clutter, clean settings panel |

## Scoring Guidelines

- **9-10**: Community-leading, matches or exceeds open-source benchmarks
- **7-8**: Solid, aligns with community consensus
- **5-6**: Present but incomplete or display-only
- **3-4**: Missing or misconfigured
- **1-2**: Anti-pattern

## Calibration Feedback Threshold

Community consensus: forward calibration should FEED BACK into decisions, not just display.

### Three-Level Feedback System (v9.3+)

| Level | Condition | Display | Action |
|-------|-----------|---------|--------|
| 样少 | `calMinSamples < 5` | 定调: `校准 多X%/空Y% 样少` | Info only |
| ⚠低 | `calTotal >= 5 AND calRate < 40%` | 定调: `⚠低` | Warn in 定调 |
| ❌校准 | `calWeak AND (setupLongB or setupShortB or setupLongC or setupShortC)` | 条件行: `❌校准` | Block: checklist shows red flag for B/C grades |

```pine
int calMinSamples = math.min(calLongTotal, calShortTotal)
bool calFewSamples = calMinSamples < 5
string calibrationTextFull = calibrationText + (calFewSamples ? " 样少" : calWeak ? " ⚠低" : "")
bool calDegradeLong = calLongWeak and (setupLongB or setupLongC)
bool calDegradeShort = calShortWeak and (setupShortB or setupShortC)

// In checklist row:
string ckCal = calDegradeLong or calDegradeShort ? "❌校准" : calWeak ? "⚠校准" : ""
```

The `❌校准` gate on the checklist row only fires for B/C grade setups — A-grade signals are strong enough to ignore calibration weakness. This prevents over-trusting B/C setups when the model's recent hit rate is poor.

## Community-Sourced Pitfalls for Multi-Market Dashboards

1. **TradingView CVD ≠ real order flow** — Reddit consensus confirms CVD on TV is an estimate using up/down tick volume. Treat as confirmation layer, never standalone signal.
2. **ICT+VP is community gold standard** — Use VP for structural context (VAH/VAL/POC), ICT for entry timing (sweeps). This combination outperforms standalone use.
3. **Market adaptation is mandatory** — Crypto ≠ Forex ≠ Metals. Crypto leans CVD/sweeps, Forex leans VWAP/EMA, Metals lean ICT/VP sweeps.
4. **Forward calibration is the real edge** — Community emphasizes "honest backtest" over more indicators. A simple hit-rate counter with feedback is better than 3 more indicators.
5. **Visual cleanliness matters** — Top TradingView scripts use single tables over multi-row dashboards. Clutter correlates negatively with usability scores.
6. **SVP extreme sweeps are community-unique** — Almost no open-source scripts combine VP extremes with ICT sweep detection. This is a differentiating feature.

## Search Strategy

Search 4-5 themes separately:
1. "TradingView multi-market indicator scoring system"
2. "volume profile sweep lines ICT integration"
3. "Reddit CVD orderflow quality reliability TradingView" (notable for critique)
4. "site:tradingview.com/script combined dashboard Pine Script"
5. "forward calibration hit rate Pine Script indicator"

Extract concrete thresholds, formulas, and critique — not one-off market opinions.
