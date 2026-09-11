# Hermes Cron Management — Pitfalls & Patterns

## Script Path Resolution (Windows)

Hermes cron resolves `--script` relative to `%LOCALAPPDATA%/hermes/scripts/`, NOT from the cron's `--workdir`. This means:

- If your scripts live in `D:/Hermes agent/scripts/` (repo), cron won't find them
- `--workdir` only sets the CWD for execution, not the script lookup path
- Using `--workdir` with a Windows path that differs from AppData creates silent "Script not found" errors

### Solution: Directory Junction

On Windows, create a junction so AppData/hermes/scripts points to your repo scripts:

```python
import os, ctypes
appdata_scripts = os.path.join(os.environ['LOCALAPPDATA'], 'hermes', 'scripts')
repo_scripts = r'D:\Hermes agent\scripts'

# Delete existing directory first (must be empty)
# Then create junction via kernel32
kernel32 = ctypes.windll.kernel32
kernel32.CreateSymbolicLinkW(appdata_scripts, repo_scripts, 0x1)
```

- `0x1` = directory symlink/junction flag
- After creation, both paths point to the same files — no more dual-path sync
- The junction survives reboots and Hermes restarts

## `hermes cron create` Syntax

The schedule is a **positional argument**, not a flag:

```bash
# ✅ Correct
hermes cron create --name "task" --script "script.py" --no-agent "*/5 8-22 * * *"

# ❌ Wrong
hermes cron create --name "task" --script "script.py" --schedule "*/5 8-22 * * *"
```

This also applies to `hermes cron edit`:
```bash
hermes cron edit JOB_ID --schedule "30 12 * * *"
# (edit accepts --schedule as flag)
```

## Sleep-Hour Scheduling

To silence frequent cron jobs during sleep hours (23:00–08:00), use a cron expression instead of interval:

```bash
# Every 5 minutes, only 8:00–22:55
hermes cron create --name "daytime-task" --script "task.py" --no-agent "*/5 8-22 * * *"

# Last run: 22:55, next run: 08:00 — no pushes during 23:00–07:55
```

## no_agent Mode

When `--no-agent` is set:
- The script IS the job — its stdout is delivered verbatim
- Empty stdout = silent (no push to Telegram)
- Good for: position monitors, health checks, data cleanup
- Bad for: tasks that need LLM reasoning

## Common Pitfalls

1. **Deleting a cron doesn't remove it from jobs.json in AppData** — check with `hermes cron list` (shows active) vs the raw `%LOCALAPPDATA%/hermes/cron/jobs.json` (may still contain paused/deleted entries)
2. **Paused jobs still appear in Web UI** — use `hermes cron delete ID` to fully remove
3. **`hermes cron tick` runs due jobs once** — for testing, but won't reset `last_run_at` if not due
4. **`hermes cron run ID` queues for next tick** — doesn't run immediately
