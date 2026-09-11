# Windows System Audit — PowerShell Commands Reference

All commands run via `powershell -Command "..." | cat` in MSYS/Git Bash.
Escaping: use `\$` for `$` inside double-quoted bash strings, or wrap in single quotes where possible.

## ① Hardware

```powershell
# CPU
Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,CurrentClockSpeed,LoadPercentage | Format-List

# GPU
Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,DriverDate,AdapterRAM,Status | Format-List

# Motherboard + BIOS
Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product,Version | Format-List
Get-CimInstance Win32_BIOS | Select-Object Manufacturer,SMBIOSBIOSVersion,ReleaseDate | Format-List

# Physical memory modules
Get-CimInstance Win32_PhysicalMemory | Select-Object BankLabel,Capacity,Speed,ConfiguredClockSpeed,Manufacturer,PartNumber | Format-Table -AutoSize

# Disk model
Get-CimInstance Win32_DiskDrive | Select-Object Model,Size,MediaType,InterfaceType,Status | Format-Table -AutoSize

# Sound devices
Get-CimInstance Win32_SoundDevice | Select-Object Name,Status | Format-Table -AutoSize

# Network adapters (physical)
Get-CimInstance Win32_NetworkAdapter | Where-Object { $_.NetConnectionID } | Select-Object Name,NetConnectionID,Speed,MACAddress | Format-Table -AutoSize
```

## ② OS & Runtime

```powershell
Get-ComputerInfo | Select-Object OsName,OsVersion,WindowsVersion,OsArchitecture,OsBuildNumber,OsInstallDate | Format-List

# Uptime
Get-CimInstance Win32_OperatingSystem | Select-Object LastBootUpTime, @{N='Uptime_Days';E={[math]::Round(((Get-Date) - $_.LastBootUpTime).TotalDays,1)}}

# Current time (for uptime calc)
(Get-Date).ToString('yyyy-MM-dd HH:mm:ss')

# Page file
Get-CimInstance Win32_PageFileUsage | Select-Object Name,@{N='AllocatedGB';E={[math]::Round($_.AllocatedBaseSize/1GB,1)}},CurrentUsage,PeakUsage | Format-List

# Timezone
Get-CimInstance Win32_TimeZone | Select-Object Caption,StandardName
```

## ③ Disk

```powershell
Get-Volume | Select-Object DriveLetter,FileSystemLabel,FileSystem,HealthStatus,@{N='SizeGB';E={[math]::Round($_.Size/1GB,1)}},@{N='FreeGB';E={[math]::Round($_.SizeRemaining/1GB,1)}} | Format-Table -AutoSize

# Alternative (PSDrive)
Get-PSDrive -PSProvider FileSystem | Format-Table Name,Used,Free -AutoSize
```

## ④ Security

```powershell
# Windows Defender
Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureLastUpdated,QuickScanEndTime,FullScanEndTime | Format-List

# Firewall profiles
Get-NetFirewallProfile | Select-Object Name,Enabled | Format-Table -AutoSize

# Inbound rule count
Get-NetFirewallRule | Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' } | Measure-Object | Select-Object Count

# Last security update (HotFix)
Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10 HotFixID,Description,InstalledOn | Format-Table -AutoSize

# BitLocker
Get-BitLockerVolume | Select-Object MountPoint,ProtectionStatus,EncryptionMethod | Format-Table -AutoSize

# Defender preferences / exclusions
Get-MpPreference | Select-Object DisableRealtimeMonitoring,ExclusionPath,ExclusionExtension | Format-List

# Recent threats
Get-MpThreat | Select-Object ThreatName,DetectionTime | Format-Table -AutoSize
```

## ⑤ Network

```powershell
# Adapter status + link speed
Get-NetIPConfiguration | Select-Object -ExpandProperty NetAdapter | Select-Object Name,Status,LinkSpeed | Format-Table -AutoSize

# DNS servers
Get-DnsClientServerAddress | Where-Object { $_.ServerAddresses } | Select-Object InterfaceAlias,ServerAddresses | Format-Table -AutoSize

# Proxy settings
Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' | Select-Object ProxyEnable,ProxyServer,ProxyOverride | Format-List

# Active connections count
netstat -ano | Select-String 'ESTABLISHED' | Measure-Object | Select-Object Count

# Listening ports
Get-NetTCPConnection | Where-Object { $_.State -eq 'Listen' } | Select-Object LocalPort,OwningProcess | Sort-Object LocalPort | Format-Table -AutoSize
```

