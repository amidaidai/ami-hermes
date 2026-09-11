# Execution Closed-Loop & Governance Feedback (Phase 2 Pattern)

## Purpose
Achieve true execution closed-loop for the trading system: analysis/monitor → record trade/plan → review outcome → update risk_state + governance statistics (sample count, avg R, win rate) → model weight adjustment. Use sim trades to bootstrap samples safely. Automate daily validation + governance via maintenance script. This was the key advancement after hygiene P0s (XAU guard, prediction overfit, cron path).

## Core Scripts (canonical path — always exercise the CLIs)
- `scripts/成交记录.py`  
  Records open or plan execution. Updates `data/risk_state.json` (trades_count, unreviewed, last_unreviewed).  
  Usage: `python scripts/成交记录.py --symbol BTCUSDT --plan-id "BTCUSDT-20260620-sim1" [--note "..."]`

- `scripts/成交复盘.py`  
  Records review (real or sim). Updates risk_state (daily_realized_pnl, trades, sets unreviewed=0), appends to `trade_reviews.jsonl`.  
  Supports --dry-run for safe testing.  
  Usage: `python scripts/成交复盘.py --plan-id "..." --pnl 2.8 --r 0.9 --discipline "遵守" --mistake "无"`

- `scripts/策略治理.py` (enhanced in this phase)  
  Reads `trade_reviews.jsonl`, aggregates per-model: current_sample, avg_r, win_rate, etc.  
  Applies modest weight boost (≤1.5x) only if min_sample reached + positive expectancy.  
  Previously mostly static config dump. Now sample-driven.  
  Run: `python scripts/策略治理.py` → expect "策略治理 updated from reviews"

- `scripts/日间维护.py` (extended)  
  `run_day_trading_maintenance()` or `python scripts/日间维护.py day` runs: daily validation (backtest_runner), 策略治理 refresh, model stats update.  
  Integrates into no-agent cron for automation.

- Supporting: `scripts/backtest_runner.py`, `scripts/cvd_aggtrades.py`, `scripts/run_daily_validation.py`

## Recommended Workflow
1. Identify executable structure from monitor_levels.json or analysis card.
2. `成交记录.py` (use -simN plan-id for bootstrap) → risk_state.unreviewed increases.
3. Simulate or execute review.
4. `成交复盘.py` (dry-run first, then real) → risk_state updated + review logged.
5. `策略治理.py` → governance reflects new sample/avg_r.
6. Include in daily maintenance run for backtest + governance.
7. Verify CVD A-grade (BTC) or alternative for XAU is feeding scoring.

## Sim Trade Bootstrap
- Plan IDs containing "-sim" or "-simN" allow safe sample accumulation without real money risk.
- Example sequence in this session produced:
  - risk_state: trades=1, daily_realized_pnl=2.8, unreviewed=0
  - strategy_governance: current_sample=1, avg_r=0.9 for model (e.g. VWAP反抽)
- Target: ≥20 samples per model (real + sim) before weight adjustments become reliable. Governance policy min_sample ~20.
- Real trades use clean plan-ids; sims are for training the governance loop.

## CVD A-Grade Pipeline
- `cvd_aggtrades.py` → BTC produces usable A级 + direction for scoring/博弈段.
- XAUUSD → "非加密" (correct and expected; no Binance aggTrades. Use gold-api + jin10).
- Must be wired into scoring_engine / multi_model_engine for A-grade to affect cards and risk.

## Verification Bundle Extension (post closed-loop changes)
After editing record/review/governance/maintenance scripts, always execute:
1. `python scripts/成交记录.py --symbol BTCUSDT --plan-id "BTCUSDT-...-simN"`
2. Inspect: `cat data/risk_state.json` (unreviewed should increment)
3. `python scripts/成交复盘.py --plan-id "..." --pnl X.X --r X.X --discipline "遵守" --mistake "无"` (and --dry-run first)
4. Re-inspect risk_state: trades/pnl updated, unreviewed=0
5. `python scripts/策略治理.py` (confirm "updated from reviews" + sample fields populated)
6. `python scripts/run_daily_validation.py` or 日间维护 day (check data/validation/audit_summary_latest.json, strategy_governance)
7. Regenerate cards: `python scripts/auto_card.py BTCUSDT && python scripts/auto_card.py XAUUSD`
8. `grep -E "setup_id|model_id|entry_tag|exit_tag" data/auto_card_*.md` → 0 leaks
9. `python -m pytest -q` (target 98+ passed)
10. `git status --short` → add + commit + push (棠溪 "锁定" definition)
11. Optional: cvd_aggtrades test + backtest_runner smoke

Only claim "closed-loop working" after real tool outputs match expectations.

## Integration with Daily Automation
- Add no-agent cron calling `python 日间维护.py day` (e.g. 08:30 or 09:00 in active window).
- This runs validation + governance refresh automatically.
- Complements 5m "持仓与信号" cron.

## Pitfalls Specific to This Pattern
- Governance stats start at sample=0/1 and are meaningless for weight changes — always bootstrap with multiple sim reviews first. Never tune live weights on <20 samples.
- Bypassing the CLIs (direct JSON edits to risk_state or reviews) defeats the purpose — the loop must exercise 成交记录/复盘 code paths.
- After any patch to these scripts, re-run the full record→review→governance chain with actual tool calls (not just "it should work").
- XAU vs BTC asymmetry: CVD/orderflow data sources differ; guards in price bridge must stay absolute.
- "一起修复了" or "继续推进" requests still mean: identify all related P0/P1 (hygiene + loop), batch implement, run complete verification bundle (including sim flow), git lock, report real outputs.
- Prediction overfit fix (0.5% threshold + low-conf exclusion + log clear) must stay paired with closed-loop to keep review labels honest.
- Backtest numbers (e.g. 50.3% win, PF 2.71) are directional only; do not use raw for position sizing.

## Evidence from 2026-06-20 Phase2 Advance
- risk_state after sim flow: trades=1, daily_realized_pnl=2.8, unreviewed=0
- 策略治理 output: "策略治理 updated from reviews"
- strategy_governance sample fields populated (current_sample=1, avg_r=0.9)
- backtest_runner summary: 167 trades, win_rate 50.3%, profit_factor 2.71, total_r 142.25, max_drawdown_r 3.0
- pytest: 98 passed
- auto_card regeneration: 0 machine field leaks
- git: phase2 commit (e.g. 428c0e3) + clean working tree after push
- CVD: BTC A级 confirmed; XAU 非加密 (correct)
- All changes committed with explicit verification bundle execution.

## Future Extensions
- Wire real/sim order execution (binance-trading MCP dry-run first).
- Add regime_classifier / walk-forward into daily maintenance.
- Increase sample rate with more sims or live reviews.
- Dashboard exposure of governance stats (current samples per model).

This pattern, combined with the hygiene fixes and verification bundle iron law, enables production-grade closed-loop operation for the 棠溪 trading system.

Cross-reference: trading-system-audit SKILL.md (verification bundle, "一起修复了" batch mode, XAU guards, cron path lessons). See also trade_reviews.jsonl, risk_state.json, strategy_governance.json, and the scripts themselves for current implementation.