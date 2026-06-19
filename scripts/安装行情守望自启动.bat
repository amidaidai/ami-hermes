@echo off
REM Install HW Monitor Scheduled Task
set TASK_NAME=HW_Monitor
set SCRIPT_PATH=D:\Hermes agent\scripts\行情守望.py

for /f "delims=" %%i in ('where python') do set PYTHON_PATH=%%i

echo Creating scheduled task: %TASK_NAME%
echo Python: %PYTHON_PATH%
echo Script: %SCRIPT_PATH%

REM Delete existing task
schtasks /delete /tn "%TASK_NAME%" /f 2>nul

REM Create new task - start at boot, delay 60s, highest privileges
schtasks /create /tn "%TASK_NAME%" /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\"" /sc onstart /delay 0001:00 /rl HIGHEST /f

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================
    echo SUCCESS - Task created
    echo ========================================
    echo.
    echo Manual controls:
    echo   Start: schtasks /run   /tn "%TASK_NAME%"
    echo   Stop:  schtasks /end   /tn "%TASK_NAME%"
    echo   Query: schtasks /query /tn "%TASK_NAME%" /v
    echo.
    REM Start it now
    schtasks /run /tn "%TASK_NAME%"
    echo Started task immediately.
) else (
    echo.
    echo FAILED - Try running as Administrator
    echo Right-click this .bat file -> Run as Administrator
    pause
)
