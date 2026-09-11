# Community Recommendations · 2026-06-18 (Updated 16:45)

Aggregated from X/Twitter, Reddit r/algotrading, GitHub, Freqtrade, QuantConnect, NautilusTrader.

## P0 · Implemented This Session

| Source | Recommendation | Implementation |
|--------|---------------|----------------|
| Reddit r/algotrading | Walk-forward validation = gold standard | scripts/walk_forward.py |
| Reddit consensus | 95% of retail algos fail from overfitting | check_overfit() + max_params_per_model=3 |
| X/Twitter ICT community | BTC=15m, XAU=5m — don't mix timeframes | enforce_timeframe() |
| Freqtrade Hyperopt | Bayesian optimization replaces grid search | scripts/bayesian_optimizer.py |
| Freqtrade docs | startup_candle_count=400 for EMA100 stability | BTConfig.startup_candle_count |
| **NEW** Freqtrade docs | Vectorized operations (pandas/numpy, not Python loops) | backtest_runner.py v1.2 numpy向量化 |
| **NEW** NautilusTrader | Crash-Only + Fail-Fast data integrity | 行情守望.py NaN/inf检测 + 具体异常 |
| **NEW** Reddit consensus | 2% max daily drawdown hard stop (conservative mode) | risk_constitution.py DRAWDOWN_MODE |
| **NEW** Reddit | Meta-Labeling: main model→direction, auxiliary→execution | scripts/meta_labeler.py |

## P1 · Implemented This Session

| Source | Recommendation | Implementation |
|--------|---------------|----------------|
| **NEW** Freqtrade docs | df.shift() instead of iloc[-1] (防repainting) | 验证通过 — 无iloc[-1]无未来引用 |
| **NEW** Freqtrade strategy-advanced | trade custom_data persistent storage | hard_stop.py log_execution custom_data字段 |
| **NEW** NautilusTrader | Structured logging + RotatingFileHandler | scripts/logger.py |
| **NEW** Community consensus | broad except → specific exception types | 行情守望.py 16/21处替换 |

## P1 · Implemented (Session 2 — 社区建议落地)

| Source | Recommendation | Implementation |
|--------|---------------|----------------|
| Bookmap | **CVD divergence detection** (price new high + CVD new low = reversal) | `scripts/cvd_analyzer.py` — 看涨/看跌背离检测 |
| Bookmap | **CVD exhaustion** (CVD surges but price stalls = running out of fuel) | `scripts/cvd_analyzer.py` — 买方/卖方耗尽检测 |
| Bookmap | **CVD absorption** (CVD drops but price holds = passive buyers absorbing) | `scripts/cvd_analyzer.py` — 看涨/看跌吸收检测 |
| Bookmap | CVD + VWAP confluence (combined confirmation) | `scripts/cvd_analyzer.py` — `check_cvd_confluence()` |
| 3Commas | Volatility Targeting (adjust position by asset volatility) | `risk_constitution.py` — `volatility_target_multiplier()` |
| 3Commas | Max 10 trades/day + cooldown timer | `risk_constitution.py` — 检查10+11 in `check_constitution()` |
| 3Commas | Real-time volatility filter (CVI / BB width) | `risk_constitution.py` — `real_time_volatility_filter()` |

## P1 · Still Pending

| Source | Recommendation | Status | Priority |
|--------|---------------|--------|----------|
| X/Twitter | Kill Zone entry precision is 2.5x normal hours | Session filter created, not yet verified with stats | Medium |
| ICT Guide | DST handling in session_filter | Needs verification | Low |
| ICT Guide | London Close Kill Zone reversal session | Needs verification | Low |

## P2 · Future

| Source | Recommendation | Status |
|--------|---------------|--------|
| VectorBT | 10k trades < 1 second (vectorized) | Backtest still uses Python loop for trade state machine |
| QuantConnect/LEAN | Event-driven engine architecture | Reference only |
| Reddit | Meta-Labeling v2.0: sklearn LogisticRegression | v1.0 heuristic rules implemented |

