# update-when-idle.ps1 — detached Hermes updater that waits for the venv lock to clear.
#
# WHY: on Windows `hermes update` refuses to run while any venv python (the Studio
# agent-bridge hermes_bridge.py, binance-mcp/server.py, ...) is alive, because they keep
# .pyd files locked. The app RESPAWNS a killed backend, so the only clean path is for the
# user to fully exit Studio. This watcher survives that exit and then runs the update.
#
# LAUNCH DETACHED (never terminal(background=true) — that dies with the session host):
#   powershell -NoProfile -Command "Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\Administrator\AppData\Local\hermes\outputs\update-when-idle.ps1' -WindowStyle Hidden -PassThru | Select-Object -ExpandProperty Id"
#
# Then tell the user: exit Studio from the TRAY ICON (closing windows is not enough).
# Read the log this script prints/creates to follow progress.

$ErrorActionPreference = 'Continue'

$OutDir    = 'C:\Users\Administrator\AppData\Local\hermes\outputs'
$HermesExe = 'C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe'
$RepoDir   = 'D:\Hermes agent'
$TimeoutMin = 45

$ts  = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = Join-Path $OutDir "hermes_update_auto_$ts.log"
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

function Log($m) {
  "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $m" | Out-File -FilePath $log -Append -Encoding utf8
}

# Holders = anything that keeps venv .pyd locked, plus the desktop app itself.
function Get-Holders {
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessId -ne $PID -and (
      ($_.Name -eq 'python.exe' -and "$($_.CommandLine)" -like '*hermes-agent\venv\Scripts\python*') -or
      ($_.Name -eq 'hermes.exe') -or
      ($_.Name -eq 'Hermes Studio.exe') -or
      ($_.Name -eq 'Ekko Studio.exe')
    )
  }
}

Log "watcher started (pid $PID); log=$log"
Log "waiting for venv holders + Studio to exit (max $TimeoutMin min)"

$deadline = (Get-Date).AddMinutes($TimeoutMin)
$waited = 0
while ((Get-Date) -lt $deadline) {
  $holders = @(Get-Holders)
  if ($holders.Count -eq 0) { break }
  if ($waited % 30 -eq 0) {
    $names = ($holders | ForEach-Object { "$($_.ProcessId):$($_.Name)" }) -join ' '
    Log "  waiting ($waited s) holders = $names"
  }
  Start-Sleep -Seconds 5
  $waited += 5
}

$left = @(Get-Holders)
if ($left.Count -gt 0) {
  Log "TIMEOUT after $waited s - holders still locked, NOT updating:"
  foreach ($h in $left) { Log "  $($h.ProcessId) $($h.Name) $($h.CommandLine)" }
  Log 'RESULT=timeout'
  exit 1
}

Log "all holders cleared after $waited s"
Start-Sleep -Seconds 6                     # let the OS release the file handles
$left2 = @(Get-Holders)
if ($left2.Count -gt 0) {
  Log "holders reappeared (respawned) after clearing - aborting, count=$($left2.Count)"
  Log 'RESULT=respawned'
  exit 1
}

Set-Location $RepoDir
Log "pre-update HEAD = $(& git rev-parse HEAD)"
# --no-backup: a full pre-update zip was already taken this round (update also snapshots
# state). Swap to --backup if you want a fresh full zip, at ~2 min for a 1.2 GB home dir.
Log 'running: hermes update --yes --no-backup'
Log '-----------------------------------------------------------'

& $HermesExe update --yes --no-backup 2>&1 | ForEach-Object { Log $_ }
$code = $LASTEXITCODE

Log '-----------------------------------------------------------'
Log "update exit code = $code"
Log "post-update HEAD = $(& git rev-parse HEAD)"
Log 'RESULT=done'
