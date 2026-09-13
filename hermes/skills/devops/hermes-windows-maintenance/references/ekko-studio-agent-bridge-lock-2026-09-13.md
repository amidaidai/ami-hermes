# hermes update vs the Ekko Studio agent-bridge lock (2026-09-13)

Context: `hermes update` on a box where the live conversation ran inside the Hermes Studio / Ekko Studio desktop app. Install kind **git** at `D:\Hermes agent` (repo) with the app's venv at `C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv`. Version at the time: `v0.20.6 (2026.8.27) · upstream e16f6867`, **7979 commits behind**.

## Read-only pre-flight that worked
```
$ hermes update --plan
Update plan:
  Install: git (v0.20.6 @ c03c72a1)
  Profiles: default
  Running services to restart (1):
    • gateway [default] pid 37860 — manual @ c03c72a1
      restart: hermes gateway restart

$ hermes update --check
→ Fetching from origin...
⚕ Update available: 7979 commits behind origin/main.
```

## Abort #1 — `hermes.exe` shim guard (transient, ignore)
```
⚕ Updating Hermes Agent...
→ Fleet: 1 running service(s) across profiles: default
✗ Another hermes.exe is running:
    PID 32080  hermes.exe
  Updating now would fail to overwrite ...\venv\Scripts\hermes.exe because
  Windows blocks REPLACE on a running executable.
  ...
  Override with `hermes update --force` if you've already
  confirmed those processes will not write to the venv.
```
PID 32080 was already gone by the next `Get-Process` — it was the updater's own `hermes.exe` (the updater re-execs itself). Re-running was the fix, **not** `--force`.

## Abort #2 — venv-holder guard (the real gate)
```
  ⚠ Snapshot: skipping state.db (1.6 GB exceeds 1.0 GB limit)
◆ Pre-update snapshot: 20260913-145037-pre-update
◆ Creating pre-update backup...
  Saved: ~/AppData/Local/hermes/backups\pre-update-2026-09-13-225038.zip (1.2 GB, 119.8s)
  Restore:  hermes import ...\pre-update-2026-09-13-225038.zip

→ Stopping Windows gateway process(es) before updating Hermes...
  → 1 gateway(s) ACKed socket pause; waiting up to 190s for graceful exit
  ✓ Paused gateway profile(s): default
✗ Other Hermes processes are running from this install's venv:
  PID 408    python.exe  .../venv/Scripts/python.exe D:/Hermes agent/tools/binance-mcp/server.py
  PID 1592   python.exe  .../venv/Scripts/python.exe ...\Hermes Studio\Ekko Studio\resources\webui\dist\server\agent-bridge\python\hermes_bridge.py --worker-profile default --endpoint tcp://127.0.0.1:30317
  PID 33872  python.exe  ...
  On Windows these keep native extension files (.pyd) locked, so the
  dependency update would fail partway and leave a broken install.
  ...
  (or use `hermes update --force-venv` to proceed anyway at your own risk)

  ✓ Restarting Windows gateway profile(s): default
```

Notes: the backup URL printed with a Windows path but the separator was a single `\` — the restore line is authoritative. The gateway was paused **before** the guard fired and was not left running afterwards (`hermes gateway status` → `✗ Gateway is not running`), so the platforms stayed offline until the update completed.

## Process tree — two trees, only one is yours
```
Ekko Studio.exe 16276 --updated
└─ Ekko Studio.exe 10644
   ├─ python 31188 (venv)  -m hermes_cli.main gateway run --replace      <-- TREE A (gateway)
   │  └─ python 37860 (uv)  ... gateway run --replace                    (this is the pid --plan reports)
   │     ├─ python 36156 (venv) tools/binance-mcp/server.py
   │     ├─ node tradingview-mcp / Hermes Studio webui ×4
   │     └─ python 35768 (venv) scripts/btc_tv_refresh.py → keylevels_collect.py …
   └─ python 33872 (venv) agent-bridge/python/hermes_bridge.py          <-- TREE B (session host)
      └─ python 34036 (uv)
         └─ python 1592 (venv) hermes_bridge.py --worker-profile default
            ├─ python 408 (venv) tools/binance-mcp/server.py
            └─ powershell → bash ×3 → terminal tool  <-- WHERE THE AGENT RUNS
```
Tree A is stopped by the update's own gateway-pause step. Tree B survives it and holds the lock — so `--force-venv` was the only way to keep the session, and it was rejected (see semantics below).

Ancestry is easy to get wrong: `Get-CimInstance Win32_Process | Where-Object { $_.Name -like '*Studio*' }` returned **0** at one point while the app was clearly running, because the executable is named `Ekko Studio.exe`, not `Hermes Studio.exe`. Always query the generic `python.exe` / `hermes.exe` / `*Studio*.exe` set, and read `CommandLine` rather than trusting the process name.

## Dead ends (do not repeat)
| Attempt | Result |
|---|---|
| Kill the agent-bridge / its `binance-mcp` to free the lock | Ends the conversation; and `update_cmd.py` says **the app respawns a killed backend**, so the lock returns |
| `hermes update --force` | Bypasses the `hermes.exe` shim guard only — **not** the venv-holder guard |
| `hermes update --force-venv` | Clears the guard, then the dependency sync writes into locked `.pyd` → half-updated venv. Unacceptable at a 7979-commit delta |
| `terminal(background=true)` for the updater | Child of the session host → dies when Studio closes |

## What was deployed instead
`scripts/update-when-idle.ps1` launched detached via `Start-Process -WindowStyle Hidden -PassThru`, waiting for every venv holder **and** `Ekko Studio.exe` to disappear before calling `hermes update --yes --no-backup`. Verified live: the watcher started, logged `<pid>:<name>` for all 13 holders, and stayed alive while the session continued. The user then exits the tray icon; the watcher proceeds on its own and the log at `...\hermes\outputs\hermes_update_auto_<ts>.log` carries the whole run plus the pre/post HEAD.
