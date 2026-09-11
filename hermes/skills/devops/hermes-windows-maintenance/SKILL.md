---
name: hermes-windows-maintenance
description: "Update and keep healthy the Hermes Agent install on this Windows box when the Tangxi trading daemons (btc_daemon.py, 行情守望.py) and multiple Hermes Studio desktop instances are running. Covers venv .pyd lock diagnosis, safe process killing under git-bash, force-venv fallback, daemon-relaunch multiplication pitfalls, and post-update verification."
version: 1.0.0
author: Tang Xi / 安禾
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [hermes, windows, update, maintenance, venv, daemon, tangxi]
---

# Hermes Windows Maintenance (update + daemon coordination)

## When to use this skill
- User runs `hermes update` (or you need to) on this Windows host.
- `hermes update` aborts with "Other Hermes processes are running from this install's venv" and lists PIDs.
- After an update you must restore the Tangxi trading daemons (btc_daemon, 行情守望) without multiplying them.
- You suspect stale/duplicate daemon or binance-mcp instances locking the venv.

## Core mental model — the lock chain
`hermes update` rewrites venv native libs (`.pyd`). On Windows those files are locked by any running python process that imported them. The update ABORTS (clean, by design) if it finds:
- the **Hermes desktop backend** (`tools/binance-mcp/server.py` from `hermes-agent/venv`) — this IS the current session's host;
- **Tangxi daemons** launched with the venv python: `scripts/btc_daemon.py`, `scripts/行情守望.py -s BTCUSDT XAUUSD`.

Critical facts (learned the hard way):
1. **Exiting the desktop does NOT kill the Tangxi daemons.** They are independent `python.exe` processes with unrelated parents (not children of the desktop). The desktop only owns `binance-mcp/server.py`.
2. **Multiple Hermes Studio instances multiply daemons.** Each `Hermes Studio.exe` pulls its own `binance-mcp` backend + daemon set. 6 desktop instances → 4+ binance-mcp, 2+ btc_daemon. This is the usual root cause of "locked venv" — not a single stray process.
3. **The daemons are auto-managed by the desktop/gateway runtime.** They reappear after `hermes update`'s "Restarting Windows gateway profile(s)" step WITHOUT any manual launch. Do NOT manually relaunch them — `background=true` launching stacked duplicates on top of the auto-relaunched set (observed: 1 launch → 5 btc_daemon instances).
4. **`nohup`/`disown`/`setsid` are blocked** by the Hermes terminal (returns an error telling you to use `background=true`). But `background=true` for a daemon is exactly what causes duplication — so prefer letting the desktop manage daemons entirely.

