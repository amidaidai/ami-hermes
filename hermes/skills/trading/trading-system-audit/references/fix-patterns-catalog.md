# Fix Patterns Catalog

Reusable fix patterns discovered during trading system audits.
Each pattern: symptom → root cause → fix → verification → source.

---

## 1. Heartbeat-at-Top-of-Loop

**Symptom**: watchdog.log shows "心跳停滞 Ns·PID存活=True" with N in 90-200s range.
Process is alive but heartbeat is stale because serial network requests accumulate.

**Root Cause**: `write_heartbeat()` called at END of `while True` loop. If any
`requests.get()` or `subprocess.run()` blocks for >90s, heartbeat expires before
the next write.

**Fix**: Move `write_heartbeat("running")` to the TOP of the loop (first statement
inside `while True`). Reduce network timeouts to 5-10s max.

**Verification**: After restart, check `data/monitor_heartbeat.json` — `age` should
be <10s consistently across multiple checks.

**Source**: 2026-06-18 audit P0-1 fix.

---

## 2. numpy Vectorization for Indicator Calculations

**Symptom**: Backtest runner slow on >2000 candles. Python loops for EMA/ATR/VWAP.

**Root Cause**: `calc_atr()`, `calc_vwap()`, `calc_vwap_bands()`, `rolling_window()`
implemented with Python for-loops and list appends.

**Fix**: Replace with numpy vectorized operations:
- `TR`: `np.maximum(high - low, np.maximum(abs(high - prev_close), abs(low - prev_close)))`
- `ATR`: `np.convolve(tr, np.ones(n)/n, mode='valid')` or `pd.Series(tr).rolling(n).mean()`
- `VWAP`: `np.cumsum(tp * vol) / np.cumsum(vol)` where `tp = (high + low + close) / 3`
- `VWAP bands`: `vwap ± band_mult * np.sqrt(...)`
- EMA: must retain Python loop (recursive dependency: `ema[i] = alpha * close[i] + (1-alpha) * ema[i-1]`)

**Pitfall**: EMA cannot be fully vectorized due to recursive dependency.
Only the non-recursive indicators (ATR/TR/VWAP/bands) can use numpy.

**Verification**: Run `python -c "from backtest_runner import calc_atr; print(calc_atr(...))"`
and compare output before/after vectorization.

**Source**: 2026-06-18 audit P1-1 fix. Pattern borrowed from Freqtrade's vectorized
indicator calculations using pandas `.loc` operations.

---

## 3. Crash-Only / Fail-Fast Data Validation

**Symptom**: NaN or inf prices silently propagate through scoring engine, producing
garbage confidence scores or crashing downstream modules.

**Root Cause**: No input validation on price data before processing. A single corrupt
snapshot (null price, zero volume, inf from division) cascades through the pipeline.

**Fix**: Add Fail-Fast validation at the entry point of `process_block()`:
```python
import math
def validate_price_data(price, volume=None):
    if price is None or math.isnan(price) or math.isinf(price) or price <= 0:
        raise ValueError(f"Invalid price: {price}")
    if volume is not None and (math.isnan(volume) or math.isinf(volume) or volume < 0):
        raise ValueError(f"Invalid volume: {volume}")
```
Call before any scoring/model logic. Let the exception propagate — the watchdog
will restart the process. Corrupt data is worse than no data.

**Philosophy**: Borrowed from NautilusTrader's Crash-Only design — prefer crashing
and restarting over silently processing corrupt data.

**Verification**: Inject `float('nan')` into a test price feed, confirm process
exits with ValueError (not silent garbage output).

**Source**: 2026-06-18 audit P2-3 fix.

---

## 4. Meta-Labeling Execution Gate

**Symptom**: All model signals execute at full confidence regardless of data quality,
recent performance, or market conditions.

**Root Cause**: No secondary classifier to gate primary signals. Every signal that
passes the model checklist is treated equally.

**Fix**: Create a Meta-Labeler module (`scripts/meta_labeler.py`) that acts as a
secondary execution gate:
- Features: model score, data quality grade, consecutive losses, CVD alignment, session
- Primary: heuristic rules (score≥70 + data A/B + no consecutive losses → pass)
- Secondary: logistic regression on historical trade outcomes (when ≥16 samples)
- Fallback: pure rule-based when insufficient training data
- Output: `{label: 0/1, confidence: 0-100}` — only execute when label=1

**Pitfall**: With <16 trades, logistic regression is unreliable. Always fall back
to heuristic rules until enough data accumulates. Future upgrade: XGBoost at 100+ trades.

**Verification**: Test with high-score + A-grade data → label=1, conf≥80%.
Test with low-score + C-grade data → label=0, conf<50%.

**Source**: 2026-06-18 audit P2-1 fix. Pattern from López de Prado "Advances in
Financial Machine Learning" Meta-Labeling concept.

---

