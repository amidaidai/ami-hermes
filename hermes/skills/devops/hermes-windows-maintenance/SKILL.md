---
name: hermes-windows-maintenance
description: "Update and keep healthy the Hermes Agent install on this Windows box while Tangxi trading daemons (btc_daemon.py, 行情守望.py), Hermes Studio desktop instances, and the Studio agent-bridge (hermes_bridge.py — the live session host) are running. Covers venv .pyd lock diagnosis, ancestry checks before killing, --force-venv semantics from the updater source, detached update launching, daemon-relaunch multiplication pitfalls, and post-update verification."
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
- `hermes update` aborts with `Another hermes.exe is running: PID xxxx` (usually the transient updater itself — re-scan before acting on it).
- You must decide whether the update can survive in the current session, or state exactly what the user has to close.

## Core mental model — the lock chain
`hermes update` rewrites venv native libs (`.pyd`). On Windows those files are locked by any running python process that imported them. The update ABORTS (clean, by design) if it finds:
- the **Hermes desktop backend** (`tools/binance-mcp/server.py` from `hermes-agent/venv`) — this IS the current session's host;
- **Tangxi daemons** launched with the venv python: `scripts/btc_daemon.py`, `scripts/行情守望.py -s BTCUSDT XAUUSD`.

Critical facts (learned the hard way):
1. **Exiting the desktop does NOT kill the Tangxi daemons.** They are independent `python.exe` processes with unrelated parents (not children of the desktop). The desktop only owns `binance-mcp/server.py`.
2. **Multiple Hermes Studio instances multiply daemons.** Each `Hermes Studio.exe` pulls its own `binance-mcp` backend + daemon set. 6 desktop instances → 4+ binance-mcp, 2+ btc_daemon. This is the usual root cause of "locked venv" — not a single stray process.
3. **The daemons are auto-managed by the desktop/gateway runtime.** They reappear after `hermes update`'s "Restarting Windows gateway profile(s)" step WITHOUT any manual launch. Do NOT manually relaunch them — `background=true` launching stacked duplicates on top of the auto-relaunched set (observed: 1 launch → 5 btc_daemon instances).
4. **`nohup`/`disown`/`setsid` are blocked** by the Hermes terminal (returns an error telling you to use `background=true`). But `background=true` for a daemon is exactly what causes duplication — so prefer letting the desktop manage daemons entirely.
5. **The current session host is NOT always `binance-mcp/server.py`.** On this box (2026-09-13) it was the **Studio agent-bridge** (`hermes_bridge.py --worker-profile default`) — a different process in a different tree. Always walk your own ancestry chain before killing a candidate locker; see the dedicated section below.
6. **`hermes update` pauses the Windows gateway BEFORE it runs the venv-holder guard.** If it then aborts, the gateway is left DOWN until the update succeeds or the desktop restarts it — Telegram/other platform doors are offline in the meantime. Say so explicitly in your status report.

## The Studio agent-bridge lock class (2026-09-13 — current-session host)
The locker is not necessarily `binance-mcp/server.py`. On this box the live conversation ran as:

```
Ekko Studio.exe 10644  (child of Ekko Studio.exe 16276 --updated, child of explorer.exe)
└─ python.exe  venv/Scripts/python.exe "...\Ekko Studio\resources\webui\dist\server\agent-bridge\python\hermes_bridge.py"
              --worker-profile default --endpoint tcp://127.0.0.1:30317
   └─ python.exe  uv cpython-3.11  (same bridge, re-exec layer)
      └─ powershell.exe → bash.exe ×3 → the `terminal` tool
```