## Procedure
### 1. Diagnose the lockers (run from the in-session terminal)
Use PowerShell (not `tasklist | grep`, and NEVER `taskkill /PID` under git-bash — bash mangles `/PID` into a path). Filter by `Name -eq 'python.exe'` to avoid the query command matching itself:

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -like '*btc_daemon*' -or $_.CommandLine -like '*行情守望*' -or $_.CommandLine -like '*binance-mcp*') } | Select-Object ProcessId,CommandLine | Format-List
# count desktop instances:
(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'Hermes Studio*' }).Count
```

### 2. Decide the path (present to user)
- **Clean path (preferred):** user exits ALL `Hermes Studio.exe` instances (task manager or `Stop-Process`), then runs `hermes update` in a SEPARATE terminal. Zero risk, daemons relaunch automatically on next desktop start. NOTE: this ends the current session, so the verify/relaunch steps happen in a fresh session.
- **Force path (current session must survive):** `hermes update --force-venv`. It skips locked `.pyd` replacement and may leave the update partial if a native lib couldn't be swapped. Always follow with `hermes doctor` and, if damaged, schedule a clean full exit+update.

You may safely `Stop-Process` the standalone Tangxi daemons (they auto-relaunch with the desktop) but NEVER kill the `binance-mcp/server.py` that hosts the active session — it disconnects the conversation.

```powershell
# stop standalone Tangxi daemons only (safe; they relaunch with desktop)
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -like '*btc_daemon*' -or $_.CommandLine -like '*行情守望*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
```

### 3. Verify the update
```bash
hermes --version        # expect newer build + "Up to date"
hermes doctor           # "All checks passed!" — ⚠ optional modules (browser-cdp, discord, spotify, etc.) are NOT failures
```
Web UI build errors during update (e.g. `error TS7016: Could not find a declaration file for module 'qrcode'`, `Cannot find module '@vitejs/plugin-react'`) are LOCAL, pre-existing TS config issues. The updater serves the stale `dist` as fallback — the desktop still works; core Python is fine. Do not chase these unless the user reports a broken UI.

### 4. Restore daemons (only if user explicitly wants them back NOW)
Let the desktop relaunch them — just start ONE clean Hermes Studio instance. Do NOT `background=true` launch `btc_daemon.py` / `行情守望.py` yourself; it duplicates. If a genuinely dead state exists, confirm zero instances first (step 1), then start a single desktop instance and verify exactly one of each daemon appears.

## venv native-lib breakage: pydantic-core version conflict (not update-related)

**Symptoms:** `hermes doctor` dies with `SystemError: The installed pydantic-core version (2.48.0) is incompatible with the current pydantic version, which requires 2.46.4`. ANY new Hermes process fails at import — CLI, gateway restart, model switching (spawns a new session), cron dispatch. Long-running processes (an already-open Web UI session) keep working because modules are loaded in memory. **This asymmetry is the tell: "old session fine, everything new crashes" = venv native-lib breakage, not a config problem.**

**Root cause:** a stray `pip install` into the hermes venv upgraded `pydantic-core` (2.46.4 → 2.48.0) while `pydantic` stayed pinned at 2.13.4 (which requires core 2.46.4). site-packages then holds BOTH `pydantic_core-2.46.4.dist-info` and `pydantic_core-2.48.0.dist-info`; `pip show` may even report 2.46.4 while `import` reads 2.48.0 from the `.pyd`.

Diagnose:
```bash
cd "$(dirname "$(hermes config path)")/hermes-agent"
./venv/Scripts/python -c "import pydantic_core, pydantic; print(pydantic_core.__version__, pydantic.__version__)"  # fails w/ SystemError
ls venv/Lib/site-packages | grep -i pydantic_core   # two dist-info dirs = collision
```

Fix (restore the pinned core; the intended pin lives in `pyproject.toml`):
```bash
./venv/Scripts/python -m pip install --force-reinstall --no-deps "pydantic-core==2.46.4"
rm -rf venv/Lib/site-packages/pydantic_core-2.48.0.dist-info   # remove stale metadata
```

Verify: `./venv/Scripts/python -c "import pydantic, pydantic_core, openai; print('OK', pydantic.__version__, pydantic_core.__version__)"` then `hermes doctor` → all green. Also re-check MCP servers launched with `command: python` (e.g. binance-mcp) — they die with `Failed to connect ... Connection closed` for the same reason and come back once the venv imports cleanly.

Pitfall: **don't `pip install` upgrades into the hermes venv casually** — it is deliberately pinned (pyproject.toml comments explain e.g. pydantic 2.13.4 → core 2.46.4 to fix an OpenAI-SDK segfault). If a package genuinely needs a newer core, re-pin BOTH in pyproject and let `hermes update` handle it.

Full observed transcript: `references/pydantic-core-version-conflict.md`.

## Pitfalls (what went wrong this session)
- **Heartbeat content `status:"running"` is NOT proof a daemon is alive — check the file's mtime.** A stale heartbeat from a *superseded* daemon generation reads as `running` for weeks. When deciding whether a daemon is "dead", first `stat -c %y data/monitor_heartbeat.json` and compare to `date`; if mtime is days/weeks old, the daemon that wrote it is NOT running regardless of what the JSON says (a watchdog that only reads content `status` but not mtime will never alert — that's how a "dead 44 days" daemon stays quietly `ok`).
- **Confirm which daemon generation is the CURRENT authority before declaring P0.** The daemon set MIGRATES: the old `行情守望.py` (→ `data/monitor_heartbeat.json`, cron `行情守望看门狗` 020e260f5ac0) was archived to `scripts/_archive/` and its watchdog cron is `enabled=False/paused` — that's a **completed migration, not a failure**. The current authority is `keylevel_guard.py` (→ `data/.keylevel_guard_heartbeat.json`, cron `BTC关键位守护看门狗`, config `data/keylevels_config.json`). A stale `monitor_heartbeat.json` + a live `.keylevel_guard_heartbeat.json` = old gen retired, new gen alive. Diagnosis: `hermes cron list` to read watchdog `enabled/state`, and `data/keylevels_config.json` to see which symbols are actually monitored.
- **psutil instance counts include the querying command itself** — filter out `bash -c`, `-c import psutil`, and current `os.getpid()` or you'll misread a healthy single daemon as multiple (or count zero when the authority is a different-named daemon).
- Assumed "exit desktop" kills everything → wrong; Tangxi daemons survived. Always re-scan before declaring the path clear.
- `taskkill /PID 11468 /F` under git-bash → "无效开关/PID" because bash parsed `/PID` as a path. Use PowerShell `Stop-Process -Id`.
- `nohup ... &` → terminal refused (shell-level background wrapper blocked). Use `background=true` ONLY for genuinely needed manual processes, never for the auto-managed daemons.
- `background=true` launching a daemon → 5× multiplication because desktop gateway had ALSO relaunched it. Trust the desktop's auto-management.
- Process query matched its own bash wrapper → always filter on `Name -eq 'python.exe'` and on a specific substring, not a bare regex over all CommandLines.
- **Double-Python interpreter trap on Windows (uv cpython) — 2026-09-02 confirmed P0.** When the Tangxi pipeline is launched from Hermes' `uv`-managed CPython (e.g. `C:\Users\Administrator\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe`), `auto_card.py:4806` and the cron `script` runner resolve to **that exact short-name path** — NOT to whatever `python` is first on `PATH` (which is `hermes-agent\venv\Scripts\python.exe`) and NOT to `uv python find` (which returned `cpython-3.12.13-windows-x86_64-none` on this box, a third interpreter). The terminal used to test the fix is therefore a **different interpreter from the one auto_card and cron actually use**. If `python -c "import requests"` succeeds in your shell but `auto_card` crashes with `ModuleNotFoundError: No module named 'requests'`, the interpreter the cron runner uses is missing the package even though yours has it. **Diagnosis 3-step (always run, never skip):**
  1. `crud jobs.json` → read the `script` field for the failing cron. In `auto_card`'s case `python auto_card.py BTCUSDT --full` is wrapped by the Hermes cron runner which uses `sys.executable` from the spawning interpreter.
  2. `python -c "import sys; print(sys.executable)"` IN THE TERMINAL you're about to use for the fix. Compare to the interpreter the auto_card traceback names (e.g. `D:\Hermes agent\scripts\auto_card.py", line 4806` tells you nothing — the traceback is the script path, not the interpreter).
  3. Probe the actual interpreter that ran: open a terminal that mimics cron — typically the bare `cpython-3.11-windows-x86_64-none\python.exe` path, not `python`. Run the same `import requests` test there. If THAT fails, fix the **interpreter the script actually uses**, not the one `python` resolves to in your shell.
  **The real interpreter on this box (2026-09-02):** `C:\Users\Administrator\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe`. `uv python find` returns 3.12.13 — **ignore it**; it is the default-pick interpreter, not the one any existing cron uses. `cpython-3.11-windows-x86_64-none` (Windows short name) and `cpython-3.11.15-windows-x86_64-none` (full name) both point to the same 3.11.1 binary. **Fix path for missing packages on this interpreter (use `--break-system-packages` because the uv cpython 3.11 is `externally managed`):** `"<the actual path>\python.exe" -m pip install --break-system-packages <pkgs>`. Common missing: `requests pydantic aiohttp numpy pandas websockets`. After install, verify with the same `<the actual path>\python.exe -c "import <pkg>"` — never with the bare `python` shell, which masks the bug. Reference: `references/uv-cpython-3-11-short-name-2026-09-02.md`.
