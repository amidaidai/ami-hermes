# Watchdog Popen.poll() AttributeError Fix (v1.3 · 2026-06-21)

## Symptom
```
启动失败: 'P' object has no attribute 'poll'
```
Watchdog tries to restart monitor → `proc.poll()` fails → counts as restart → rate limit triggers → system unmonitored.

## Root Cause
`subprocess.Popen` on certain Windows environments (especially when launched with `creationflags=subprocess.CREATE_NO_WINDOW`) returns an incomplete object whose `.poll()` method is missing or corrupted. The `poll()` call on line 235 of `watchdog.py` raises `AttributeError: 'P' object has no attribute 'poll'`.

## Fix Pattern (scripts/watchdog.py L232-248)

```python
time.sleep(3)
# v1.3: Popen may return incomplete object on Windows
try:
    if proc.poll() is not None:
        reason = f"启动失败: 行情守望提前退出 code={proc.returncode}"
        log(reason)
        write_watchdog_state(status="failed", last_restart_reason=reason)
        return False
except AttributeError:
    # Popen object incomplete → fallback to pid check
    if not pid_alive(proc.pid):
        reason = f"启动失败: 进程未存活 pid={proc.pid}"
        log(reason)
        write_watchdog_state(status="failed", last_restart_reason=reason)
        return False
```

## Recovery After Rate Limit
When watchdog guard hits limit:
```bash
echo '{"restart_times":[],"restart_times_emergency":[]}' > data/watchdog_guard.json
```
Watchdog resumes on next check cycle.

## Verification
- `Popen.poll()` wrapped in try/except AttributeError ✓
- `pid_alive()` fallback handles incomplete Popen objects ✓
- Guard reset clears rate limit post-fix ✓
