# uv cpython 3.11 short-name interpreter — install + verify recipe (2026-09-02)

> The exact interpreter that runs `auto_card.py` and the cron `script` runner on this Windows box. Confirmed via traceback + process inspection. `uv python find` returns the WRONG one.

## The interpreter that matters

```
C:\Users\Administrator\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe
```

- This is the **Windows short-name** path. Full name `cpython-3.11.15-windows-x86_64-none` points to the same 3.11.1 binary.
- This is the interpreter that runs when the cron `auto_card` job and similar `script:`-bearing jobs fire, and what `auto_card.py:4806` is actually launched with.
- `python` on PATH → `hermes-agent\venv\Scripts\python.exe` (different interpreter, has packages).
- `uv python find` → `cpython-3.12.13-windows-x86_64-none` (yet a third interpreter, the default-pick).

## Symptom that exposes the trap

`python -c "import requests"` succeeds in the terminal (because `python` → hermes venv has it), but `auto_card` exits with:

```
ModuleNotFoundError: No module named 'requests'
  File "D:\Hermes agent\scripts\auto_card.py", line 3841, in _collect_binance_data
  File "D:\Hermes agent\scripts\auto_card.py", line 2550, in <module>
    import requests, time as _time, hmac, hashlib, urllib.parse
```

The traceback is the **script path** — the interpreter is not in the traceback. The only way to confirm is to print `sys.executable` from a wrapper or to probe the bare path.

## Why `uv pip install` fails first

```
$ uv pip install -p "$(uv python find)" requests
Using Python 3.12.13 environment at: ...cpython-3.12.13-windows-x86_64-none
error: The interpreter ... is externally managed, and indicates the following:
  This Python installation is managed by uv and should not be modified.
hint: Consider creating a virtual environment, e.g. with `uv venv`.
```

`uv pip install` against the short-name path also fails (externally-managed). The 3.11 short-name interpreter is **stub-grade** — only `setuptools` + `pip` are pre-installed. `ensurepip -m ensurepip` returns `subprocess.CalledProcessError` because it cannot fetch its bootstrap into the externally-managed env.

## The fix that actually works

Call pip on the bare interpreter path with `--break-system-packages`:

```bash
"C:/Users/Administrator/AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe" \
    -m pip install --break-system-packages \
    requests pydantic aiohttp numpy pandas websockets
```

Common warnings to ignore:
- `WARNING: The script websockets.exe is installed in '...Scripts' which is not on PATH.` — expected, those `.exe` shims are not needed.
- `WARNING: The scripts f2py.exe and numpy-config.exe ...` — same.

Result on this box (2026-09-02):
```
Successfully installed aiohappyeyebbles-2.7.1 aiohttp-3.14.3 ... requests-2.34.2 ... pydantic-2.13.5 ...
```

## Verification (must use the same interpreter)

```bash
"C:/Users/Administrator/AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe" \
    -c "
import requests, pydantic, aiohttp, numpy, pandas, websockets
print('OK:', requests.__version__, pydantic.VERSION, aiohttp.__version__, numpy.__version__, pandas.__version__, websockets.__version__)
"
```

**Do NOT** verify with `python -c "import requests"` from the terminal — that goes through the hermes venv and masks the bug. The whole point of the trap is that the shell's `python` and the cron runner's `python` are different binaries.

## End-to-end test (proves the cron runner now has the packages)

```bash
"C:/Users/Administrator/AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe" \
    "D:/Hermes agent/scripts/auto_card.py" BTCUSDT --quick
```

Expected: exit 0, no `ModuleNotFoundError`. Pipeline emits the standard 3-step completion table.

## Pin this for next time

The interpreter path is stable across `hermes update` cycles (it's a uv-managed install, not the hermes venv). If the path ever changes, re-discover it with:

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*auto_card*' } | Select-Object -First 1 -ExpandProperty ProcessId
# then read its full command line including the python.exe path
```

Or, on the next trap, just add to the failing script's top:

```python
import sys, json
from pathlib import Path
Path('data/_last_interpreter.json').write_text(json.dumps({'executable': sys.executable, 'version': sys.version}))
```

Then `cat data/_last_interpreter.json` from any shell gives you the absolute truth.