Two sibling trees co-existed: one under the **gateway** (`hermes_cli.main gateway run --replace`, cleanly stopped by the update's own pause step) and one under the **Studio agent-bridge**, which survives and is what the update then chokes on. The second tree also owns its own `binance-mcp/server.py` pair plus the desktop node children (tradingview-mcp, webui).

**Walk your own ancestry before killing anything.** If `hermes_bridge.py` — or the `binance-mcp` inside its tree — is an ancestor of your `terminal` process, killing it ends the conversation:

```powershell
$cur = $PID
for ($i=0; $i -lt 12; $i++) {
  $p = Get-CimInstance Win32_Process -Filter "ProcessId=$cur" -ErrorAction SilentlyContinue
  if (-not $p) { break }
  Write-Output ("{0,-8} {1,-20} {2}" -f $p.ProcessId, $p.Name, $p.CommandLine)
  $cur = $p.ParentProcessId
}
```
`$PID` is the **PowerShell** pid when run via `powershell -File`; the chain still reaches the real host (powershell ← bash ×3 ← the python bridge).

### Authoritative semantics — read from `hermes_cli/update_cmd.py` (~line 1302)
> Any venv python still running (typically the Desktop `hermes serve` backend) keeps .pyd locked and would corrupt the sync; refuse rather than race (**the app respawns a killed backend**). NOT bypassed by `--force` (desktop updater, shim guard only); `--force-venv` is.

Do not re-derive these by trial and error:
- **Killing the backend is futile.** Studio respawns it and the update re-locks.
- **`--force` does NOT clear the venv guard** (only the `hermes.exe` shim guard).
- **`--force-venv` clears the guard, not the problem** — the dependency sync then writes into locked `.pyd`. Only for small deltas, with the user explicitly accepting the risk.
- `_abort_dependency_sync_if_self_locked()` runs *after* the code swap, right before the dependency sync (it excludes the updater process by design).

### Read-only pre-flight — run these first, always
```bash
hermes update --plan     # install kind + every running Hermes service (pid, supervisor, version) + how each restarts. Read-only, safe on a live fleet.
hermes update --check    # update availability only; changes nothing.
hermes update --help     # --yes --no-backup --backup --keep-stash --force --force-venv --branch
```
`--plan` is the fastest way to learn which gateway/PID the update intends to restart.

### Surviving the update: launch it DETACHED
Any process started with `terminal(background=true)` is a child of the session host and dies when the user closes Studio. Launch through Windows instead:

```powershell
Start-Process -FilePath 'powershell.exe' `
  -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\Administrator\AppData\Local\hermes\outputs\update-when-idle.ps1' `
  -WindowStyle Hidden -PassThru | Select-Object -ExpandProperty Id
```

`scripts/update-when-idle.ps1` (in this skill) is the ready-made version: polls until no venv holder **and** no `Ekko Studio.exe` / `Hermes Studio.exe` remains (45-min cap, then exits without touching anything), asserts the holders did not respawn, then runs `hermes update --yes --no-backup`, timestamping every line and logging the pre/post git HEAD.

Then give the user ONE message containing: (1) fully exit Studio — **tray icon → 退出**, not just closing windows; (2) the watcher starts the update by itself; (3) reopen Studio afterwards so `hermes doctor` can run in a fresh session; (4) the log path so they can watch progress.

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
- **Force path (only for a SMALL delta):** `hermes update --force-venv`. It clears the venv-holder guard, but the dependency sync then writes into locked `.pyd` files and can leave the venv half-updated. For a jump of thousands of commits this is not a "save the session" button — take the clean path. `--force` does NOT clear the venv guard at all (shim guard only). See the source-code semantics section below.

You may safely `Stop-Process` the standalone Tangxi daemons (they auto-relaunch with the desktop) but NEVER kill the `binance-mcp/server.py` that hosts the active session — it disconnects the conversation.

```powershell
# stop standalone Tangxi daemons only (safe; they relaunch with desktop)
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -like '*btc_daemon*' -or $_.CommandLine -like '*行情守望*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
```

### 3. Verify the update — run the FULL sweep, never just `hermes doctor`
`hermes doctor` passing is necessary and nowhere near sufficient. The update re-pins venv deps, which silently kills python MCP servers (see the fastmcp section) and can leave every platform reading `connected` while a data path is dead. When the user asks "is it all fixed now?", answer with tool output, not an assertion — run the sweep and report the table.

| Check | Command | Pass looks like |
|---|---|---|
| Version + real HEAD | `hermes --version`; `git -C <install dir> log -1 --format="%h %ad %s" --date=short` | new build + `Up to date`; HEAD = the new commit (the workspace repo's HEAD is NOT the install's — check the install dir) |
| Gateway (from state files) | `cat "$LOCALAPPDATA/hermes/gateway_state.json"` | `gateway_state: running`, every platform `connected` |
| Cron freshness | `hermes cron list` (grep `Name:` / `Last run:`) | every job `ok`, last runs within a few minutes — this is also the proof the gateway/cron ticker survived |
| Python MCP server | `hermes mcp test binance` | `✓ Connected` **and** the tool list (binance: 15 tools) |
| TV MCP | `hermes mcp test tradingview` | `✓ Connected` **and** 78 tools |
| **Trading heart** | `tv_health_check`, then `data_get_pine_tables` | `cdp_connected` + `api_available` true; chart = the expected symbol/TF; **both** the SVP main table and the AggVol sub table return live rows |
| Feishu sidecar | HTTP GET `http://127.0.0.1:8765/health` | `healthy` + a `process_pid` |
| Static integrity | `python scripts/maintenance/local_integrity_audit.py` | `{"ok": true}`, 0 syntax errors, no missing contract files |
| Skill drift | `python scripts/maintenance/skill_drift_scan.py` | `LIVE 0` — historical counts are expected and fine |
| User's working repo | `git status --short` in the project repo | the pre-update uncommitted files, byte-for-byte unchanged |

Two rules behind the table:
- **`hermes mcp test` reporting "Tools discovered: N" is not proof the server works** — it proves the handshake. A stdio python server that crashes on import can still surface a healthy-looking tool list, so only an actual tool *call* on the data path (here: reading the two Pine tables) proves the chain end to end.
- **Verify the install's own HEAD, not the workspace repo's.** Any `git rev-parse`/`git log` run from the project directory reports the project's history and will look "unchanged" after an update — always resolve paths against the install dir (`Install directory:` in `hermes --version`).

Web UI build errors during update (e.g. `error TS7016: Could not find a declaration file for module 'qrcode'`, `Cannot find module '@vitejs/plugin-react'`) are LOCAL, pre-existing TS config issues. The updater serves the stale `dist` as fallback — the desktop still works; core Python is fine. Do not chase these unless the user reports a broken UI.

### 4. Restore daemons (only if user explicitly wants them back NOW)
Let the desktop relaunch them — just start ONE clean Hermes Studio instance. Do NOT `background=true` launch `btc_daemon.py` / `行情守望.py` yourself; it duplicates. If a genuinely dead state exists, confirm zero instances first (step 1), then start a single desktop instance and verify exactly one of each daemon appears.

## 2026-09-13 update run: the force path that actually worked (v0.20.6 → v0.21.2)

Observed on this box with **Ekko Studio (Hermes Studio) hosting the live session**. Ekko Studio's session host is a chain of venv-python + uv-python `agent-bridge` processes (`Ekko Studio.exe` → `venv\Scripts\python.exe` agent-bridge → uv python → ... → the session's python). Those venv holders can never be closed while you work from inside them, so the clean `exit-desktop` path is unavailable and **`--force-venv` is the only in-session option** — but it is safe when you check what the dependency sync will actually rewrite first.

