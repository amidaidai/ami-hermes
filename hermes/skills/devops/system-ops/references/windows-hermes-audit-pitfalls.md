# Windows Hermes Audit Pitfalls

Use this reference when running a comprehensive system/Hermes check from the Windows Git-Bash environment.

## Encoding

Windows commands such as `systeminfo`, `tasklist`, `wmic`, `ping`, and localized CLI output may emit GBK/ACP bytes. If a Python collector uses `subprocess.run(..., text=True)`, reader threads can crash with `UnicodeDecodeError` before evidence files are written.

Prefer byte capture and decode defensively:

```python
r = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
text = r.stdout.decode("utf-8", errors="replace")
```

## Shell selection

Inside a Python process on Windows, `subprocess.run(..., shell=True)` uses `cmd.exe`, not the Hermes terminal's Git-Bash shell. POSIX loops like `for u in ...; do ...; done` can fail with messages such as `unexpected u` or localized `u` errors.

For POSIX syntax, either:

- run the command directly through the `terminal` tool, or
- explicitly invoke Bash from Python, e.g. `subprocess.run(["bash", "-lc", script], ...)`.

## Curl timing

For network timing checks in Git-Bash, put the curl `-w` format in single quotes and run directly in the terminal, not through `cmd.exe`:

```bash
for u in https://api.deepseek.com/v1/models https://api.yairouter.com/v1/models; do
  echo "==== $u ===="
  curl -k -L -s -o /dev/null --connect-timeout 8 --max-time 20 \
    -w 'code=%{http_code} connect=%{time_connect} ttfb=%{time_starttransfer} total=%{time_total}\n' "$u"
done
```

## Reporting

Separate current runtime failures from historical log noise. Example: a gateway can be currently running while old `gateway-error.log` entries show prior Telegram connection timeouts.
