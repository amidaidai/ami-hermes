# Multi-Market Capability Audit Framework

Framework for assessing whether a Pine Script indicator adequately covers multiple market types. Developed from the 2026-06-24 audit of SVP+ICT+VWAP+EMA+CVD.

## Audit Dimensions

For each market type (Crypto, Metals, Forex, Stock, Futures, Index), assess:

1. **Parameter Layer**: Does the market have entries in all `eff*` parameter computations?
2. **SVP Tuning**: Profile period, precision, and row count appropriate for the market's volatility profile?
3. **VWAP Anchor**: Anchor selection appropriate for the market's typical trading session?
4. **CVD Tuning**: Anchor period and LTF resolution appropriate for the market's liquidity profile?
5. **DMI Thresholds**: ADX trend/hot thresholds appropriate for the market's typical volatility?
6. **KillZone Timing**: KillZone windows aligned with the market's actual high-volatility periods?
7. **SMT Pair**: Cross-instrument divergence pair appropriate for the market?
8. **Session Filtering**: Weekend/holiday filtering correct for the market's trading hours?
9. **Scoring Bonuses**: Any market-specific bonus points in the scoring engine?
10. **Decision Engine**: Any market-specific gating in grade assignment?

## Scoring Rubric

| Grade | Meaning |
|-------|---------|
| A | All 10 dimensions have market-specific values; parameter choices are battle-tested |
| A- | 8-9 dimensions covered; minor tuning gaps |
| B+ | 6-7 dimensions covered; parameter choices are reasonable |
| B | 4-5 dimensions covered; usable but not optimized |
| C+ | 1-3 dimensions covered; detected but default params only |
| C | Detected as a market type but zero adaptation |
| F | Not detected as a market type |

## Common Gaps by Market Type

| Market | Typical Gaps |
|--------|-------------|
| **Crypto** | DMI thresholds too low (crypto ADX ranges higher); CVD periods may be too short on low TF |
| **Metals (XAU)** | SMT pair correctness; KillZone NY window may be too wide |
| **Forex** | EMA periods too slow; DMI thresholds too high; KillZone windows may be forex-specific |
| **Stock** | EMA periods too fast on daily; no SMT pair; ICT session times mismatch |
| **Futures** | MOST COMMON GAP: detected but ZERO parameter adaptation — all 10 dimensions default |
| **Index** | Same as stock; often double-counted with futures |

## Optimization Priority

1. **Futures adaptation** (low effort, high impact): Inherit stock/index parameters in all `eff*` branches
2. **KillZone per market** (medium effort, high impact): Crypto/metals wide windows, forex/stock narrow
3. **SVP rows per market** (low effort, medium impact): Crypto needs more, forex needs fewer
4. **ADX per market** (low effort, medium impact): Different volatility profiles need different thresholds
5. **ICT session times** (high effort, low impact for existing markets): Only needed for futures/stocks
