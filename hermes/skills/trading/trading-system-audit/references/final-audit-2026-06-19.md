# 2026-06-19 Final System Audit Notes

Purpose: durable audit/runbook detail from the final full-system check after v6.9 community fusion and monitor recovery.

## Card header formatting correction

User corrected the analysis card header order and legibility:

1. 品种 first
2. 时间 second
3. 周期 third
4. Periods should display high → low to visually encode the top-down workflow:
   - 4h 背景偏向
   - 1h 趋势继承
   - 15m 执行结构
   - 5m 触发确认

Recommended header shape:

```text
**① 品种：BTCUSDT.P:BINANCE**
**◷ 时间：YYYY-MM-DD HH:MM CST**
**② 周期：**（高周期定方向 → 低周期找入场）
**4h ...** — 背景偏向
**1h ...** — 趋势继承
**15m ...** — 执行结构
**5m ...** — 触发确认
```

This is not merely cosmetic: it matches the community/top-down principle: higher timeframe defines direction/location, lower timeframe defines tactical entry/stop.

## Full audit status interpretation

When the user asks “现在什么情况 / 全方位检查”, report status in this order:

1. P0 headline: alive/dead, not a long preamble.
2. Monitor heartbeat age, pid, symbol rotation.
3. Binance account/positions/open orders.
4. TradingView CDP/chart status.
5. Cron statuses, explicitly distinguishing old `last_run` errors from manually verified fixed wrappers.
6. Data snapshots for BTC and XAU, including freshness and quality.
7. Test result.
8. Risk gate state and whether old plans are blocked.
9. Git hygiene only after runtime health.

## XAU snapshot freshness pitfall

`gold_monitor.py` can be healthy and still leave `data/source_snapshot_XAUUSD.json` stale if it only refreshes `xau_macro_context.json`. This makes audits or analysis cards read old XAU quality even while the gold monitor itself is producing fresh prices.

Fix pattern:

- Add a quiet `refresh_xau_snapshot()` in `gold_monitor.py` that imports `trading_system` and calls `source_snapshot('XAUUSD')` after price resolution, before early return on non-trigger.
- Failure should be logged as `snapshot_refresh_error` but must not break no-agent monitor output.
- Verify by comparing mtime/time fields of:
  - `data/source_snapshot_XAUUSD.json`
  - `data/xau_macro_context.json`
- Manual refresh command:

```bash
cd "/d/Hermes agent"
"$LOCALAPPDATA/hermes/hermes-agent/venv/Scripts/python.exe" scripts/trading_system.py snapshot --symbol XAUUSD
```

Expected healthy XAU snapshot fields:

```text
symbol=XAUUSD
quality=A- or A
confidence≈88
confidence_label mentions 金十+gold-api双源一致; Yahoo futures/basis only reference
```

## Watchdog log interpretation pitfall

If heartbeat is fresh (<30s), `status=running`, and push logs are succeeding, do not over-prioritize older watchdog `重启速率限制` lines. They can be stale noise from previous restart loops. Check `data/watchdog_guard.json` current buckets and heartbeat age before declaring a new P0.

## Cron daily validation display pitfall

After fixing the no-agent wrapper, `hermes cron list` may still display the old `Last run ... error` until the next scheduled run. Manually verify by running the wrapper with the desktop-runtime Python and checking `data/validation/` new artifacts:

```bash
"C:/Users/Administrator/.hermes-web-ui/desktop-runtime/hermes/0.16.0/win-x64/python/python.exe" \
  "C:/Users/Administrator/AppData/Local/hermes/scripts/run_daily_validation.py"
ls -lt data/validation | head
```

Healthy output: exit code 0 and new `backtest_*`, `walk_forward_*`, `model_coverage_*`, `audit_summary_latest.json`.

## Risk-gate interpretation

If trade events show `risk_gate.allowed=false` with reason like `单笔风险 4.4% > 3% 上限`, this is a healthy protection, not a runtime failure. Tell the user old plans must not be executed directly; refresh card/structure and recalculate sizing under current equity.