### Pre-flight: will the dep sync touch a locked file at all?
`hermes update` only replaces a distribution whose pin changed. Compare the target pyproject against the installed versions before running:
```bash
cd "$LOCALAPPDATA/hermes/hermes-agent"
git show origin/main:pyproject.toml > "$LOCALAPPDATA/Temp/up_pyproject.toml"
diff pyproject.toml "$LOCALAPPDATA/Temp/up_pyproject.toml" | head -40     # base deps + extras pins
./venv/Scripts/python.exe -c "import importlib.metadata as m; print(m.version('nemo-relay'))"
```
Then check whether any running venv process has the at-risk native module mapped (a loaded `.pyd` blocks REPLACE on Windows):
```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*hermes-agent\venv\Scripts\python.exe*' } | ForEach-Object {
  $p=$_.ProcessId
  Get-Process -Id $p | Select-Object -ExpandProperty Modules | Where-Object { $_.FileName -like '*nemo_relay*' -or $_.FileName -like '*brotli*' }
}
```
2026-09-13 result: only `nemo-relay` (0.7.3 → 0.8.4), `brotlicffi`, `slack-sdk` changed, **none of them mapped in any live process** → the sync completed cleanly (`✓ Dependencies repaired!`, `Installed 5 packages`) with no deferral marker.

