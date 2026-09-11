# Market-Adaptive Orderflow v8.1 Pattern

Use this reference when improving a Pine overlay dashboard that combines SVP/Volume Profile, ICT liquidity sweeps, VWAP, EMA, DMI, and CVD.

## Session Learning

The user asked for a full community-informed upgrade after table removal. The useful durable pattern was not another visual layer; it was splitting the system into:

1. A live no-table indicator for execution and alerts.
2. A companion `strategy()` file for TradingView backtesting.
3. Data Window replay fields so signals can be exported and audited.

## Community Consensus Encoded

- CVD should be a key-level confirmation layer, not an independent directional engine.
- Absorption/distribution only matters near meaningful levels: VAH/VAL/POC/VWAP/nPOC/liquidity sweep points.
- A-grade setups should require location + sweep/reclaim or value-area/VWAP acceptance + CVD confirmation + HTF non-conflict.
- Mid-range signals should be downgraded; do not promote them to A just because multiple indicators point the same way.
- VWAP extension and ADX heat should produce no-chase/risk states rather than late entries.
- Volume Profile is the structural map; EMA/DMI are filters, not primary trade location.

## v8.1 Market-Adaptive Layer

Add an effective-parameter layer rather than mutating user inputs directly:

- `MARKET_ADAPTIVE_ENGINE`: master switch.
- `effCvdWeight`: higher for crypto, lower for forex/stocks/options when native volume/order flow is weaker.
- `effAKeyLevelAtr`: market-specific key-level distance for A-grade gating.
- `effCvdKeyLevelAtr`: market-specific CVD confirmation distance.
- `effVwapExtendedAtr`: market-specific no-chase VWAP extension threshold.
- `effAtrStopMult`: market-specific ATR stop buffer.
- `effTrendAThreshold`, `effTrendBThreshold`, `effReversalThreshold`: market-specific grade thresholds.

Suggested defaults from the session:

- Crypto: CVD +0.5, A key distance >= 0.75 ATR, CVD key distance >= 0.55 ATR, VWAP extension 2.0 ATR, stop 1.8 ATR.
- Precious metals: keep CVD neutral, A key distance 0.60 ATR, VWAP extension 1.5 ATR, stop 1.5 ATR.
- Forex: lower CVD, A key distance 0.50 ATR, CVD key distance 0.35 ATR, VWAP extension 1.2 ATR, stop 1.2 ATR, A threshold 9.
- Stocks/indices: lower CVD, A key distance 0.55 ATR, CVD key distance 0.30 ATR, VWAP extension 1.4 ATR, stop 1.4 ATR.
- Futures: now inherits stock/index parameters (was previously unadapted — fell through to generic defaults).

## v8.1 Full A+ Multi-Market Upgrade (2026-06-24)

Four additional market-adaptive layers beyond the base parameter layer:

### Futures Parameter Inheritance
`marketFutures` was detected but had ZERO adaptation. Now added to the stock/index group in all 5 `eff*` branches.

### KillZone Market-Adaptive Times
| Market | London KZ | NY KZ |
|--------|-----------|-------|
| Crypto / Metals | 0700-0930 | 0820-1130 |
| Forex | 0700-0900 | 0820-1000 |
| Stock / Index / Futures | 0800-0930 | 0930-1030 |

```pine
string effKzLondonTime = MARKET_ADAPTIVE_ENGINE ? (marketCrypto or marketMetal ? "0700-0930" : marketForex ? "0700-0900" : "0800-0930") : KILLZONE_LONDON_TIME
```

### SVP Rows Per Market
Crypto needs finer VP buckets (≥70 rows), forex can use fewer (≥40).

```pine
int FINAL_ROWS = MARKET_ADAPTIVE_ENGINE ? (marketCrypto ? math.max(NUM_ROWS, 70) : marketForex ? math.max(NUM_ROWS, 40) : NUM_ROWS) : NUM_ROWS
```

**PITFALL**: `FINAL_ROWS` uses `marketCrypto`/`marketForex` — the market detection block MUST be declared before this assignment. Pine is single-pass sequential.

