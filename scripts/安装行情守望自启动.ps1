# 行情守望 开机自启动任务计划
# 以管理员身份运行此脚本

$TaskName = "行情守望"
$ScriptPath = "D:\Hermes agent\scripts\行情守望.py"
$PythonExe = (Get-Command python).Source

# 先删除旧任务（如果存在）
schtasks /delete /tn $TaskName /f 2>$null

# 创建开机自启任务：延迟60秒启动，最高权限
$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptPath`""
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force

Write-Host "✅ 行情守望开机自启动已配置"
Write-Host "   任务名: $TaskName"
Write-Host "   Python: $PythonExe"
Write-Host "   脚本:   $ScriptPath"
Write-Host ""
Write-Host "手动启动: schtasks /run /tn 行情守望"
Write-Host "手动停止: schtasks /end /tn 行情守望"
Write-Host "查看状态: schtasks /query /tn 行情守望 /v"