### Local uncommitted patches: `git stash` is BLOCKED in-session
`git stash` (and anything resembling it) is refused by the Hermes terminal guard on the live checkout — "would rewrite Hermes's live source checkout". Do **not** try to pre-stash. Instead:
1. Back the work up by hand:
   ```bash
   BK="$LOCALAPPDATA/hermes/workspace/outputs/pre_update_hermes_$(./venv/Scripts/python.exe -c "from datetime import datetime;print(datetime.now().strftime('%Y%m%d_%H%M%S'))")"
   mkdir -p "$BK" && git diff > "$BK/local_patches.diff" && git rev-parse HEAD > "$BK/HEAD_before.txt"
   cp --parents <each modified file> "$BK/" ; cp <untracked files> "$BK/"
   ```
2. Run the update with **`--keep-stash`** (`hermes update --force-venv --yes --keep-stash`): the updater autostashes tracked+untracked changes, fast-forwards, and leaves everything parked in `stash@{0}` (`hermes-update-autostash-<ts>`) so nothing conflicts or silently rides along.
3. Restore what still applies by hand and drop the rest (see below). Untracked files that the autostash swept out of the tree (e.g. `.hermes_feishu_card_manifest`) must be copied back from the backup dir.
4. **Check upstream first** before re-applying any patch — half of them are usually superseded:
   ```bash
   git show origin/main:<file> | grep -n "<the patched symbol>"
   ```
   2026-09-13: both local Windows loop-tick patches (`gateway/shutdown_watchdog.py`, `hermes_cli/gateway.py`) were **already upstream** in v0.21.2 (renamed: heartbeat key `loop_tick_tcp_port`, `os.name == "posix"` branch, `_probe_loop_tick_tcp`). Dropped them. Only the TG CJK-rich patch was still needed and had to be re-expressed against the refactor (`_rich_content_ok(content, *, allow_cjk_rich=False)` + `_rich_eligible` passing `allow_cjk_rich=True`).

### Post-update: stale `__pycache__` breaks the restarted gateway (🔴 silent)
The update's own "Restarting Windows gateway profile(s)" step can start a gateway **while the checkout is mid-swap**, which compiles `.pyc` files from a mixed tree. The next launch then trusts those caches and dies with **compile-time ImportErrors that `hermes doctor` and `hermes --version` never surface**:
```
ImportError: cannot import name '_dict_slot' from 'gateway.config'
ImportError: cannot import name 'cache_image_from_bytes_async' from 'gateway.platforms.base'
ERROR gateway.run: Platform 'discord' is registered but adapter creation failed
```
Both names DO exist in the new on-disk files — the module object is stale. Fix:
```bash
cd "$LOCALAPPDATA/hermes/hermes-agent"
find . -name "__pycache__" -type d -not -path "./venv/*" -not -path "*/node_modules/*" -exec rm -rf {} +
./venv/Scripts/python.exe -c "from gateway.config import _dict_slot; from gateway.platforms.base import cache_image_from_bytes_async; import gateway.run; print('OK')"
hermes gateway restart
```
Then confirm from the log: `Gateway running with N platform(s)` and no fresh `adapter creation failed`.

### Verify the gateway from state files, not `hermes gateway status`
`hermes gateway status` printed "✗ Gateway is not running" while `gateway_state.json` showed a live pid and `state/gateway.heartbeat` was fresh — v0.21.x no longer writes `gateway.pid` / `gateway.lock`. Trust:
```bash
cat "$LOCALAPPDATA/hermes/gateway_state.json"      # pid, gateway_state, code_version, per-platform state
cat "$LOCALAPPDATA/hermes/state/gateway.heartbeat" # freshness + loop_tick_tcp_port (proves the Windows witness is armed)
hermes cron status                                 # ticker heartbeat + next run
```
A healthy post-update gateway shows `code_version` = the new version, every platform `connected`, and `loop_tick_tcp_port` non-null.

