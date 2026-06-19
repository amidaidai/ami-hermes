$ErrorActionPreference = "SilentlyContinue"
$patterns = @('*smart_monitor.py*', '*价格监控.py*', '*行情守望.py*')
$targets = Get-CimInstance Win32_Process | Where-Object {
    $cmd = $_.CommandLine
    if (-not $cmd) { return $false }
    $hit = $false
    foreach ($pat in $patterns) {
        if ($cmd -like $pat) { $hit = $true }
    }
    $hit -and $_.ProcessId -ne $PID -and $cmd -notlike '*停止价格监控.ps1*' -and $cmd -notlike '*停止行情守望.ps1*' -and $cmd -notlike '*stop_smart_monitor.ps1*'
}
foreach ($p in $targets) {
    try {
        Stop-Process -Id $p.ProcessId -Force
        Write-Output "stopped $($p.ProcessId) $($p.Name)"
    } catch {
        Write-Output "failed $($p.ProcessId) $($p.Name): $($_.Exception.Message)"
    }
}