## 5. Configurable Drawdown Circuit Breaker

**Symptom**: Hard-coded daily drawdown limit (5%) too aggressive for small capital
($67). Single bad day can wipe 5% of an already small account.

**Root Cause**: `risk_constitution.py` CONSTITUTION dict has fixed
`DAILY_DRAWDOWN_LIMIT_PCT = 5.0`.

**Fix**: Add `DRAWDOWN_MODE` config with two presets:
- `conservative`: 2% daily drawdown limit (Reddit r/algotrading consensus for small accounts)
- `aggressive`: 5% daily drawdown limit (original, for larger capital or high-conviction periods)
- Default: `conservative` when account balance < $500
- Mode is selectable at runtime, not hardcoded

**Verification**: Set mode=conservative, simulate 2.5% drawdown → circuit breaker fires.
Set mode=aggressive, same drawdown → normal operation continues.

**Source**: 2026-06-18 audit P2-8 fix. Reddit r/algotrading consensus: 2% daily
drawdown is the community standard for accounts under $1000.

---

## 6. broad except → Specific Exception Types

**Symptom**: `except Exception` catches everything including programming errors
(TypeError, AttributeError) that should crash loudly, masking real bugs.

**Root Cause**: Lazy error handling — broad except used as a catch-all for "something
might go wrong" without distinguishing expected failures from programming bugs.

**Fix**: Replace with specific exception types:
- Network: `requests.Timeout`, `requests.ConnectionError`, `requests.HTTPError`
- Parsing: `json.JSONDecodeError`, `ValueError`, `KeyError`
- File: `OSError`, `PermissionError`, `FileNotFoundError`
- Keep broad `except Exception` ONLY for: import failures (`ImportError`),
  `__import__` dynamic loading, `hasattr`/`getattr` reflection — where any exception
  type is expected and degradation is the correct response

**Rule of thumb**: If the except block logs and continues → use specific types.
If the except block degrades to a fallback → broad is acceptable.

**Verification**: After replacement, grep for remaining `except Exception` and
justify each one with a comment explaining why broad catch is intentional.

**Source**: 2026-06-18 audit P1-2 fix. 16/21 broad excepts replaced with specific types.

---

## 7. profit_factor = null (not 999) for Zero Trades

**Symptom**: `equity_curve.json` shows `profit_factor: 999` when there are 0 trades,
which pollutes dashboard displays and statistical aggregations.

**Root Cause**: Division by zero guard returns 999 as a "sentinel" value, but 999
is a valid profit factor for extremely profitable strategies — it's not distinguishable
from the error case.

**Fix**: Return `null` (Python `None`) when trade count is 0. Dashboard and
aggregation code should handle null explicitly (display "N/A", skip in averages).

**Verification**: `json.load(equity_curve.json)` with 0 trades → `profit_factor` is `null`.
With >0 trades → `profit_factor` is a float.

**Source**: 2026-06-18 audit P2-10 fix.

---

## 8. Unified Logging with Rotation

**Symptom**: Each script uses `print()` or ad-hoc `logging.basicConfig()`. Logs grow
unbounded, no rotation, inconsistent formats across modules.

**Root Cause**: No shared logging infrastructure. Each script reinvents logging.

**Fix**: Create `scripts/logger.py`:
- `RotatingFileHandler`: 5MB per file, 3 backup files
- Unified format: `[YYYY-MM-DD HH:MM:SS] [LEVEL] [module] message`
- Module-level `get_logger(name)` function
- Log directory: `data/logs/`
- Each script: `from logger import get_logger; log = get_logger(__name__)`

**Verification**: Write 1000 log lines, confirm rotation creates backup files.
Check format consistency across modules.

**Source**: 2026-06-18 audit P1-3 fix. Pattern from Freqtrade's unified logging.

---

## 9. Test Coverage for Core Modules

**Symptom**: Zero pytest tests. Every code change is a blind modification with no
regression protection.

**Root Cause**: No test infrastructure. Memory may claim "31 tests" but those are
from sandbox/ projects (feedgrab, feishu-streaming-card), not the trading system.

**Fix**: Create `tests/test_core.py` covering:
- `scoring_engine`: score calculation, weight distribution, edge cases
- `risk_constitution`: Kelly sizing, circuit breaker triggers, mode switching
- `hard_stop`: stop-loss calculation, execution logging, custom_data persistence
- `multi_model_engine`: model triggering, event_ban, confidence aggregation
- `push_allowed`: threshold logic, tier-based filtering, data quality gates

**Pitfall**: sandbox/ test files are from OTHER projects. Always verify:
```bash
find scripts/ tests/ -name "test_*.py" 2>/dev/null  # excludes sandbox/
```

**Verification**: `python -m pytest tests/test_core.py -v` → 30/30 passed in <1s.

**Source**: 2026-06-18 audit P0-2 fix. First real test coverage for the trading system.