### Daemon truth after the update = heartbeat mtime, not "it disappeared"
The update's gateway pause kills gateway-child processes, so a process scan afterwards always looks alarming. Compare against pre-update reality:
- `keylevel_guard.py` (uv python) — **current authority**, alive, `.keylevel_guard_heartbeat.json` fresh; supervised by cron `BTC关键位守护看门狗` every 2 min.
- `btc_daemon.py` — heartbeat `.btc_daemon_heartbeat.json` stale since **2026-08-30**: long dead, not update damage.
- `行情守望.py` — heartbeat `monitor_heartbeat.json` stale since **2026-07-16**: retired migration, watchdog cron paused.
- feishu card sidecar (`~/.hermes_feishu_card/sidecar.pid`, port 8765) — **this IS the live path for card pushes** (棠溪 sends cards via the sidecar API, deliberately bypassing the gateway hook). It dies silently, has no watchdog cron, and is NOT relaunched by the desktop. After every update poll `http://127.0.0.1:8765/health`; on `WinError 10061` relaunch it detached:
  ```powershell
  Start-Process -FilePath "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\python.exe" `
    -ArgumentList '-m','hermes_feishu_card.runner','--config','C:\Users\Administrator\.hermes_feishu_card\config.yaml','--token','<token from sidecar.pid>' `
    -WindowStyle Hidden
  ```
  Then rewrite `sidecar.pid` with `{"pid": <process_pid from /health>, "token": <same token>}` — the file goes stale otherwise. Do NOT pass `-RedirectStandardOutput` together with a long-running child: `Start-Process` then blocks the calling shell (observed 240s terminal timeout even though the sidecar came up fine — verify via `/health` instead of waiting on the launcher).
