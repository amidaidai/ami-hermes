# Cron-Based Report Delivery Pattern

Pattern used when a user wants automated daily/weekly reports delivered to messaging platforms.

## Architecture

```
Python data script → Markdown/JSON report → cron job → Discord/Telegram
```

## Recipe: New Daily Report

### 1. Write the data collector script

```python
# sandbox/my-system/report.py
import json, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPORT_DIR = Path(os.environ.get("OUTPUT_DIR",
    Path.home() / "AppData/Local/hermes/my-reports"))
REPORT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    # Collect data from APIs
    data = {...}

    # Generate markdown report
    now = datetime.now(timezone(timedelta(hours=8)))
    md = f"# My Report\n\n**{now.strftime('%Y年%m月%d日')}**\n\n..."
    
    fp = REPORT_DIR / f"report-{now.strftime('%Y%m%d')}.md"
    fp.write_text(md, encoding="utf-8")
    print(f"Report → {fp}")

if __name__ == "__main__":
    main()
```

### 2. Test standalone

```bash
python sandbox/my-system/report.py
```

### 3. Create cron job

Use the `cronjob` tool (action='create'):

| Field | Value |
|---|---|
| `name` | Descriptive Chinese name |
| `schedule` | `0 9 * * *` (daily at 9am) |
| `deliver` | `origin` (deliver to message origin) |
| `enabled_toolsets` | `["terminal", "file"]` (minimal needed tools) |
| `prompt` | Steps: 1. Run the Python script 2. Read the generated report 3. Send via send_message to Discord 4. Confirm done |

### 4. Verify

After creating, check `next_run_at` in the response. Use `cronjob(action='run', job_id=...)` for a one-off manual test run.

## Cron Schedule Reference

| Schedule | Meaning |
|---|---|
| `0 9 * * *` | Every day at 9:00 AM |
| `30 9 * * *` | Every day at 9:30 AM |
| `0 18 * * 5` | Every Friday at 6:00 PM |
| `0 8 * * 1` | Every Monday at 8:00 AM |

## Anti-Patterns

- Don't put all data collection logic in the cron prompt — keep it in the Python script.
- Don't use `background=true` for reports — cron handles scheduling.
- Don't make the cron prompt too complex — "run script X, read output, send to Discord" is sufficient.
- For financial data: always READ-ONLY. Never put trade execution in automated scripts.
