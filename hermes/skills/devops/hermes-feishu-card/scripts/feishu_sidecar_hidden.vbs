Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "D:\Hermes agent"
sh.Run """C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"" ""D:\Hermes agent\scripts\feishu_sidecar_watchdog.py""", 0, False