- **The feishu gateway-hook patch breaks on Hermes updates that refactor `gateway/`. The fix is to UPGRADE THE PLUGIN, not to hand-patch the AST.** v0.21.2 split `gateway/run.py`: the handler moved to `gateway/run_turn.py`, final delivery was extracted into `_hmwa_deliver_turn_response` (L~1760, its `return response` at L~1798), and cron delivery split into `cron/scheduler_delivery.py`. Symptom on an out-of-date plugin: `hermes-feishu-card doctor` → `Hermes: unsupported` + `gateway/run.py missing async anchor function: _handle_message_with_agent`. Order of work:
  1. `cd <plugin clone>; git fetch origin main; git log origin/main --oneline -5`. A `git fetch --dry-run` does **not** advance `origin/main`, so `git log origin/main` still shows the stale tip — fetch for real before concluding the plugin is up to date (this box was 3.6.1 while upstream was already 4.4.5).
  2. Upstreams that support the split carry `patcher.DECOMPOSED_GATEWAY_TARGETS` = `run_turn.py`, `run_turn_runner.py`, `run_inbound.py`, `run_busy.py`, `run_startup.py`, `run_notifications.py`, plus `cron/scheduler_delivery.py` and `gateway/platforms/base.py`. If present: `git stash push -m ... -- <locally modified files>` then `git merge --ff-only origin/main` (the plugin clone lives under `sandbox/`, which is gitignored by the workspace repo and is its own repo, so this cannot dirty the user's tree).
  3. Re-run `hermes-feishu-card doctor`. `compatibility full` means the moved anchors were found. A remaining `gateway/platforms/base.py exact delivery anchors are unsupported` is an **upstream-not-caught-up** condition, not a config error: the plugin's `apply_base_patch` AST contract for the exact-delivery ledger no longer matches this Hermes build. **Do not force a partial patch.** On the split files `apply_patch` inserts only the *start* block at the handler entry, where `locals()` still lacks `response`/`agent_result` — the card would open and then never complete, which is worse than no patch. Leave the hook uninstalled (a clean, non-lying state) and use direct sidecar sends, which need no hook.
  4. `hermes-feishu-card start` refuses to launch the sidecar while `hook.status: manual_review_required` (it exits printing only `hook.next:`). After a plugin upgrade, relaunch the sidecar directly with the runner recipe above and refresh `sidecar.pid`; `status` reads the sidecar over HTTP, so it still reports `running` correctly.
  Verify an installed hook with `grep -c HERMES_FEISHU_CARD_PATCH gateway/run_turn.py` (**not** `gateway/run.py`) plus the manifest check:
  ```bash
  ./venv/Scripts/python.exe - <<'EOF'
  import hashlib, json, pathlib
  root = pathlib.Path(r"C:\Users\Administrator\AppData\Local\hermes\hermes-agent")
  d = json.loads((root / ".hermes_feishu_card_manifest").read_text(encoding="utf-8"))
  for k, p in (("patched_sha256", d["run_py"]), ("cron_patched_sha256", d["cron_py"])):
      h = hashlib.sha256((root / p).read_bytes()).hexdigest()
      print(p, "PATCH_INTACT" if h == d[k] else "NOT PATCHED")
  EOF
  ```
Do not "restore" any of these from a terminal `background=true` launch.

## 🔴 Post-update: python MCP servers die — `fastmcp` vs `mcp 2.0` (2026-09-13)
**Symptom:** `hermes mcp test <server>` → `✗ Connection failed (NNNNms): Connection closed`, and the `.../tools/binance-mcp/server.py` process pairs that were running before the update are simply gone. Everything else (gateway, cron, platforms) looks healthy, so this reads as "the MCP just isn't needed" — it isn't; the server is crashing at import.

Confirm by running the server directly (stdio servers print the traceback on stderr):
```bash
timeout 10 "$LOCALAPPDATA/hermes/hermes-agent/venv/Scripts/python.exe" "D:/Hermes agent/tools/binance-mcp/server.py" < /dev/null 2>&1 | head -25
```
**Root cause:** the update re-pins the venv's `mcp` package to **2.0.0** (hermes `pyproject.toml` pins `mcp==2.0.0` in 3 places — it is NOT optional and must not be downgraded), while a user-installed `fastmcp 3.4.2` only supports `mcp<2.0` (`Requires-Dist: mcp<2.0,>=1.24.0; extra == 'server'`). Result:
```
ImportError: cannot import name 'request_ctx' from 'mcp.server.lowlevel.server'
→ ImportError: FastMCP server support is not installed.
```
Note `mcp 2.0` **removed** `mcp.server.fastmcp`, so "use the official SDK instead" is not an option — the third-party fastmcp must be upgraded.

**Fix (dry-run first, always):**
```bash
PY="$LOCALAPPDATA/hermes/hermes-agent/venv/Scripts/python.exe"
"$PY" -m pip install --dry-run -U fastmcp     # expect: mcp<3.0.0,>=2.0.0 satisfied by 2.0.0; no downgrade
"$PY" -m pip install -U fastmcp                # 3.4.2 → 4.0.x (+ fastmcp-slim 4.0.x, uncalled-for)
"$PY" -c "from fastmcp import FastMCP; print('OK')"
hermes mcp test binance                        # expect ✓ Connected + tool count
```
fastmcp 4.x's `fastmcp-slim` requires `mcp<3.0.0,>=2.0.0` — exactly compatible with hermes' pin, and it does not touch `pydantic`/`pydantic-core`. Verify the tool list comes back (binance: 15 tools) rather than trusting `✓ Connected` alone.

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
- **`Another hermes.exe is running: PID xxxx` is usually the transient updater itself.** The first `hermes update` attempt in this session reported a `hermes.exe` PID that was already gone seconds later (it was the updater's own `hermes.exe`, which re-execs). Re-scan the PID list before `--force`-ing anything on the strength of that message — the venv-holder guard (python.exe) is the real gate.
- **Don't stop at the first `hermes --version` failure to conclude the CLI is broken.** `hermes --version` under git-bash can dump a `threading._readerthread` traceback while PowerShell's `hermes` (via the `.cmd` shim) returns the version cleanly. Use PowerShell for CLI checks — see the `hermes-cli-windows` skill.
- **Double-Python interpreter trap on Windows (uv cpython) — 2026-09-02 confirmed P0.** When the Tangxi pipeline is launched from Hermes' `uv`-managed CPython (e.g. `C:\Users\Administrator\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe`), `auto_card.py:4806` and the cron `script` runner resolve to **that exact short-name path** — NOT to whatever `python` is first on `PATH` (which is `hermes-agent\venv\Scripts\python.exe`) and NOT to `uv python find` (which returned `cpython-3.12.13-windows-x86_64-none` on this box, a third interpreter). The terminal used to test the fix is therefore a **different interpreter from the one auto_card and cron actually use**. If `python -c "import requests"` succeeds in your shell but `auto_card` crashes with `ModuleNotFoundError: No module named 'requests'`, the interpreter the cron runner uses is missing the package even though yours has it. **Diagnosis 3-step (always run, never skip):**
  1. `crud jobs.json` → read the `script` field for the failing cron. In `auto_card`'s case `python auto_card.py BTCUSDT --full` is wrapped by the Hermes cron runner which uses `sys.executable` from the spawning interpreter.
  2. `python -c "import sys; print(sys.executable)"` IN THE TERMINAL you're about to use for the fix. Compare to the interpreter the auto_card traceback names (e.g. `D:\Hermes agent\scripts\auto_card.py", line 4806` tells you nothing — the traceback is the script path, not the interpreter).
  3. Probe the actual interpreter that ran: open a terminal that mimics cron — typically the bare `cpython-3.11-windows-x86_64-none\python.exe` path, not `python`. Run the same `import requests` test there. If THAT fails, fix the **interpreter the script actually uses**, not the one `python` resolves to in your shell.
  **The real interpreter on this box (2026-09-02):** `C:\Users\Administrator\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe`. `uv python find` returns 3.12.13 — **ignore it**; it is the default-pick interpreter, not the one any existing cron uses. `cpython-3.11-windows-x86_64-none` (Windows short name) and `cpython-3.11.15-windows-x86_64-none` (full name) both point to the same 3.11.1 binary. **Fix path for missing packages on this interpreter (use `--break-system-packages` because the uv cpython 3.11 is `externally managed`):** `"<the actual path>\python.exe" -m pip install --break-system-packages <pkgs>`. Common missing: `requests pydantic aiohttp numpy pandas websockets`. After install, verify with the same `<the actual path>\python.exe -c "import <pkg>"` — never with the bare `python` shell, which masks the bug. Reference: `references/uv-cpython-3-11-short-name-2026-09-02.md`.
- **uv cpython 3.11 is a stub — only setuptools+pip are pre-installed.** First `pip install` on it fails with `error: externally-managed environment` (because `uv python find` returns the wrong one) or `subprocess.CalledProcessError` (because `ensurepip` cannot fetch its bootstrap). The clean path: directly call `<the actual path>\python.exe -m pip install --break-system-packages <pkgs>`. The `Scripts` and `Lib/site-packages` dirs are created on demand; do not pre-create them. If you see `ensurepip` errors, your shell is the wrong interpreter — switch to the bare path and retry. Same verification rule as the pitfall above.
- **Diagnose which interpreter a failed cron / subprocess ACTUALLY used, not the one in your shell.** Trap recipe: have the failing script log `sys.executable` to a sentinel file on first call (or `print` it in a no-op wrapper). Then `cat` that file from any terminal — it tells you the interpreter that ran, regardless of what `python` resolves to locally. Saves a full round of "works in shell / fails in cron" debugging.

## Fixed: `image_gen` dead — no `OPENAI_API_KEY` on this box (2026-09-13)
`hermes doctor` reports `⚠ image_gen (image generation unavailable — check the provider selection and its key or SDK)`, while `hermes tools` still prints `[✓] Image Generation`. **Trust `doctor`, not `tools`:** `tools` reports tool enablement, `doctor` checks provider availability. The cause was `config.yaml` → `image_gen.provider: openai` with **no `OPENAI_API_KEY`** in `.env` (only `OPENAI_IMAGE_MODEL` was there).
Fix without buying an OpenAI key — reuse the Codex subscription:
```bash
hermes config set image_gen.provider openai-codex
```
- `plugins/image_gen/openai-codex/` needs **no API key**: it routes `gpt-image-2` through the ChatGPT/Codex Responses `image_generation` tool using the OAuth token; `is_available()` = `_read_codex_access_token()` truthy + httpx present.
- Check the token before switching: `./venv/Scripts/python.exe -c "from agent.auxiliary_client import _read_codex_access_token as r; print('PRESENT' if r() else 'MISSING')"`.
- Registered backends: `deepinfra`, `fal`, `krea`, `meta-ai`, `openai`, `openai-codex`, `openrouter` (needs `OPENROUTER_API_KEY` — this box has one), `xai`. They live in `hermes-agent/plugins/image_gen/<name>/` and register via `PluginContext.register_image_gen_provider()`; `plugins/image_gen/<name>/plugin.yaml` lists `requires_env`.
- Verify with `hermes doctor` → `✓ image_gen` (the `Found N issue(s)` count drops by one).
- Two tooling gotchas: (a) `hermes config set` warns `'image_gen.provider' is not a recognized config key` — harmless, custom top-level keys are bridged and the registry reads it via `configured_provider_name("image_gen")`; (b) the `patch`/`write_file` tools **refuse** to edit `config.yaml` ("Refusing to write to Hermes config file … security-sensitive configuration") — always go through `hermes config set`.

## state.db bloat = the FTS index, not the conversations (2026-09-13)
`state.db` reached 1.74 GB with 2,929 sessions / 91,224 messages. Size distribution (`dbstat`, read-only while the gateway holds the DB):

| object | MB |
|---|---|
| `messages_fts_trigram_data` | 586.8 |
| `messages` | 368.8 |
| `messages_fts_trigram_content` | 276.3 |
| `messages_fts_content` | 276.3 |
| `messages_fts_data` | 90.6 |

The search index (≈1.23 GB) dwarfs the message rows. `sessions.auto_prune: true` (retention_days 30, vacuum_after_prune) was **already set**, so doctor's "enable sessions.auto_prune" advice was stale — the growth is the legacy duplicate-copy FTS layout, not un-pruned sessions. Check the config before acting on that advice.
Fix — no gateway stop required, no conversation data touched:
```bash
hermes sessions optimize-storage --yes   # migrate FTS to the compact v23 external-content layout
hermes sessions optimize                 # (alternative) merge FTS5 segments + VACUUM only
```
`optimize-storage` self-describes as throttled so a live gateway stays responsive, resumable, and VACUUMs at the end — the docstring is the authority here; doctor's "offline (gateway stopped)" line is the conservative default, not a hard requirement. Diagnose distribution first:
```bash
./venv/Scripts/python.exe -c "import sqlite3; c=sqlite3.connect(r'file:C:\Users\Administrator\AppData\Local\hermes\state.db?mode=ro', uri=True); [print(f'{n:<34} {mb}') for n,mb in c.execute('SELECT name, ROUND(SUM(pgsize)/1048576.0,1) mb FROM dbstat GROUP BY name ORDER BY mb DESC LIMIT 8')]"
```
Also present on this box: `state.db.bak_lingsuan_clear` (842 MB, 2026-07-02) — a stale manual backup Hermes does not manage. Ask before deleting; never remove it as part of an automatic cleanup.

## References
- `references/venv-lock-recovery.md` — exact commands, the real `hermes update` lock message, and the observed instance-multiplication transcript.
- `references/pydantic-core-version-conflict.md` — full observed transcript of the pydantic-core 2.48.0 vs 2.46.4 breakage (symptoms, fix, verification), and why "model switching fails" can be a venv native-lib issue.
- `references/uv-cpython-3-11-short-name-2026-09-02.md` — the double-Python-interpreter trap: which interpreter `auto_card.py:4806` and cron `script` actually use, why `python` in the shell masks the bug, and the `--break-system-packages` install recipe.
- `references/ekko-studio-agent-bridge-lock-2026-09-13.md` — the agent-bridge lock class: verbatim abort texts, the two-tree process dump, `--plan`/`--check` output, and how the detached watcher was deployed.
- `scripts/update-when-idle.ps1` — detached update watcher: waits for every venv holder + Studio to exit, then runs `hermes update --yes`. Launch with `Start-Process` (see above) so it outlives the session host.