## ⑥ Memory & Processes

```powershell
# Total / Free / Used RAM
Get-CimInstance Win32_OperatingSystem | Select-Object @{N='TotalRAM_GB';E={[math]::Round($_.TotalVisibleMemorySize/1MB,1)}},@{N='FreeRAM_GB';E={[math]::Round($_.FreePhysicalMemory/1MB,1)}},@{N='UsedRAM_GB';E={[math]::Round(($_.TotalVisibleMemorySize-$_.FreePhysicalMemory)/1MB,1)}} | Format-List

# Total process memory
[math]::Round((Get-Process | Measure-Object WorkingSet64 -Sum).Sum/1GB,2)

# Top processes by memory + CPU
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 20 Name,@{N='CPU(s)';E={[math]::Round($_.CPU,1)}},@{N='MB';E={[math]::Round($_.WorkingSet64/1MB,0)}},Id | Format-Table -AutoSize

# Process count by name
Get-Process | Group-Object Name | Sort-Object Count -Descending | Select-Object -First 10 Count,Name | Format-Table -AutoSize
```

## ⑦ Drivers & Devices

```powershell
# Problem devices (ConfigManagerErrorCode ≠ 0)
Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -ne 0 } | Select-Object Name,DeviceID,ConfigManagerErrorCode | Format-Table -AutoSize

# Key drivers (GPU, NIC, Audio)
Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceName -like '*NVIDIA*' -or $_.DeviceName -like '*Intel*' -or $_.DeviceName -like '*Realtek*' } | Select-Object DeviceName,DriverVersion,DriverDate | Format-Table -AutoSize

# Printers
Get-CimInstance Win32_Printer | Select-Object Name,Default,PrinterStatus | Format-Table -AutoSize
```

## ⑧ User Accounts

```powershell
Get-LocalUser | Select-Object Name,Enabled,LastLogon,PasswordLastSet | Format-Table -AutoSize
Get-LocalGroupMember -Group Administrators | Select-Object Name,PrincipalSource | Format-Table -AutoSize
```

## ⑨ Startup Items

```powershell
Get-CimInstance Win32_StartupCommand | Select-Object Name,Command,Location | Format-Table -AutoSize
```

## ⑩ Scheduled Tasks

```powershell
Get-ScheduledTask | Where-Object { $_.State -eq 'Ready' -or $_.State -eq 'Running' } | Select-Object TaskName,State | Format-Table -AutoSize
```

## ⑪ Event Logs

```powershell
# System errors (Level ≤ 2 = Error/Critical)
Get-WinEvent -LogName System -MaxEvents 50 | Where-Object { $_.Level -le 2 } | Select-Object -First 10 TimeCreated,Id,LevelDisplayName,ProviderName,Message | Format-List

# Application errors
Get-WinEvent -LogName Application -MaxEvents 50 | Where-Object { $_.Level -le 2 } | Select-Object -First 10 TimeCreated,Id,LevelDisplayName,ProviderName | Format-Table -AutoSize

# Windows Update log
Get-WinEvent -LogName 'Microsoft-Windows-WindowsUpdateClient/Operational' -MaxEvents 5 | Select-Object TimeCreated,Id,Message | Format-List

# Security logins (4624=success, 4625=failure, 4672=special privileges)
Get-WinEvent -LogName Security -MaxEvents 50 | Where-Object { $_.Id -eq 4625 } | Select-Object -First 5 TimeCreated
```

## ⑫ Shares

```powershell
Get-CimInstance Win32_Share | Select-Object Name,Path,Type | Format-Table -AutoSize
```

## Pitfalls

- `wmic` is NOT available in MSYS/Git Bash — always use `powershell -Command`
- Pipe to `| cat` to avoid PowerShell output truncation in bash
- Use `\$` to escape `$` in bash double-quoted strings
- Chinese locale output has encoding issues in bash — PowerShell handles it better
- `Get-WindowsUpdate` module may not be installed — fall back to `Get-HotFix` + Update event log
- Temperature sensors (`Win32_TemperatureProbe`) usually return empty on desktop PCs
- `AdapterRAM` on GPU may be empty for some drivers — use VRAM from driver name instead
