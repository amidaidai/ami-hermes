# Backtest reliability and pytest conflict audit notes — 2026-06-18

## Why this matters

During a deep audit, two backtest entry paths using the same `data/btc_klines_30d_merged.json` produced radically different conclusions. Treat this as a class-level reliability warning: before trusting model win rates or walk-forward output, verify that the backtest engine is internally consistent and that test collection is clean.

## Symptom 1: same data, incompatible backtest results

Observed pattern:

- `backtest_from_klines('BTCUSDT', rows, cfg=cfg)` produced hundreds of trades and very high aggregate R / profit factor.
- Direct `run_backtest(...)` with only OHLCV produced only a few trades and negative result.

Likely explanation:

- `backtest_from_klines()` injects futures-derived arrays such as taker buy/sell volumes, long-short ratios, global long-short, taker ratios, and OI.
- Direct `run_backtest()` without those arrays runs only the base model subset.

Audit rule:

- Do not compare these as if they are the same strategy.
- Report separate buckets: base OHLCV models, futures-enriched engines, and combined output.
- If a combined output is used, list exactly which auxiliary arrays were present.

## Symptom 2: inflated R / unrealistic RR

Red flags observed:

- Individual trades with `rr_ratio` in the hundreds, e.g. `450+`.
- Very high aggregate R and profit factor from a short sample.
- Trades where price movement appears favorable for the side but `result` is `loss` or `pnl_r` has the opposite sign.

Required sanity constraints before trusting stats:

1. Minimum stop distance:
   - `abs(entry - stop) >= max(0.5 * ATR, price * 0.001)` or another explicitly justified floor.
2. Maximum RR cap / anomaly quarantine:
   - `rr_ratio > 10` should be excluded, flagged, or require explicit justification.
3. Directional PnL assertion:
   - For long wins, `exit > entry` should correspond to positive PnL.
   - For short wins, `exit < entry` should correspond to positive PnL.
   - Mismatch = raise or mark invalid, never silently aggregate.
4. Same-bar TP/SL ambiguity:
   - If a bar touches both stop and target, use a conservative rule such as stop-first unless lower-timeframe data resolves ordering.
5. Cost and slippage floor:
   - Ensure fees/slippage are applied before aggregating R and profit factor.

## Walk-forward caveat

Walk-forward is only as credible as the backtest function it calls. If the base backtest has RR or result-sign bugs, walk-forward output is not a validation; it only repeats the same bug across folds.

## Pytest collection conflict

Observed conflict:

- `scripts/test_core.py`
- `tests/test_core.py`

Running both can trigger `import file mismatch` because pytest imports both as `test_core`.

Audit rule:

- Full project verification must run from repo root with `python -m pytest -q`.
- If import mismatch occurs, classify as at least P1 because CI/regression coverage is not trustworthy.

Preferred fix:

- Keep tests under `tests/`.
- Rename or move script-local smoke tests, e.g. `scripts/test_core.py` → `scripts/runtime_core_smoke.py` or migrate into `tests/test_runtime_core.py`.

## Reporting language

When these red flags appear, avoid saying “回测很好” or “模型有效”. Use:

- “回测引擎可运行，但统计可信度未通过审计。”
- “当前 win rate / total R 只能作为调试信号，不能用于模型升权。”
- “先修成交判定和测试收集，再谈参数优化。”
