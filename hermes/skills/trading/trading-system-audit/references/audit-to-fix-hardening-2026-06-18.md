# Audit-to-Fix Hardening Pattern — 2026-06-18

Use this reference when a trading-system audit turns into implementation work, especially after findings around XAU data quality, backtest credibility, pytest drift, cron validation, and monitor restart verification.

## Durable lessons

### 1. Do not stop at reporting P0/P1 findings

When the user says `全部做`, `全部最优解`, `全部修复`, or equivalent, treat the audit report as an implementation plan:

1. Add protective tests for the exact failure modes before changing code.
2. Patch source code.
3. Run syntax/import checks.
4. Run targeted tests.
5. Run full pytest.
6. Run the actual daily validation/backtest pipeline.
7. Restart the live monitor if touched code is process-resident.
8. Verify logs/heartbeat prove the running process uses the new code.

### 2. Backtest credibility needs hard runtime guards, not just interpretation warnings

Minimum safeguards to enforce in or near `backtest_runner.py`:

- Minimum stop distance: use `max(0.5 * ATR, price * 0.001)` or a strategy-specific equivalent.
- Cap unrealistic reward/risk: reject or clip setups with `R:R > 10` unless explicitly justified.
- Validate result consistency:
  - long: positive R must not be marked as loss
  - short: positive R must not be marked as loss
  - negative R must not be marked as win
- Same-bar TP/SL ambiguity must not assume the favorable side. Prefer conservative stop-first or explicit intrabar policy.
- Store sanity summary with `trade_count`, `win_rate`, `total_r`, `profit_factor`, `max_drawdown_r`, and `max_rr`.

### 3. XAU data quality must separate spot consensus from futures basis

For XAUUSD, evaluate spot sources separately from Yahoo futures proxies:

- Spot consensus: `金十`, `gold-api.com`, `OANDA` when available.
- Futures context: `GC=F`, `MGC=F` as basis/context only.
- Without OANDA, do not label as clean `A92` just because 金十 and gold-api agree; cap around `A- 88` unless another true spot source confirms.
- Keep metrics explicit:
  - `spot_spread_pct`
  - `futures_basis_pct`
  - `source_spread_pct`

### 4. Source spread is never volatility

Protect against this exact bug with a test:

- Input snapshot has only `price_spread_pct`.
- Expected volatility extractor returns `0` or unavailable.
- A real `volatility_24h_pct: 1.25` should normalize to decimal `0.0125`.

Never pass `price_spread_pct` to `check_constitution(..., volatility_24h_pct=...)`.

### 5. pytest drift is itself an audit finding

Common fix pattern:

- Rename runtime smoke files under `scripts/` away from `test_*.py`, e.g. `runtime_core_checks.py`.
- Add `pytest.ini` with `testpaths = tests`.
- Exclude unrelated directories such as `sandbox`, `data`, `outputs`, `hermes`, `.git`, and `__pycache__`.
- Full validation is only acceptable after `python -m pytest -q` passes.

### 6. Daily validation should usually be a no-agent cron

For deterministic checks, prefer zero-token `no_agent` cron:

- Main script in repo, e.g. `scripts/run_daily_validation.py`.
- Thin wrapper under Hermes scripts directory that calls the repo script.
- Output timestamped JSON artifacts under `data/validation/` plus `audit_summary_latest.json`.
- Include backtest, walk-forward, model coverage, and sanity constraints.

### 7. Process-resident fixes require live verification

After patching `行情守望.py`, `trading_system.py`, `backtest_runner.py`, or monitor-adjacent modules:

1. Compile files.
2. Restart or force watchdog restart.
3. Confirm heartbeat PID/time changed or was refreshed.
4. Scan `data/monitor.log` for disappearance of old error patterns.
5. Run a real entry point such as `python scripts/auto_card.py BTCUSDT` if the pipeline is affected.

If watchdog does not restart a killed monitor, record it as a separate watchdog-chain risk rather than assuming code fixes are live.
