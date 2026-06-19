@echo off
set TASK_NAME=HW_Monitor
set SCRIPT=D:\Hermes agent\scripts\market_watch.py
set PYTHON=C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe

schtasks /delete /tn "%TASK_NAME%" /f 2>nul
schtasks /create /tn "%TASK_NAME%" /tr "\"%PYTHON%\" \"%SCRIPT%\"" /sc onstart /delay 0001:00 /f

if %ERRORLEVEL% equ 0 (
    echo OK
    schtasks /run /tn "%TASK_NAME%"
) else (
    echo FAILED - need Admin
)
