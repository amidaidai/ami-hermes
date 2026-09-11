# Audit Closure: Runtime Sync and Green-State Verification (2026-06-19)

This reference captures the reusable closure pattern from a full 棠溪 trading-system audit/fix session. Use it when an audit turns into implementation and the user expects the system to be genuinely fixed, not just diagnosed.

## Key lesson

For this system, source edits are not enough. Several runtime paths are separate from the repository and must be verified directly:

- Repository source: `D:/Hermes agent/scripts/`
- Hermes no-agent cron runtime copy: `%LOCALAPPDATA%/hermes/scripts/`
- Hermes venv python with trading deps: `%LOCALAPPDATA%/hermes/hermes-agent/venv/Scripts/python.exe`
- Data/health evidence: `data/`, `data/source_snapshots/`, `data/validation/`, `data/monitor_heartbeat.json`

If a script is modified in the repository but cron or watchdog runs the AppData copy, the fix is incomplete until the runtime copy is synced and executed.

## Closure checklist after fixing audit findings

1. **Sync runtime copies**
   - If modifying `gold_monitor.py`, `run_daily_validation.py`, or other no-agent cron scripts, copy the fixed repo file to `%LOCALAPPDATA%/hermes/scripts/`.
   - Do not assume `hermes cron` reads from the repository.

2. **Force a real cron run when clearing a red status**
   - A wrapper fix does not make `hermes cron list` turn green until the job runs again.
   - Run the specific cron job manually, then re-check the cron list/status.
   - Verify fresh artifacts, not just exit code. For daily validation, check `data/validation/` timestamps.

3. **Watchdog stale-noise handling**
   - If watchdog rate-limit logs come from old restart timestamps rather than current crashes, clear `data/watchdog_guard.json` to:
     `{"restart_times":[],"restart_times_emergency":[]}`
   - Then restart or verify the watchdog/background process.
   - Confirm heartbeat age is fresh and monitor PID/status are sane.

4. **XAU snapshot refresh verification**
   - After adding snapshot refresh to `gold_monitor.py`, run both the runtime copy and/or repository copy as appropriate.
   - Confirm `source_snapshot_XAUUSD.json` mtime and payload update with current price, quality, and confidence.
   - Do not rely only on gold monitor logs; the analysis card reads the unified snapshot.

5. **Git lock means commit and push**
   - 棠溪 uses “锁定” to mean `git commit` + `git push`, not just saving files.
   - Audit `git status --short` for critical untracked scripts. Add, commit, and push anything required for system recovery.
   - Expand `.gitignore` to exclude runtime data, local external tools, startup wrappers, and secret-bearing scripts before broad `git add`.

6. **Final proof bundle before claiming fixed**
   - `py_compile` changed Python files.
   - Run the relevant operational scripts once.
   - Run focused or full pytest.
   - Check cron list/status.
   - Check heartbeat freshness.
   - Check BTC/XAU source snapshot freshness and quality.
   - Check git status is clean after commit/push.

## Report style

When reporting completion to 棠溪, include concise evidence:

- exact test result, e.g. `97 passed`
- cron last run status/time
- latest snapshot timestamp/quality/confidence/price
- heartbeat age/PID/status
- commit hash and push result

Do not say “已修复” unless the runtime path was exercised and the evidence above is fresh.
