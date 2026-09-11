# Windows Audit Commands

Proven PowerShell commands for auditing a Hermes installation on Windows 11 via git-bash terminal.

## System Overview

```bash
# OS info + boot time + memory
powershell.exe -Command "Get-CimInstance Win32_OperatingSystem | Select-Object Caption, LastBootUpTime, TotalVisibleMemorySize, FreePhysicalMemory, NumberOfProcesses"

# CPU-heavy processes (top 15)
powershell.exe -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 15 Name, CPU, WorkingSet, StartTime | Format-Table -AutoSize"

# Disk usage
df -h
```

## Hermes Config Locations

```bash
# Primary config (Windows %APPDATA% path)
# C:\Users\<user>\AppData\Local\hermes\config.yaml

# .env file (alongside config.yaml)
# C:\Users\<user>\AppData\Local\hermes\.env

# Hermes Web UI config
# C:\Users\<user>\.hermes-web-ui\config.json

# Hermes Web UI database
# C:\Users\<user>\.hermes-web-ui\hermes-web-ui.db
```

## Reading Hermes Web UI DB via Python

```python
import sqlite3, os

db_path = os.path.expanduser(r"~\AppData\Local\hermes\hermes-web-ui\hermes-web-ui.db")
# Alternative if that doesn't exist:
db_path2 = os.path.expanduser(r"~\.hermes-web-ui\hermes-web-ui.db")

conn = sqlite3.connect(db_path2)
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
for t in cursor.fetchall():
    print(t[0])

# Check user accounts
cursor.execute("SELECT id, username, role, status, last_login_at FROM users")
for row in cursor.fetchall():
    print(row)

# Check provider settings
cursor.execute("SELECT id, provider, settings_json FROM tts_provider_settings")
cursor.execute("SELECT id, provider, settings_json FROM stt_provider_settings")

# Check session usage (reveals what models were actually used)
cursor.execute("SELECT model, provider, input_tokens, output_tokens FROM session_usage ORDER BY rowid DESC LIMIT 10")

# Check model_context (empty = no custom model context limits registered)
cursor.execute("SELECT * FROM model_context")

# Check provider model catalog cache (shows all models discovered per provider)
# File: ~/.hermes-web-ui/cache/provider-model-catalog.json
```
```

## Reading Hermes Web UI config.json

```bash
cat /c/Users/Administrator/.hermes-web-ui/config.json | python -m json.tool
```

Key field to check: `modelVisibility` — controls which models are shown in the Web UI dashboard dropdown.