### ADX Thresholds Per Market
```pine
float effDmiAdxTrend = MARKET_ADAPTIVE_ENGINE ? (marketCrypto ? 25.0 : marketForex ? 18.0 : marketMetal ? 22.0 : DMI_ADX_TREND) : DMI_ADX_TREND
float effDmiAdxHot = MARKET_ADAPTIVE_ENGINE ? (marketCrypto ? 45.0 : marketForex ? 35.0 : marketMetal ? 42.0 : DMI_ADX_HOT) : DMI_ADX_HOT
```
All DMI usage (`dmiBalance`, `dmiHot`, `dmiBullPath`, `dmiBearPath`) must reference effective params.

### Complete Multi-Market Matrix
| Param | Crypto | Metals | Forex | Stock | Futures | Index |
|-------|--------|--------|-------|-------|---------|-------|
| CVD w | +0.5 | ±0 | -0.5 | -0.5 | -0.5 | ±0 |
| A-key ATR | ≥0.75 | 0.60 | 0.50 | 0.55 | 0.55 | 0.55 |
| CVD-key ATR | ≥0.55 | 0.45 | 0.35 | 0.30 | 0.30 | 0.45 |
| VWAP ext | 2.0 | 1.5 | 1.2 | 1.4 | 1.4 | 1.4 |
| Stop ATR | 1.8 | 1.5 | 1.2 | 1.4 | 1.4 | 1.4 |
| ADX trend | 25 | 22 | 18 | 20 | 20 | 20 |
| ADX hot | 45 | 42 | 35 | 40 | 40 | 40 |
| SVP rows | ≥70 | 50 | ≥40 | 50 | 50 | 50 |
| KZ Lon | 0700-0930 | 0700-0930 | 0700-0900 | 0800-0930 | 0800-0930 | 0800-0930 |
| KZ NY | 0820-1130 | 0820-1130 | 0820-1000 | 0930-1030 | 0930-1030 | 0930-1030 |
| A thr. | 8 | 8 | 9 | 8 | 8 | 8 |
| Rev thr. | 7 | 6 | 7 | 6 | 6 | 6 |

## Data Window Replay Fields

For no-table overlays, expose audit/replay fields with `display=display.data_window`:

- `Replay Side Code`: `1` long, `-1` short, `9` no-trade risk, `0` wait.
- `Replay Grade Code`: `3` A, `2` B, `1` C, `-1` X, `0` wait.
- `Replay Plan Price` and `Replay Invalid Price`.
- `Replay Stop Distance` and `Replay RR Unit`.
- `Location Score`, `Confirm Score`, `Extension Risk Score`.
- Effective parameters: CVD weight, VWAP extension ATR, ATR stop buffer.

These fields let the user export TradingView data and measure whether rule changes actually improve hit rate and drawdown.

## Companion Strategy Pattern

Create a separate `strategy()` version instead of replacing the live indicator:

- Keep the indicator version with `alertcondition()` for real-time alerts.
- Strategy version may comment out `alertcondition()` lines and use `strategy.entry/exit` alert messages instead.
- Add inputs:
  - `BACKTEST_ENABLE`
  - `BACKTEST_ENTRY_GRADE`: `A`, `A+B`, `A+B+C`
  - `BACKTEST_RR`
  - `BACKTEST_CLOSE_ON_X`
- Enter long/short from the stable grade booleans.
- Use invalid price if available; otherwise fall back to `close +/- ATR * effAtrStopMult`.
- Use fixed R target first; optimize after baseline OOS results exist.
- Close all on X/no-chase risk when enabled.

## Verification Checklist

Local text verification before delivery:

- No table residue: no `table.`, `table(`, or stale table input prefixes.
- Live indicator still has `indicator(` and keeps the expected `alertcondition()` count.
- Strategy companion has `strategy(`, `strategy.entry`, `strategy.exit`, and backtest inputs.
- Both files contain `MARKET_ADAPTIVE_ENGINE`, effective parameters, and Data Window replay fields.
- Remind the user final Pine syntax validation must happen in TradingView Pine Editor because there is no local TradingView compiler.
