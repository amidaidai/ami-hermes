# 2026-06-21 Live Audit Evidence (trading-system-audit run)

## Confirmed Healthy State
- Exactly 3 no-agent crons active and last_run=ok:
  - 持仓与信号: */5 8-23 * * * (wrapper serial 持仓监测 + 信号巡检)
  - 清理守护: 0 12 * * *
  - 日间维护: 30 8 * * *
- hermes cron list matches target; jobs.json stale/empty (normal).
- Git clean (status --porcelain = 0 changes).
- Snapshots: BTC quality=A (88, multi-source), XAU quality=A- (88, 金十+gold-api spot consistent, Yahoo futures as basis only).
- monitor_levels.json: BTC 2 levels + XAU 4 levels, updated ~23:55, monitor_enabled=true.
- Recent structure refreshes: "同轮多关键位触发" for both symbols.
- Telegram pushes succeeding on 385 (XAU) / 386 (BTC); recent monitor.log tail shows only direct success.

## Template & Card Compliance (this run)
- 0 machine-field leaks (grep setup_id/model_id/entry_tag/exit_tag/critical/warning/info on auto_card_*.md = 0). Good.
- BTC card: per-line 5m/15m/1h/4h cycles present, but **bold** still appears in header fields.
- XAU card: compacted cycle line (not strict per-line), **bold** present, higher TFs showed "当前无数据".
- Master template v6.9.4 loaded first per iron law.
- Monitor-template short format used for alerts (品种→周期→现价→状态→模型→触发位→关键位→订单流→风控→中文动作).

## Watchdog & Stability Observations
- watchdog.log showed repeated "重启速率限制[真崩溃]：4次/小时已达上限 · 冷却3599s" and "卡死/环境未就绪：2次/小时".
- Multiple restarts in 22:08–22:20 window.
- Heartbeat PID 22772 was live at audit time; tasklist showed multiple python.exe (normal).
- Lesson: repeated rate-limit entries often indicate main-loop blocking (serial requests in 行情守望) rather than outright crash. Check monitor.log for long-running network/push before assuming dead process.

## XAU Price Path Hygiene
- get_price() and system_data_bridge have strong early guards: `if "XAU" in symu or not symu.endswith("USDT")`.
- Despite guards, monitor.log still contained kline 400s for XAUUSD (5m/15m at 10:27 and price errors at 21:xx).
- Root: indicator_feed.py and other collectors still reach Binance for XAU (uses "yahoo_gc_proxy" in some places but kline calls leak).
- Verification command that must pass: `python -c "from scripts.行情守望 import get_price; print(repr(get_price('XAUUSD')))"` → None (no 400).

## Other Live Signals
- Prediction tracker: 0 verified samples currently.
- Discord remnants only in old log lines (no recent attempts in tail).
- 行情守望 v7.1 features active (Session+Retry, tiered scores warning=75>critical=70, XAU session_filter, alert budgets).
- auto_card.py (hermes/scripts/ main impl) + root wrapper present.

## Verification Bundle Executed in This Session
- read_file master-template-v68.md (done)
- Card regen test (dry import + existence checks)
- 0 leaks confirmed
- hermes cron list + last_status
- Heartbeat fresh + tasklist cross-check
- Snapshots A/A-
- Git clean
- Recent log tail (pushes + structure updates)

## Actionable for Next Audit
- Always chase XAU kline/collector paths in addition to get_price().
- Explicitly check for ** in rendered cards + cycle line format against template.
- When watchdog.log shows rate limits, treat as "investigate blocking" not just "process died".
- Confirm exactly 3 crons; any extra = drift.

Add to future bundles: explicit kline guard test for XAU + card ** + per-line grep.