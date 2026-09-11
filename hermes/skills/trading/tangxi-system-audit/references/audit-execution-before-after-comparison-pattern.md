# Audit Execution: Before/After Comparison Pattern (2026-06-30 session)

## Trigger
User says "执行" after receiving audit suggestions, or explicitly "再跑一次...对比前后" / "run the check again for before/after".

## Core Pattern (iron law for closure)
1. Capture BEFORE baseline (real terminal output, no assumption):
   - `hermes doctor`
   - `hermes status --all`
   - `git status --short --branch`
   - `ls -lt data/source_snapshot*.json data/tv_live.json data/tv_dmi_cache.json data/protections_state.json data/.btc_daemon_heartbeat.json data/monitor_heartbeat.json`
   - Heartbeat cats + key timestamps

2. Execute fixes (batch, not piecemeal):
   - Data refresh: `python scripts/data_freshness_watchdog.py`, `macro_poly_refresh.py`, `黄金宏观.py`, dune/deribit collectors
   - `hermes doctor --fix`
   - Git: `git add -A [target dirs/files]`; `git commit -m "audit: batch sync ... (pre/post comparison)"`

3. Re-run verification bundle (real execution, capture output):
   - `python scripts/pine_static_scan.py ...`
   - `python scripts/pipeline_router.py BTCUSDT XAUUSD` (confirm routing)
   - `timeout 60 python scripts/auto_card.py BTCUSDT` (or 90s for full; check tables, GO/NO-GO gates, exit_code)
   - Re-capture AFTER timestamps, heartbeats, git status

4. Report deltas only (structured, evidence-backed):
   - BEFORE vs AFTER tables or vertical lists
   - Highlight what moved (config version, git clean, fresh caches, verified pipeline output)
   - Remaining P1s with commands

## Evidence from session
- BEFORE: v31, dirty git (7M+2??), snapshots 6/29, tv_dmi 15:10
- Fixes executed: refreshes produced Dune net outflow + Deribit C/P, doctor --fix → v32, commit 179436f
- AFTER: v32, git committed, tv_dmi 15:15, heartbeats 15:17, router+auto_card produced real gates (R:R 1:1.1, data freshness A, protections pass)
- Auto_card smoke captured full table output (not description)

## Pitfalls
- Do not describe what "you would do" — run the commands and paste real stdout.
- Source snapshots/protections may lag short runs; note as remaining P1 and re-trigger full gatherer if needed.
- Always use timeout on auto_card (≥60s) to see gates.
- Commit message must reference "pre/post comparison" for traceability.

## Related
See main SKILL.md Step 6 (实测管线) and Step 7 (cron) for base. Extend verification bundle with this pattern for any "执行" request after audit.