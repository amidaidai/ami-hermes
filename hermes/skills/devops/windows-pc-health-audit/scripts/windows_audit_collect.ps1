<#
Windows 整机体检 - 快批次采集器

用法:
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:/path/to/windows_audit_collect.ps1"

输出:
  %TEMP%\pc_audit_fast.txt  (UTF8)   -> 用 read_file 读，中文不乱码

只跑低开销维度（12+1 维中除"递归统计目录体积"以外的部分），正常 1-2 分钟。
递归目录体积 / 已装软件全量清单等慢项另行分批跑，
见 references/windows-machine-reclaim-and-optimization.md。
#>

$ErrorActionPreference = 'SilentlyContinue'
$out = New-Object System.Collections.Generic.List[string]
function W([string]$s) { $out.Add([string]$s) }
$now = Get-Date

W "===== WINDOWS PC AUDIT (FAST BATCH) ====="
W ("Generated: {0}" -f $now.ToString('yyyy-MM-dd HH:mm:ss'))
W ("IsAdmin: {0}" -f ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
W ("User: {0}  Computer: {1}" -f $env:USERNAME, $env:COMPUTERNAME)

W ""
W "-- 1. OS / HARDWARE --"
$cs = Get-CimInstance Win32_ComputerSystem
W ("Vendor/Model: {0} | {1}" -f $cs.Manufacturer, $cs.Model)
W ("TotalRAM_GB: {0:N2}" -f ($cs.TotalPhysicalMemory / 1GB))
$os = Get-CimInstance Win32_OperatingSystem
W ("OS: {0} | Build {1} | Version {2}" -f $os.Caption, $os.BuildNumber, $os.Version)
W ("InstallDate: {0:yyyy-MM-dd}  LastBoot: {1:yyyy-MM-dd HH:mm:ss}  Uptime_days: {2:N2}" -f $os.InstallDate, $os.LastBootUpTime, ($now - $os.LastBootUpTime).TotalDays)
W ("FreeRAM_GB: {0:N2}  FreeRAM_pct: {1:P1}" -f ($os.FreePhysicalMemory / 1MB), ($os.FreePhysicalMemory / $os.TotalVisibleMemorySize))
W ("Committed_GB: {0:N2} / Limit {1:N2}  PageFaults_per_s: {2:N0}" -f ((Get-Counter '\Memory\Committed Bytes').CounterSamples[0].CookedValue / 1GB), ((Get-Counter '\Memory\Commit Limit').CounterSamples[0].CookedValue / 1GB), (Get-Counter '\Memory\Page Faults/sec').CounterSamples[0].CookedValue)
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
W ("CPU: {0} | Cores/Threads {1}/{2} | MaxMHz {3} | Load {4}" -f $cpu.Name, $cpu.NumberOfCores, $cpu.NumberOfLogicalProcessors, $cpu.MaxClockSpeed, $cpu.LoadPercentage)
foreach ($g in (Get-CimInstance Win32_VideoController)) { W ("GPU: {0} | Driver {1} | Res {2}x{3}" -f $g.Name, $g.DriverVersion, $g.CurrentHorizontalResolution, $g.CurrentVerticalResolution) }
foreach ($m in (Get-CimInstance Win32_PhysicalMemory)) { W ("RAM module: {0}GB Speed={1} Configured={2} {3} {4}" -f ($m.Capacity / 1GB), $m.Speed, $m.ConfiguredClockSpeed, $m.Manufacturer, $m.DeviceLocator) }
W ("RAM slots total: {0}  used: {1}" -f (Get-CimInstance Win32_PhysicalMemoryArray).MemoryDevices, (Get-CimInstance Win32_PhysicalMemory | Measure-Object).Count)
$bios = Get-CimInstance Win32_BIOS
W ("BIOS: {0} | {1} | {2:yyyy-MM-dd}" -f $bios.Manufacturer, $bios.SMBIOSBIOSVersion, $bios.ReleaseDate)

W ""
W "-- 2. DISK / PARTITION --"
foreach ($v in (Get-Volume | Where-Object { $_.DriveLetter })) {
  W ("VOL {0}: FS={1} Size={2:N1}GB Free={3:N1}GB FreePct={4:P0} Health={5}" -f $v.DriveLetter, $v.FileSystem, ($v.Size / 1GB), ($v.SizeRemaining / 1GB), ($v.SizeRemaining / $v.Size), $v.HealthStatus)
}
foreach ($p in (Get-PhysicalDisk)) { W ("PHYSDISK: {0} | Media={1} | Health={2} | Bus={3}" -f $p.FriendlyName, $p.MediaType, $p.HealthStatus, $p.BusType) }
foreach ($p in (Get-Partition)) { W ("PART: Disk{0} #{1} {2:N1}GB Type={3} Letter={4}" -f $p.DiskNumber, $p.PartitionNumber, ($p.Size / 1GB), $p.Type, $p.DriveLetter) }
foreach ($l in (fsutil behavior query DisableDeleteNotify 2>&1 | Select-Object -First 2)) { W ("TRIM: {0}" -f $l) }
if (Test-Path 'C:\hiberfil.sys') { W ("hiberfil.sys: {0:N2}GB" -f ((Get-Item 'C:\hiberfil.sys' -Force).Length / 1GB)) } else { W "hiberfil.sys: not present" }
if (Test-Path 'C:\Windows.old') { W "Windows.old: EXISTS" } else { W "Windows.old: none" }
foreach ($p in (Get-CimInstance Win32_PageFileUsage)) { W ("PAGEFILE: {0} Alloc={1}MB Peak={2}MB" -f $p.Name, $p.AllocatedBaseSize, $p.PeakUsage) }

W ""
W "-- 3. BOOT MODE / SECURE BOOT --"
W ("BiosFirmwareType: {0}  firmware_type env: {1}" -f (Get-ComputerInfo -Property BiosFirmwareType).BiosFirmwareType, $env:firmware_type)
foreach ($l in (bcdedit /enum '{current}' 2>&1 | Select-String -Pattern 'path|description')) { W ("BCD: {0}" -f $l) }
$sb = Confirm-SecureBootUEFI
if ($sb -eq $true -or $sb -eq $false) { W ("SecureBoot: {0}" -f $sb) } else { W "SecureBoot: query returned nothing (likely Legacy BIOS / not UEFI)" }

W ""
W "-- 4. PENDING REBOOT / HOTFIX --"
W ("RebootPending_CBS: {0}" -f (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'))
W ("RebootRequired_WU: {0}" -f (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'))
foreach ($h in (Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 5)) { W ("HOTFIX: {0} {1:yyyy-MM-dd} {2}" -f $h.HotFixID, $h.InstalledOn, $h.Description) }

W ""
W "-- 5. AV / DEFENDER TAKEOVER --"
$mp = Get-MpComputerStatus
if ($mp) {
  W ("MpStatus: AntivirusEnabled={0} AMService={1} RealTime={2} Tamper={3} Engine={4} Sig={5}" -f $mp.AntivirusEnabled, $mp.AMServiceEnabled, $mp.RealTimeProtectionEnabled, $mp.IsTamperProtected, $mp.AMEngineVersion, $mp.AntivirusSignatureVersion)
  W ("MpStatus: QuickScanAge_days={0} FullScanAge_days={1}" -f $mp.QuickScanAge, $mp.FullScanAge)
}
foreach ($k in @('HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection', 'HKLM:\SOFTWARE\Microsoft\Windows Defender')) {
  $i = Get-Item $k
  if ($i) { foreach ($v in ($i.GetValueNames() | Where-Object { $_ -match 'Disable|ProductStatus|PassiveMode' })) { W ("AVREG {0} :: {1} = {2}" -f $k, $v, $i.GetValue($v)) } }
}
foreach ($av in (Get-CimInstance -Namespace root\SecurityCenter2 -ClassName AntiVirusProduct)) { W ("AVPRODUCT: {0} state=0x{1:X}" -f $av.displayName, $av.productState) }
W ("WinDefend service: {0} (StartType {1})" -f (Get-Service WinDefend).Status, (Get-Service WinDefend).StartType)
W "(被策略禁用时 Start-Service WinDefend 起不来; 测完保持原状态)"
foreach ($fw in (Get-NetFirewallProfile)) { W ("FIREWALL {0}: Enabled={1}" -f $fw.Name, $fw.Enabled) }
$fv = Get-MpThreatDetection
if ($fv) { foreach ($t in $fv) { W ("THREAT-DETECTION: {0} | {1}" -f $t.InitialDetectionTime, $t.ThreatID) } } else { W "THREAT-DETECTION: none recorded" }

W ""
W "-- 6. HIJACK VECTORS / PERSISTENCE --"
$wl = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
W ("Winlogon Shell: {0} | Userinit: {1} | Taskman: {2}" -f $wl.Shell, $wl.Userinit, $wl.Taskman)
$ai = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Windows'
W ("AppInit_DLLs: '{0}' LoadAppInit: {1}" -f $ai.AppInit_DLLs, $ai.LoadAppInit_DLLs)
$ifeoCount = 0
foreach ($k in (Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options')) {
  $d = (Get-ItemProperty $k.PSPath).Debugger
  if ($d) { W ("IFEO-HIJACK: {0} -> {1}" -f $k.PSChildName, $d); $ifeoCount++ }
}
W ("IFEO entries with Debugger: {0} (expect 0)" -f $ifeoCount)
$lsa = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa'
W ("LSA AuthPackages: '{0}' NotificationPackages: '{1}'" -f ($lsa.AuthenticationPackages -join ';'), ($lsa.NotificationPackages -join ';'))
$hosts = Get-Content 'C:\Windows\System32\drivers\etc\hosts' | Where-Object { $_ -notmatch '^\s*#' -and $_.Trim() -ne '' }
if ($hosts) { foreach ($h in $hosts) { W ("HOSTS-ENTRY: {0}" -f $h) } } else { W "HOSTS: no active custom entries" }

W ""
W "-- 7. STARTUP / SERVICES / TASKS --"
foreach ($s in (Get-CimInstance Win32_StartupCommand)) { W ("STARTUP [{0}] {1} :: {2}" -f $s.Location, $s.Name, $s.Command) }
$svc = Get-CimInstance Win32_Service
W ("SERVICES total={0} running={1} auto={2}" -f $svc.Count, ($svc | Where-Object State -eq 'Running').Count, ($svc | Where-Object StartMode -eq 'Auto').Count)
foreach ($s in ($svc | Where-Object { $_.PathName -and $_.PathName -notmatch 'system32|SysWOW64|Windows\\' } | Sort-Object State, Name)) {
  W ("SVC: {0} | {1} | Start={2} | {3}" -f $s.Name, $s.State, $s.StartMode, $s.PathName)
}
foreach ($s in ($svc | Where-Object { $_.StartMode -eq 'Auto' -and $_.State -ne 'Running' })) { W ("AUTOSTOPPED: {0}" -f $s.Name) }
foreach ($t in (Get-ScheduledTask | Where-Object { $_.TaskPath -notmatch '^\\Microsoft\\' })) {
  $ti = Get-ScheduledTaskInfo -TaskName $t.TaskName -TaskPath $t.TaskPath
  W ("TASK: {0}{1} | State={2} | Last={3} | Result={4}" -f $t.TaskPath, $t.TaskName, $t.State, $ti.LastRunTime, $ti.LastTaskResult)
}

W ""
W "-- 8. USERS / UAC / RDP --"
foreach ($u in (Get-LocalUser)) { W ("LOCALUSER: {0} | Enabled={1} | LastLogon={2}" -f $u.Name, $u.Enabled, $u.LastLogon) }
foreach ($g in (Get-LocalGroupMember -Group Administrators)) { W ("ADMINGROUP: {0}" -f $g.Name) }
$uac = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System'
W ("UAC EnableLUA={0} ConsentPromptBehaviorAdmin={1} (0=不弹窗, 5=默认)" -f $uac.EnableLUA, $uac.ConsentPromptBehaviorAdmin)
W ("RDP fDenyTSConnections={0} (1=禁止)" -f (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server').fDenyTSConnections)
W ("RemoteRegistry: {0}" -f (Get-Service RemoteRegistry).Status)

W ""
W "-- 9. NETWORK --"
$inet = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
W ("WinINET ProxyEnable={0} ProxyServer={1}" -f $inet.ProxyEnable, $inet.ProxyServer)
foreach ($d in (Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object { $_.ServerAddresses })) { W ("DNS {0}: {1}" -f $d.InterfaceAlias, ($d.ServerAddresses -join ',')) }
foreach ($c in (Get-NetTCPConnection -State Established | Where-Object { $_.RemoteAddress -notmatch '^(127\.|::1|0\.0\.0\.0|192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)' })) {
  $p = Get-Process -Id $c.OwningProcess
  W ("NET-EXT: {0}:{1} <- {2} pid={3}" -f $c.RemoteAddress, $c.RemotePort, $p.ProcessName, $c.OwningProcess)
}
foreach ($c in (Get-NetTCPConnection -State Listen | Where-Object { $_.LocalAddress -notmatch '^(127\.|::1)' })) {
  $p = Get-Process -Id $c.OwningProcess
  W ("LISTEN: {0}:{1} [{2}]" -f $c.LocalAddress, $c.LocalPort, $p.ProcessName)
}

W ""
W "-- 10. TOP PROCESSES --"
W ("Processes: {0}  Handles: {1}" -f (Get-Process | Measure-Object).Count, (Get-Process | Measure-Object Handles -Sum).Sum)
foreach ($p in (Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 20)) {
  W ("PROC-MEM: {0} | WS={1:N0}MB | Threads={2} | {3}" -f $p.ProcessName, ($p.WorkingSet / 1MB), $p.Threads.Count, $p.Path)
}
foreach ($p in (Get-Process | Sort-Object CPU -Descending | Select-Object -First 15)) {
  W ("PROC-CPU-CUM: {0} | CPU_s={1:N0} | WS={2:N0}MB" -f $p.ProcessName, $p.CPU, ($p.WorkingSet / 1MB))
}
foreach ($g in (Get-Process | Group-Object ProcessName | Sort-Object Count -Descending | Select-Object -First 12)) {
  W ("PROCGROUP: {0} x{1} | WS={2:N0}MB" -f $g.Name, $g.Count, (($g.Group | Measure-Object WorkingSet -Sum).Sum / 1MB))
}

W ""
W "-- 11. PROCESS SIGNATURE SWEEP --"
$uniq = Get-Process | Where-Object { $_.Path } | Sort-Object Path -Unique
W ("Unique process binaries: {0}" -f $uniq.Count)
foreach ($p in $uniq) {
  $sig = Get-AuthenticodeSignature -LiteralPath $p.Path
  $signer = ''
  if ($sig.SignerCertificate) { $signer = ($sig.SignerCertificate.Subject -replace '^CN=([^,]+).*', '$1') }
  $risky = $p.Path -match 'AppData\\(Local|Roaming)\\Temp|\\Temp\\|\\Downloads\\|\\Public\\|ProgramData\\[^\\]+\\'
  if ($sig.Status -ne 'Valid' -or $risky) { W ("FLAG: {0} | Status={1} | Signer={2} | {3}" -f $p.ProcessName, $sig.Status, $signer, $p.Path) }
}
W "(未签名 != 恶意; 判断项 = 未签名 且 从用户可写目录运行)"

W ""
W "-- 12. EVENT LOG / CRASH --"
$ev = Get-WinEvent -FilterHashtable @{LogName = 'System'; Level = 1, 2; StartTime = (Get-Date).AddDays(-7) } -MaxEvents 300
W ("SystemErrEvents(7d): {0}" -f ($ev | Measure-Object).Count)
foreach ($g in ($ev | Group-Object ProviderName | Sort-Object Count -Descending | Select-Object -First 10)) { W ("EVT-SYS: {0} x{1}" -f $g.Name, $g.Count) }
foreach ($e in ($ev | Sort-Object TimeCreated -Descending | Select-Object -First 12)) {
  $m = ($e.Message -replace "\s+", ' ')
  W ("EVT-D: {0:MM-dd HH:mm} | {1} | Id={2} | {3}" -f $e.TimeCreated, $e.ProviderName, $e.Id, $m.Substring(0, [Math]::Min(150, $m.Length)))
}
foreach ($e in (Get-WinEvent -FilterHashtable @{LogName = 'System'; Id = 41, 6008, 1001, 1003; StartTime = (Get-Date).AddDays(-30) } -MaxEvents 20)) {
  $m = ($e.Message -replace "\s+", ' ')
  W ("CRASH: {0:yyyy-MM-dd HH:mm} | {1} | Id={2} | {3}" -f $e.TimeCreated, $e.ProviderName, $e.Id, $m.Substring(0, [Math]::Min(130, $m.Length)))
}
W ("MinidumpCount: {0}" -f ((Get-ChildItem 'C:\Windows\Minidump') | Measure-Object).Count)

W ""
W "-- 13. TIME SYNC --"
W ("TimeZone: {0}  CurrentTime: {1}" -f (Get-TimeZone).Id, $now.ToString('yyyy-MM-dd HH:mm:ss'))
W ("w32time: {0} (StartType {1})" -f (Get-Service w32time).Status, (Get-Service w32time).StartType)
foreach ($l in (w32tm /query /status 2>&1 | Select-Object -First 12)) { W ("NTP: {0}" -f $l) }
W "(源=Local CMOS Clock 且 上次成功同步=未指定 => 从未同步过, P1 项)"

W ""
W "-- 14. BROWSER EXTENSIONS --"
function Resolve-Ext([string]$root, [string]$name) {
  if (-not (Test-Path $root)) { return }
  foreach ($e in (Get-ChildItem $root -Directory)) {
    $sub = Get-ChildItem $e.FullName -Directory | Sort-Object Name -Descending | Select-Object -First 1
    if (-not $sub) { continue }
    $mf = Join-Path $sub.FullName 'manifest.json'
    if (-not (Test-Path $mf)) { continue }
    $j = Get-Content $mf -Raw -Encoding UTF8 | ConvertFrom-Json
    $nm = $j.name
    $desc = $j.description
    foreach ($field in @('nm', 'desc')) {
      $val = if ($field -eq 'nm') { $nm } else { $desc }
      if ($val -like '__MSG_*') {
        $key = $val.Trim('_').Replace('MSG_', '')
        foreach ($loc in @('zh_CN', 'en', 'en_US')) {
          $lf = Join-Path $sub.FullName "_locales\$loc\messages.json"
          if (Test-Path $lf) {
            $m = Get-Content $lf -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($m.$key.message) { if ($field -eq 'nm') { $nm = $m.$key.message } else { $desc = $m.$key.message }; break }
          }
        }
      }
    }
    W ("EXT [{0}] {1} | NAME={2} | v{3}" -f $name, $e.Name, $nm, $j.version)
    W ("     PERMS: {0}" -f ($j.permissions -join ','))
    W ("     HOSTS: {0}" -f ($j.host_permissions -join ','))
  }
}
Resolve-Ext "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Extensions" 'Chrome'
Resolve-Ext "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Extensions" 'Edge'

W ""
W "-- 15. PENDING WINDOWS UPDATES --"
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$res = $searcher.Search('IsInstalled=0 and IsHidden=0')
W ("Pending updates: {0}" -f $res.Updates.Count)
foreach ($u in ($res.Updates | Select-Object -First 25)) { W ("WU-PENDING: {0}" -f $u.Title) }

$target = Join-Path $env:TEMP 'pc_audit_fast.txt'
$out | Out-File -FilePath $target -Encoding UTF8
Write-Output ("WROTE {0} lines -> {1}" -f $out.Count, $target)
