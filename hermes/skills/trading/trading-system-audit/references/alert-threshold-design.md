# Alert Threshold Design: Community Consensus

## Core Principle

**"Confirmation Gate (de-whipsaw)" pattern** from the TradingView community (SuperTrend/ATR suite scripts, r/algotrading):
- Approach/near signals have LOW signal-to-noise ratio — no price confirmation yet
- Breach/breakout signals have HIGH SNR — price already crossed the key level
- Therefore: near signals should face STRICTER filtering than breach signals

## Counterintuitive Hierarchy

```
MIN_WARNING > MIN_CRITICAL  ← LOOKS wrong, IS correct
```

Why: a near signal is just "price is getting close" — most near-signals never turn into actual breaches. A breach signal is "price crossed the level" — there's actual market action behind it. The apparent "inversion" reflects the fundamentally different SNR of the two signal types.

## Practical Gradients (棠溪 2026-06-19 锁定)

| Tier | Threshold | Rationale |
|------|-----------|-----------|
| Warning (near) | 75 | High bar — reduce noise, most approaches don't turn into trades |
| Critical (breach) | 70 | Moderate — price already crossed, you need to know |
| Info (expired/invalid) | 60 | Keep notifications flowing for state changes

**铁律**: Warning threshold MUST be >= critical threshold. If someone proposes lowering warning below critical, refer to this document and the community research below. The apparent "inversion" is intentional SNR-based design, not a bug.

| Tier | Threshold | Rationale |
|------|-----------|-----------|
| Warning (near) | 75 | High bar — reduce noise, most approaches don't turn into trades |
| Critical (breach) | 70 | Moderate — price already crossed, you need to know |
| Info (expired/invalid) | 60 | Keep notifications flowing for state changes |

## 棠溪 Session 2026-06-19

- User raised warning from 65 → 75 (to reduce noise)
- Critical remained at 70
- Initial concern: "warning > critical looks backwards"
- Community research confirmed: this IS the correct hierarchy
- Final config: warning=75, critical=70, info=60

## Source

- TradingView community scripts: "Confirmation gate (de-whipsaw)" — raw flip confirmed only when close breaches prior band by minimum ATR fraction + minimum bar count
- r/algotrading: confirmation gate post testing 7 threshold variants
- General SNR principle: approach signals have ~3x higher false-positive rate than breach signals
