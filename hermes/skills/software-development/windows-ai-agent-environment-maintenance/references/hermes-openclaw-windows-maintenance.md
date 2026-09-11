# Hermes/OpenClaw Windows Maintenance Notes

Session-derived notes for maintaining Windows AI-agent tooling without overfitting to one transient install state.

## Active Runtime Discovery

Hermes Desktop may set runtime paths that differ from classic `~/.hermes` expectations. Check:

```powershell
$env:HERMES_HOME
$env:HERMES_BIN
$env:HERMES_WEB_UI_HOME
[Environment]::GetEnvironmentVariable('Path','User')
```

In this session, the active Hermes Desktop config lived under `%LOCALAPPDATA%\hermes\config.yaml`, while `%USERPROFILE%\.hermes` did not contain the expected config/env files.

## OpenClaw Command-Not-Found Pattern

When `openclaw tui` fails with PowerShell `CommandNotFoundException`:

1. Check PATH lookup:
   ```powershell
   Get-Command openclaw -ErrorAction SilentlyContinue | Format-List *
   where.exe openclaw
   ```
2. Search the likely portable install path:
   ```powershell
   Test-Path "$env:LOCALAPPDATA\OpenClaw\deps\portable-node\openclaw.cmd"
   ```
3. Run directly to distinguish install vs PATH:
   ```powershell
   & "$env:LOCALAPPDATA\OpenClaw\deps\portable-node\openclaw.cmd" --version
   ```
4. If direct run works, add the containing directory to user PATH; if uninstalling, remove both the directory and the PATH entry.

## Safe PATH Repair Pattern

Use a script file rather than complex inline quoting from bash-backed terminals:

```powershell
$backupName = 'PathBackupBeforeAgentPathFix'
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
[Environment]::SetEnvironmentVariable($backupName, $userPath, 'User')

$parts = $userPath -split ';' | Where-Object { $_ -and $_.Trim() -ne '' } | ForEach-Object { $_.Trim() }
# Transform, dedupe, add/remove entries, then write:
$newPath = ($parts | Select-Object -Unique) -join ';'
[Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
```

Always verify afterwards:

```powershell
[Environment]::GetEnvironmentVariable('Path','User')
Get-Command openclaw -ErrorAction SilentlyContinue
```

## PowerShell From Bash Pitfall

Inline commands containing `$_`, hashtables (`@{...}`), or nested quotes can be mangled by bash/MSYS before reaching PowerShell. If the script includes calculated properties like:

```powershell
@{n='SizeGB';e={[math]::Round($_.Size/1GB,2)}}
```

write it to `sandbox/some_check.ps1` and invoke:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'D:/Hermes agent/sandbox/some_check.ps1'
```

## System Audit Probes

Useful low-risk checks:

```powershell
Get-ComputerInfo | Select-Object OsName,OsVersion,CsProcessors,CsTotalPhysicalMemory | Format-List
Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory
Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID,FileSystem,Size,FreeSpace
Get-NetAdapter | Where-Object Status -eq 'Up'
Get-NetTCPConnection -State Listen | Sort-Object LocalPort | Select-Object LocalAddress,LocalPort,OwningProcess
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 15 Id,ProcessName,WorkingSet64,CPU
```

For NVIDIA VRAM, prefer:

```bash
nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version,temperature.gpu,utilization.gpu --format=csv
```

WMI `Win32_VideoController.AdapterRAM` can under-report modern NVIDIA cards.

## Hermes Provider/Vision Routing Probe

When checking Hermes vision routing, inspect config and resolve with installed helpers if available:

```python
import os, sys, yaml
sys.path.insert(0, r'C:/Users/Administrator/AppData/Local/hermes/hermes-agent')
os.environ['HERMES_HOME'] = r'C:/Users/Administrator/AppData/Local/hermes'
from hermes_cli.config import load_config
from agent.image_routing import decide_image_input_mode
from agent.auxiliary_client import resolve_vision_provider_client

cfg = load_config()
print(cfg.get('model'))
print(cfg.get('auxiliary', {}).get('vision'))
print(decide_image_input_mode(cfg['model']['provider'], cfg['model']['default'], cfg))
print(resolve_vision_provider_client())
```

Do not assume `hermes config` commands are the only source of truth; if a CLI wrapper fails, direct YAML inspection plus installed helper imports can still validate routing.