- **uv cpython 3.11 is a stub — only setuptools+pip are pre-installed.** First `pip install` on it fails with `error: externally-managed environment` (because `uv python find` returns the wrong one) or `subprocess.CalledProcessError` (because `ensurepip` cannot fetch its bootstrap). The clean path: directly call `<the actual path>\python.exe -m pip install --break-system-packages <pkgs>`. The `Scripts` and `Lib/site-packages` dirs are created on demand; do not pre-create them. If you see `ensurepip` errors, your shell is the wrong interpreter — switch to the bare path and retry. Same verification rule as the pitfall above.
- **Diagnose which interpreter a failed cron / subprocess ACTUALLY used, not the one in your shell.** Trap recipe: have the failing script log `sys.executable` to a sentinel file on first call (or `print` it in a no-op wrapper). Then `cat` that file from any terminal — it tells you the interpreter that ran, regardless of what `python` resolves to locally. Saves a full round of "works in shell / fails in cron" debugging.

## References
- `references/venv-lock-recovery.md` — exact commands, the real `hermes update` lock message, and the observed instance-multiplication transcript.
- `references/pydantic-core-version-conflict.md` — full observed transcript of the pydantic-core 2.48.0 vs 2.46.4 breakage (symptoms, fix, verification), and why "model switching fails" can be a venv native-lib issue.
- `references/uv-cpython-3-11-short-name-2026-09-02.md` — the double-Python-interpreter trap: which interpreter `auto_card.py:4806` and cron `script` actually use, why `python` in the shell masks the bug, and the `--break-system-packages` install recipe.
