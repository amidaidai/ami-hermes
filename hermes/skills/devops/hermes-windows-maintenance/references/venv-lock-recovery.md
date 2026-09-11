# venv-lock recovery — session transcript & exact commands

## The real `hermes update` abort message (Windows)
```
⚕ Updating Hermes Agent...
→ Stopping Windows gateway process(es) before updating Hermes...
  ✓ Paused gateway profile(s): default
✗ Other Hermes processes are running from this install's venv:
  PID 11468  python.exe  python D:/Hermes agent/scripts/btc_daemon.py
  PID 14240  python.exe  python D:/Hermes agent/scripts/行情守望.py -s BTCUSDT XAUUSD
  PID 22236  python.exe  python D:/Hermes agent/scripts/行情守望.py -s BTCUSDT XAUUSD
  PID 51236  python.exe  ...hermes-agent\venv\Scripts\python.EXE D:/Hermes agent/tools/binance-mcp/serve
  On Windows these keep native extension files (.pyd) locked, so the
  dependency update would fail partway and leave a broken install.
  Close the Hermes desktop app / other Hermes terminals, then re-run:
    hermes update
  (or use `hermes update --force-venv` to proceed anyway at your own risk)
  ✓ Restarting Windows gateway profile(s): default
```

## Process-parent check (shows daemons are NOT children of desktop)
```powershell
Get-CimInstance Win32_Process | Where-Object { @(11468,14240,22236,51236) -contains $_.ProcessId } | Select-Object ProcessId,ParentProcessId,Name,CommandLine
# -> btc_daemon parent 9348 ; 行情守望 parents 18904, 17476 ; binance-mcp parent 40612
# All unrelated parents => daemons survive a desktop exit.
```

## Diagnose (filter by Name to avoid self-match)
```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -like '*btc_daemon*' -or $_.CommandLine -like '*行情守望*' -or $_.CommandLine -like '*binance-mcp*') } | Select-Object ProcessId,CommandLine | Format-List
(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'Hermes Studio*' }).Count
```

## Kill standalone Tangxi daemons safely (desktop relaunches them)
```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -like '*btc_daemon*' -or $_.CommandLine -like '*行情守望*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
```

## Force update + verify (used when desktop must stay up)
```bash
hermes update --force-venv     # 2>&1 | tail -40
hermes --version               # -> Hermes Agent v0.18.2 (2026.7.7.2) · Up to date
hermes doctor                  # -> All checks passed!
```
Observed `force-venv` output tail:
- Web UI build FAILED (non-fatal): `src/pages/ChannelsPage.tsx(17,25): error TS7016: Could not find a declaration file for module 'qrcode'` and `vite.config.ts(2,19): error TS2307: Cannot find module '@vitejs/plugin-react'`. Updater serves stale dist as fallback. Core Python unaffected.
- `✓ Code updated!`, `✓ Model catalog cache refreshed`, `✓ Skills are up to date`, `✓ Configuration is up to date`, `✓ Update complete!`, then `draining gateway PID ...` + `Restarting Windows gateway profile(s): default`.

## Observed instance multiplication (the trap)
- Before any manual launch: 2× btc_daemon, 2× 行情守望, 4× binance-mcp (because 6 `Hermes Studio.exe` were running).
- After I ran `terminal(background=true)` on `python scripts/btc_daemon.py`: it jumped to **5× btc_daemon** instances — the desktop gateway had ALSO relaunched it during `hermes update`'s gateway restart. Manual launch = stacking duplicates.
- Fix: `Stop-Process` all btc_daemon/行情守望, confirm count 0, let a SINGLE desktop instance relaunch them. Never manually `background=true` the auto-managed daemons.

## What did NOT work
- `taskkill /PID 11468 /F` under git-bash → "无效开关/PID" (bash treats `/PID` as path). Use PowerShell `Stop-Process`.
- `nohup python x.py &`/`disown` → Hermes terminal blocks shell-level background wrappers; returns instruction to use `background=true`.
- Nested PowerShell `$_.ProcessId -in @(...)` inside bash `$(...)` → exit code -1 / self-match. Keep queries simple and filter on `Name`.
