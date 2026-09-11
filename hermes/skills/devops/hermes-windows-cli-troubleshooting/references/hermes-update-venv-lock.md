# hermes update — venv .pyd lock resolution (worked example)

## Observed abort (verbatim, trimmed)
```
⚕ Updating Hermes Agent...
→ Stopping Windows gateway process(es) before updating Hermes...
  ✓ Paused gateway profile(s): default
✗ Other Hermes processes are running from this install's venv:
  PID 11468  python.exe  python D:/Hermes agent/scripts/btc_daemon.py
  PID 14240  python.exe  python D:/Hermes agent/scripts/行情守望.py -s BTCUSDT XAUUSD
  PID 22236  python.exe  python D:/Hermes agent/scripts/行情守望.py -s BTCUSDT XAUUSD
  PID 51236  python.exe  C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\python.EXE D:/Hermes agent/tools/binance-mcp/server.py
  On Windows these keep native extension files (.pyd) locked, so the
  dependency update would fail partway and leave a broken install.
  Close the Hermes desktop app / other Hermes terminals, then re-run:
    hermes update
  (or use `hermes update --force-venv` to proceed anyway at your own risk)
  ✓ Restarting Windows gateway profile(s): default
```

## PID classification (this session)
| PID | CommandLine | Class | Action |
|-----|-------------|-------|--------|
| 51236 | `.../venv/Scripts/python.EXE .../tools/binance-mcp/server.py` | desktop backend = CURRENT SESSION HOST | NEVER kill from agent; only user exits GUI |
| 11468 | `python D:/Hermes agent/scripts/btc_daemon.py` (parent 9348) | independent daemon | kill |
| 14240 | `python 行情守望.py -s BTCUSDT XAUUSD` (parent 18904) | independent daemon | kill |
| 22236 | `python 行情守望.py -s BTCUSDT XAUUSD` (parent 17476) | independent daemon — DUPLICATE instance | kill (both) |

Note: `hermes cron list` showed schedulers btc_ref_levels_sync / orion_screener_radar / dune_collector / COT — none matched the locking PIDs, so the 3 daemons were NOT cron-managed. No `watchdog.py` in the process tree → killing them won't auto-restart.

## Commands that worked
```powershell
# Identify each PID's parent + full command line
Get-CimInstance Win32_Process | Where-Object { @(11468,14240,22236,51236) -contains $_.ProcessId } | Select-Object ProcessId,ParentProcessId,Name,CommandLine | Format-List

# Kill independent daemons (NOT the desktop backend)
powershell -NoProfile -Command "Stop-Process -Id 11468,14240,22236 -Force -ErrorAction SilentlyContinue"

# Confirm gone
Get-CimInstance Win32_Process | Where-Object { @(11468,14240,22236) -contains $_.ProcessId } | Select-Object ProcessId,Name | Format-Table -AutoSize
```

## Commands that FAILED (pitfall)
```bash
# Under git-bash/MSYS this FAILS — '/PID' parsed as a path:
taskkill /PID 11468 /F
# → 无效选项 - 'C:/Program Files/Git/PID'
```

## Relaunch (after update, deduplicated)
- `btc_daemon.py` — 1 instance
- `行情守望.py -s BTCUSDT XAUUSD` — ONLY 1 instance (the leaked 2nd PID was a bug; do not reproduce)

## Why the agent must not kill the desktop backend
PID 51236 is the binance-mcp server started by the Hermes Desktop runtime. Killing it terminates the live conversation. The only safe path is: user exits the desktop GUI → runs `hermes update` in a SEPARATE terminal → returns the `update` + `doctor` output to a fresh session. The agent may freely kill the non-cron daemons beforehand so the separate-terminal update doesn't get re-locked.