## GitHub Borrow Workflow

1. Search GitHub API: `curl -s "api.github.com/search/repositories?q=..."`
2. Identify borrowable modules (not whole projects)
3. Clone to sandbox/: `git clone <url> sandbox/<name>`
4. Extract specific functions/classes
5. Credit source in docstring
6. Adapt to 棇溪's data format and pipeline
7. Run tests to verify integration

### Borrowed This Session

| From | What | Integrated To |
|------|------|---------------|
| aurumcrypto | BTConfig cost model (fee_bps + max_hold) | backtest_runner.py v1.1 |
| aurumcrypto | Realistic PnL: net = gross - fee_cost | backtest_runner.py |
| BAKOME Gold Scalper | Session filter (London/NY Kill Zones) | scripts/session_filter.py |
| **NEW** NautilusTrader | Crash-Only + Fail-Fast design | 行情守望.py P2-3 |
| **NEW** Freqtrade | Vectorized indicator calculation | backtest_runner.py v1.2 |
| **NEW** Freqtrade | custom_data persistent storage | hard_stop.py P2-5 |
| **NEW** Freqtrade | RotatingFileHandler logging | scripts/logger.py |
| **NEW** Reddit | Meta-Labeling execution gatekeeping | scripts/meta_labeler.py |

## 新发现社区建议 (2026-06-18 16:50 补充调研)

### 来源: 3Commas AI Trading Bot Risk Management 2025 Guide

| 建议 | 棠溪现状 | 差距 |
|------|----------|------|
| Drawdown limits (绝对10%/相对5%) | ✅ 已有 P2-8可配置2%/5% | 无 |
| ATR-based stop-loss | ✅ 已有 MIN_STOP_ATR_RATIO=0.5 | 无 |
| Kelly Criterion position sizing | ✅ 已有 kelly_position_size | 无 |
| **Volatility Targeting** (按波动率调仓位) | ✅ 已实现 `volatility_target_multiplier()` | 无 |
| 杠杆cap 2-3x for volatile assets | ⚠️ 棠溪用100x(BTC/ETH) | 高风险·社区建议远低于此 |
| **Max 10 trades/day + cooldown** | ✅ 已实现 检查10+11 in `check_constitution()` | 无 |
| Pause after 3-4 consecutive stop-losses | ✅ 已有 MAX_CONSECUTIVE_LOSSES=3 | 无 |
| **Real-time volatility filter** (CVI/BB width) | ✅ 已实现 `real_time_volatility_filter()` | 无 |
| Block entries during macroeconomic reports | ⚠️ 有news_block但未验证 | 需验证 |

### 来源: Bookmap CVD Trading Strategy

| 建议 | 棠溪现状 | 差距 |
|------|----------|------|
| CVD divergence (价格新高+CVD新低=反转) | ✅ 已实现 `CVDAnalyzer._check_divergence()` | 无 |
| CVD + VWAP confluence | ✅ 已实现 `check_cvd_confluence()` | 无 |
| **CVD exhaustion** (CVD激增但价格停滞) | ✅ 已实现 `CVDAnalyzer._check_exhaustion()` | 无 |
| **CVD absorption** (CVD降但价格持稳) | ✅ 已实现 `CVDAnalyzer._check_absorption()` | 无 |
| "CVD是确认层不是独立信号" | ✅ 符合棠溪使用方式 | 无 |

### 来源: ICT Kill Zones Complete Guide 2025

| 建议 | 棠溪现状 | 差距 |
|------|----------|------|
| 4个Kill Zone时段 | ✅ 已有session_filter | 无 |
| **DST夏令时处理** | ❓ 需验证session_filter是否处理DST | 需检查 |
| London KZ 2-5AM EST = 突破最佳 | ✅ 已有 | 无 |
| NY KZ 8-11AM EST = 重叠+数据发布 | ✅ 已有 | 无 |
| London Close = 反转时段 | ❓ 需验证是否覆盖 | 需检查 |
