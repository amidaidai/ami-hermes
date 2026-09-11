---
name: realtime-watchdog-daemon
description: >-
  Set up real-time condition monitoring using a background Python daemon
  process that polls every N seconds and alerts on condition trigger.
  Zero LLM token cost. For sub-minute polling requirements where cron
  interval is too coarse.
---

# Realtime Watchdog Daemon

Use when the user needs **sub-minute monitoring** of any condition (price level, API state, file change, threshold breach) — intervals too short for cron (which bottoms out at ~1-5m).

## Pattern

```
1. Write a Python script with a `while True: sleep(N)` loop
2. Script stays **completely silent** unless the condition triggers
3. On trigger: `print()` the alert message, then `sys.exit(0)`
4. Launch with: terminal(background=true, notify_on_complete=true)
5. Hermes captures stdout on exit and delivers it
```

## Key Design Rules

- **Silent until trigger**: no heartbeat logs, no "still checking" prints. Every byte printed inflates the stdout buffer. Only print on the trigger event.
- **Zero LLM cost**: pure Python HTTP requests (`urllib.request`), no MCP calls, no agent loop. Use `no_agent` cron as alternative for ≥1m intervals.
- **Graceful API polling**: catch exceptions, retry once on failure, `continue` on repeated failure. Never crash the daemon on a transient network blip.
- **Exit on match**: once the condition fires, the script should exit immediately after printing. Don't keep polling.

## When to Use vs. Cron

| Requirement | Tool |
|---|---|
| Every 10-30 seconds | Background daemon (this skill) |
| Every 1-5 minutes | `no_agent` cron job with script |
| Every 5+ minutes with reasoning | LLM-driven cron job |

## User Preference (棠溪)

Price condition monitors must be **real-time** (every ~10s), not 5-minute cron. User will correct you if you default to cron for sub-minute monitoring needs. Zero-token mode is preferred over LLM-driven checks.

## Pitfalls

- ✅ Always bind `closes` / result variables at the top of the while loop (initialize to `[]` / `0`) — avoids unbound-variable warnings
- ✅ Keep the while loop body under 50 lines; avoid stdout accumulation
- ❌ Don't use `print()` for debug/heartbeat in a long-lived daemon — stdout buffer fills up
- ❌ Don't use multi-minute cron for "real-time" monitoring — user will push back
- ✅ For Binance price monitoring, use `api.binance.com/api/v3/ticker/price` (free, no auth)
- ✅ **High-frequency daemon (10s) + Periodic pipeline daemon (3min)** = best architecture. Keep the fast loop lightweight (price/CVD/sweep only). Defer heavy analysis (FVG/OB/scoring/2022 pipeline) to a separate pipeline daemon with a longer interval. Don't mix them in one loop.
- ✅ **TV screenshots on high-probability signals**: pipeline daemon can call `tv_screenshot.py` subprocess when scoring detects high-probability (e.g. 2022 pipeline stage=entry_ready or multi-factor score≥8). Save screenshot path to state file for later MEDIA injection.
- ✅ **State file persistence**: write pipeline state to `btc_pipeline_state.json` (last_stage, last_score, FVG count, OB count, screenshot path) for cross-cycle awareness.
- 🔴 **Deleting the script file does NOT stop running processes**. The Python interpreter loads the full script into memory at startup. `rm`-ing the `.py` file only prevents restart — every already-running instance continues to poll and push indefinitely. Always kill all matching processes after file deletion.
- ✅ **Single-instance PID lock**: daemon scripts that could be launched multiple times (manually, via terminal background, by different shells) should write a PID lock file at startup. Check the lock on every launch and refuse to start a duplicate. This prevents the common pattern of 3-6+ concurrent instances silently pushing duplicate alerts. Simple implementation: `lock_file = "/tmp/mydaemon.lock"` with `os.getpid()` / `os.kill(pid, 0)` check.

## 🧹 Removing a Daemon (Complete Cleanup Procedure)

When the user asks to delete/stop/remove a monitoring daemon script, do NOT just delete the file. Follow these steps in order:

1. **Kill all running instances first** — find and terminate every process running the script:
   ```bash
   # Find all instances (Windows)
   powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe' AND CommandLine LIKE '%script_name%'\" | Select-Object ProcessId | Format-Table -AutoSize"
   
   # Kill each PID
   taskkill //F //PID <pid>
   
   # Or bulk kill by name pattern (caution: don't kill unrelated processes)
   taskkill //F //FI "IMAGENAME eq python.exe" 2>/dev/null  # ❌ too broad
   ```
   ⚠️ Use `Get-CimInstance` with a `CommandLine` filter, not just process name — many unrelated python.exe processes exist.

2. **Delete the script file** — only after killing all instances
3. **Delete associated state/data files** — monitor state JSONs, alert logs, pending files
4. **Remove cron jobs** — `cronjob(action='list')` → identify → `cronjob(action='remove', job_id=...)`
5. **Check Windows scheduled tasks** — `schtasks /query /FO LIST /V | grep -i script_name`
6. **Verify no residual processes** — re-run the process check from step 1

**Root cause of ghost alerts**: deleting the `.py` file is like cutting the launch pad — the rockets already in flight keep flying. The in-memory code continues its `while True: sleep(N)` loop and `subprocess.run`‑based Telegram pushes indefinitely. Always kill the live processes, then delete the file.

## Verification

```python
# Quick smoke test: run the script once, it should exit silently
# if condition not met:
python /path/to/watchdog.py
# exit code should be 0, stdout should be empty
```

## References

- `references/btc-realtime-watch.py` — full working example for BTCUSDT price condition monitoring
