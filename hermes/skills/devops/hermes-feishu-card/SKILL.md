---
name: hermes-feishu-card
description: "Setup, manage, and troubleshoot Feishu/Lark interactive card messaging for Hermes Agent via the hermes-feishu-streaming-card sidecar plugin."
version: 1.0.0
author: Agent
platforms: [windows, linux, macos]
metadata:
  trigger_patterns:
    - feishu card
    - 飞书卡片
    - streaming card
    - hermes-feishu-streaming-card
    - 卡片回复
    - interactive card
---

# Hermes Feishu Card Plugin

Enable **interactive card** responses (instead of plain text/post) for Feishu/Lark in Hermes Agent. Uses the `hermes-feishu-streaming-card` Python package as a sidecar — patches the gateway message handler (`gateway/run.py` on older Hermes, `gateway/run_turn.py` after the split) and runs an HTTP sidecar on port 8765.

## Prerequisites

- Hermes ≥ v2026.4.23 (check with `hermes doctor` or `hermes --version`)
- Feishu bot already configured and connected in Hermes gateway
- `hermes-feishu-streaming-card` installed (check with `pip show hermes-feishu-streaming-card`)
- Hermes streaming enabled in config.yaml:
  ```yaml
  streaming:
    enabled: true
    transport: edit
    edit_interval: 0.8
    buffer_threshold: 24
  ```

## Setup Procedure

### 1. Install the plugin (if not already)

```bash
pip install hermes-feishu-streaming-card
```

Or for development / editable install:
```bash
git clone <repo-url>
cd hermes-feishu-streaming-card
pip install -e .
```

### 2. Create sidecar config

Create `~/.hermes_feishu_card/config.yaml`:

```yaml
server:
  host: 127.0.0.1
  port: 8765

feishu:
  app_id: "<your-feishu-app-id>"
  app_secret: "<your-feishu-app-secret>"

bots:
  default: default

bindings:
  chats: {}
  group_rules:
    enabled: false

card:
  max_wait_ms: 800
  max_chars: 240
  title: "Bot Name"
  footer_fields:
    - duration
    - model
    - input_tokens
    - output_tokens
    - context
```

Credentials come from the same `FEISHU_APP_ID` / `FEISHU_APP_SECRET` in `~/.hermes/.env`.

**Important**: Do NOT define `bots.items` with an empty dict — the auto-creation from top-level `feishu` section handles the default bot. An explicit `items: {default: {}}` will fail with "bot default app_id is required".

### 3. Patch Hermes gateway + install hooks

```bash
hermes-feishu-card setup \
  --config ~/.hermes_feishu_card/config.yaml \
  --hermes-dir <path-to-hermes-root> \
  --yes
```

The `hermes-dir` is the Hermes source code root, typically:
- Windows (pip install): `~/AppData/Local/hermes/hermes-agent`
- Linux/macOS (pip install): `<venv>/lib/python*/site-packages/../hermes/`
- Git install: repo checkout root

Verify the patch landed — and check the file the handler actually lives in, which MOVED on recent Hermes:
```bash
# pre-split Hermes: gateway/run.py   |   current Hermes: gateway/run_turn.py
grep -c 'HERMES_FEISHU_CARD_PATCH' <hermes-dir>/gateway/run_turn.py
# Expected output: ≥ 2
```

### Hermes-version coupling — upgrade the plugin, never hand-patch the AST
The plugin anchors its patch to exact Hermes source shapes, so **any Hermes update that refactors `gateway/` can invalidate it**. Recent Hermes split `gateway/run.py`: the message handler moved to `gateway/run_turn.py`, final delivery was extracted into `_hmwa_deliver_turn_response`, and cron delivery split into `cron/scheduler_delivery.py`.

A stale plugin shows up in `hermes-feishu-card doctor` as `Hermes: unsupported` + `gateway/run.py missing async anchor function: _handle_message_with_agent`. Fix in this order:
1. `git fetch origin main` in the plugin clone **for real** — `git fetch --dry-run` does NOT advance `origin/main`, so `git log origin/main` still shows the stale tip and you will wrongly conclude the plugin is current.
2. A new-enough upstream carries `patcher.DECOMPOSED_GATEWAY_TARGETS` (`run_turn.py`, `run_turn_runner.py`, `run_inbound.py`, `run_busy.py`, `run_startup.py`, `run_notifications.py`) plus `cron/scheduler_delivery.py` and `gateway/platforms/base.py`. If present: `git stash push -m … -- <locally modified files>` then `git merge --ff-only origin/main`.
3. Re-run doctor. `compatibility full` means the moved anchors were found. A leftover `gateway/platforms/base.py exact delivery anchors are unsupported` means **upstream has not caught up with this Hermes build yet** — that is not a config error and nothing is misconfigured.
4. **Never force a partial patch to "make it work".** On the split files `apply_patch` gets in only the *start* block, at the handler entry, where `locals()` still lacks `response`/`agent_result` — the card opens and never completes, which is worse than having no hook at all. Leave the hook uninstalled (direct sidecar sends need no hook) and re-test after the next plugin release.
5. `hermes-feishu-card start` refuses to launch the sidecar while the hook is unhealthy (`hook.status: manual_review_required`, it exits printing only `hook.next:`). Relaunch the sidecar directly with the runner recipe below; `status` talks to the sidecar over HTTP and still reports correctly.

The update-side procedure and the full post-update sweep live in the `hermes-windows-maintenance` skill.

### 4. Start the sidecar

```bash
hermes-feishu-card start --config ~/.hermes_feishu_card/config.yaml
```

Check status:
```bash
hermes-feishu-card status --config ~/.hermes_feishu_card/config.yaml
```

Expected: `status: running`, port 8765 listening.

### 5. Restart Hermes gateway

```bash
hermes gateway restart
```

If running inside the gateway (will be blocked with "Refusing to restart from inside gateway process"), kill the old gateway process and start fresh:
```bash
kill $(cat ~/AppData/Local/hermes/gateway.pid 2>/dev/null | python -c "import json,sys; print(json.load(sys.stdin)['pid'])" 2>/dev/null)
rm -f ~/AppData/Local/hermes/gateway.lock ~/AppData/Local/hermes/gateway.pid
hermes gateway run --replace
```

Verify all platforms reconnected:
```bash
cat ~/AppData/Local/hermes/gateway_state.json | python -m json.tool
```

## Verification Checklist

| Component | Check | Expected |
|-----------|-------|----------|
| Gateway patch | `grep -c HERMES_FEISHU_CARD_PATCH gateway/run_turn.py` (pre-split Hermes: `gateway/run.py`) | ≥ 2 |
| Sidecar | `hermes-feishu-card status` | `status: running` |
| Gateway | `hermes gateway status` | Gateway running, feishu connected |
| Streaming config | `grep -A5 '^streaming:' config.yaml` | `enabled: true` |
| Smoke card | `hermes-feishu-card smoke-feishu-card --chat-id \"<id>\"` | `smoke ok` |

### Smoke test

```bash
hermes-feishu-card smoke-feishu-card \
  --config ~/.hermes_feishu_card/config.yaml \
  --chat-id "<feishu_chat_id>"
```

Expected output: `smoke ok` with a `message_id`.

## User Preferences

- 棠溪主用电报（Telegram），飞书作备用渠道。
- 飞书卡片通过 sidecar API 直发（绕过 gateway hook）。
- 分析卡片优先发电报；飞书仅在需要卡片格式时使用。

## Management Commands

```bash
# Status
hermes-feishu-card status --config ~/.hermes_feishu_card/config.yaml

# Stop
hermes-feishu-card stop --config ~/.hermes_feishu_card/config.yaml

# Start
hermes-feishu-card start --config ~/.hermes_feishu_card/config.yaml

# Doctor / diagnose
hermes-feishu-card doctor --config ~/.hermes_feishu_card/config.yaml --hermes-dir <path> --explain

# Uninstall hooks from gateway
hermes-feishu-card uninstall --hermes-dir <path> --yes

# Restore backup of gateway/run.py
hermes-feishu-card restore --hermes-dir <path> --yes
```

## Sidecar Logs

```bash
cat ~/.hermes_feishu_card/sidecar.log
```

## Gateway Hook Troubleshooting

The hook (`emit_from_hermes_locals`) fires from inside `_handle_message_with_agent` in `gateway/run.py`. It POSTs events to the sidecar at `http://127.0.0.1:8765/events`. When `events_received` stays at 0, diagnose in this order:

### 1. Check sidecar health

```bash
python -c "import urllib.request, json; r = urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3); d = json.loads(r.read()); print('received:', d['metrics']['events_received'])"
```

If `events_received == 0`, the gateway is not sending events.

### 2. Check gateway Python module availability

The gateway runs inside Hermes Desktop's bundled Python. **Do NOT use `pip install -e` (editable install).** The `.pth` file from editable installs is not processed by the gateway subprocess. Instead, copy directly:

```bash
SITE="<bundled-python>/Lib/site-packages"
cp -r "<source>/hermes_feishu_card" "$SITE/"
# Verify:
"<bundled>/python.exe" -c "from hermes_feishu_card.hook_runtime import emit_from_hermes_locals; print('OK')"
```

### 3. Restart gateway after module install

```bash
hermes gateway restart
```

### 4. Sidecar event format (for manual sends)

- `platform` **must** be `"feishu"` — sidecar rejects anything else
- Card text goes in `answer.delta.data.text`, NOT `message.started`
- Images via `MEDIA:` in `message.completed.data.answer` → but sidecar **cannot** upload local files; use gateway `send_message` for image delivery

## Pitfalls

- **Bundled Python (Hermes Desktop)**: The gateway runs inside the Hermes Desktop bundled Python at `C:\Users\Administrator\.hermes-web-ui\desktop-runtime\hermes\<version>\win-x64\python\`. The `hermes_feishu_card` package must be installed into THIS Python, not the user/system Python. Editable installs (`pip install -e`) with `.pth` files may not work in the bundled environment. **Fix**: Copy the module directly into the bundled Python's `Lib/site-packages/`: `cp -r hermes_feishu_card/ <bundled_python>/Lib/site-packages/`. Then restart the gateway.
- **Sidecar cannot upload local images**: The sidecar's card renderer cannot access local filesystem to upload images to Feishu. MEDIA: references in card text are ignored. **Workaround**: Send card text via sidecar API (`127.0.0.1:8765/events`), send screenshots separately via gateway `send_message` with `MEDIA:` reference.
- **Gateway hook silent failure**: The hook `emit_from_hermes_locals` swallows all exceptions. If `events_received` stays at 0 after restart, the import or event building is failing silently. Verify with: `python -c "from hermes_feishu_card.hook_runtime import emit_from_hermes_locals"` inside the bundled Python.
- **Sidecar dies silently on Windows**: See the Windows-Specific section above for the background launch workaround.

- **Config format**: Do NOT put `bots.items.default: {}` alongside top-level `feishu` section. The `_bot_from_mapping` function requires `app_id` in every bot item. Use auto-creation (no `items`) or explicitly set `app_id`/`app_secret` in each bot item.
- **Gateway restart**: Cannot restart gateway from inside the gateway process (prevents restart loops). Use an external terminal.
- **Streaming config**: The plugin expects `streaming.enabled: true` and `streaming.transport: edit` in Hermes config.yaml. Without this, `answer.delta` streaming events won't fire.
- **Windows paths**: Use forward slashes or escaped backslashes in config paths. The CLI and sidecar handle both.
- **PID stale**: If `sidecar.pid` has a stale PID, `hermes-feishu-card status` shows `status: stopped, pid: X stale`. Kill the stale process and re-run `hermes-feishu-card start`.

### Editable install doesn't work in Hermes bundled Python
`pip install -e` creates a `.pth` file in site-packages, but the Hermes gateway's bundled Python (`desktop-runtime/hermes/<version>/win-x64/python/`) does NOT process `.pth` files from editable installs at runtime. The gateway hook silently fails to `import hermes_feishu_card`.

**Fix**: Copy the module directory directly into site-packages:
```bash
cp -r <source>/hermes_feishu_card <bundled_python>/Lib/site-packages/
```
Then restart the gateway. Verify with:
```bash
<bundled_python>/python.exe -c "import hermes_feishu_card.hook_runtime; print('OK')"
```

### Gateway hook may not fire (platform enum issue)
The `_first_attr_string` function in hook_runtime checks `isinstance(value, str)`. The gateway's `source.platform` is an enum, not a string, so `_first_attr_string` returns None. `_platform_name` falls back to default `"feishu"`, but the real issue is that `build_event` may fail to extract `chat_id` from non-dict source objects.

**Workaround**: Send events directly to the sidecar API at `http://127.0.0.1:8765/events` instead of relying on the gateway hook. Events require:
- `schema_version: "1"`, `platform: "feishu"`
- Text content must go in `answer.delta` events (NOT `message.started`)
- `message.completed.answer` field must contain full text for MEDIA attachment extraction
- See `feishu-analysis-card-sender` skill for the full workflow.

### Hard gateway kill also kills sidecar
When `taskkill //PID <gateway_pid> //F` is used, the sidecar process may be killed too if it shares the same Python runtime. After a hard restart, verify sidecar is running:
```bash
python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3)"
```
If down, restart with the background runner method documented above.
- **⚠ Bundled Python (Hermes Desktop)**: The gateway runs inside Hermes Desktop's bundled Python (`~/.hermes-web-ui/desktop-runtime/hermes/<version>/win-x64/python/`). `hermes_feishu_card` MUST be installed into THIS Python, not the system/user Python. `pip install hermes-feishu-streaming-card` in the user Python does NOT make it available to the gateway.
  - **Install command**: `"<bundled-python>/python.exe" -m pip install hermes-feishu-streaming-card` (or `pip install -e <local-repo>` for dev version)
  - **Editable install warning**: `pip install -e` creates a `.pth` file that subprocess-spawned gateways may not resolve. Prefer copying the module directly into site-packages: `cp -r <source>/hermes_feishu_card <site-packages>/`
  - **Verify**: `"<bundled-python>/python.exe" -c "from hermes_feishu_card.hook_runtime import emit_from_hermes_locals; print('OK')"`
- **⚠ Gateway hook silently fails**: The `emit_from_hermes_locals` call inside `_handle_message_with_agent` is wrapped in `try/except Exception: pass`. If the import or event-building fails, it's invisible with no log output. The sidecar reports `events_received: 0` even though the gateway appears healthy.
  - **Diagnosis**: Add debug logging to `hook_runtime.py`'s `emit_from_hermes_locals` to capture what step fails (import, build_event, asyncio.get_running_loop, HTTP POST).
  - **Platform detection**: `_platform_name()` defaults to `"feishu"` when platform is None, but the sidecar validates `platform == "feishu"` strictly. Non-Feishu source messages (Web UI, CLI) will have their events built but may be rejected at the sidecar.
  - **Workaround**: When the gateway hook is unreliable, send events directly to the sidecar API at `http://127.0.0.1:8765/events` with `platform: "feishu"` hardcoded. See `references/sidecar-event-schema.md` for the event format. Use `message.started` → `answer.delta` → `message.completed` sequence. Text must go in `answer.delta.data.text`, NOT in `message.started.data`.
- **🔴 Bundled Python + editable install failure**: On Windows with Hermes Desktop, the gateway runs inside `~/.hermes-web-ui/desktop-runtime/hermes/<version>/win-x64/python/`. **`pip install -e` (editable install) does NOT work** for the gateway subprocess — the `.pth` file is not processed. The hook silently fails with `ModuleNotFoundError`. **Fix**: copy the module directly into site-packages instead:
  ```bash
  SITE="~/AppData/Local/hermes-web-ui/desktop-runtime/hermes/0.16.0/win-x64/python/Lib/site-packages"
  cp -r "<source>/hermes_feishu_card" "$SITE/"
  ```
  Verify: `"<bundled-python>/python.exe" -c "from hermes_feishu_card.hook_runtime import emit_from_hermes_locals; print('OK')"`
- **🔴 Sidecar dies on gateway hard restart**: If the sidecar was started as a child of the gateway process, `taskkill //PID //F` on the gateway will also kill the sidecar. After hard-restarting gateway, verify sidecar is still running: `curl http://127.0.0.1:8765/health`. If not, restart sidecar via `python -m hermes_feishu_card.runner` in background.
- **🔴 Hook silence**: The gateway patch wraps `emit_from_hermes_locals` in `try/except Exception: pass`. If the hook fails for ANY reason — import error, missing chat_id, asyncio loop error, HTTP POST failure — it fails silently with no log. For debugging, add file-based logging to `hook_runtime.py` `emit_from_hermes_locals` function to trace which step fails.
- **🔴 Sidecar event format**: When sending events directly to `POST /events`:
  - Text goes in `answer.delta` event's `data.text` field, NOT in `message.started`
  - MEDIA: attachments are only parsed from `message.completed` event's `data.answer` field
  - `platform` must be exactly `"feishu"` or events are rejected with 400
  - Required fields: `schema_version: "1"`, `event`, `conversation_id`, `message_id`, `chat_id`, `platform`, `sequence`, `created_at`, `data`
- **🔴 Sidecar cannot upload local images**: The sidecar API can send text cards but cannot upload local files to Feishu. For images, use gateway `send_message` with `MEDIA:<path>`.
- ⚠️ **Bundled Python install (CRITICAL)**: When Hermes runs via Desktop/Studio, the gateway uses a bundled Python at `<Desktop-runtime>/hermes/<version>/win-x64/python/`. The `hermes_feishu_card` package MUST be installed into that Python, NOT just the system/user Python. After `pip install` with system Python, also run: `"<bundled-python-path>/python.exe" -m pip install -e <path-to-hermes-feishu-streaming-card-repo>`. Verify with: `"<bundled-python-path>/python.exe" -c "from hermes_feishu_card.hook_runtime import emit_from_hermes_locals; print('OK')"`. Without this, the gateway hook silently fails (`ModuleNotFoundError` caught by `except Exception: pass`).
- ⚠️ **Gateway hook silently drops non-Feishu platform events**: The sidecar's `SidecarEvent.from_dict()` rejects events where `platform != "feishu"`. When messages come from Hermes Web UI (not Feishu), `_platform_name()` returns non-"feishu" values. The gateway hook in `emit_from_hermes_locals` catches all exceptions with `except Exception: return False`, so the rejection is invisible — `events_received` stays 0. This means the gateway hook ONLY works when the user sends messages directly from the Feishu app. For agent-initiated card sends (e.g., analysis results pushed proactively), use the direct-send workaround below.
- ✅ **Workaround — direct POST to sidecar events API**: When the gateway hook cannot be used (e.g., sending cards proactively from a Web UI conversation), POST events directly to `http://127.0.0.1:8765/events`. The sidecar accepts properly-formed events and will create + send Feishu cards. See `references/sidecar-event-schema.md` for the full event format and `scripts/send-feishu-card.py` for a reusable script.

## Windows-Specific: Hook Not Firing (events_received=0)

**Symptom**: Sidecar health shows `events_received: 0`, `feishu_send_attempts: 0` even after gateway restart. Feishu responses are plain text, not cards.

**Root causes** (check in order):
1. Module not installed in bundled Python (see Pitfalls above)
2. Gateway started before sidecar → events silently dropped (gateway doesn't retry connection)
3. Hook fails silently inside `try/except Exception: pass` wrapper

**Debug procedure**:
1. Verify sidecar is reachable: `curl http://127.0.0.1:8765/health`
2. Verify sidecar accepts events: `curl -X POST http://127.0.0.1:8765/events -H "Content-Type: application/json" -d '{"schema_version":"1","event":"message.started","conversation_id":"t","message_id":"t","chat_id":"t","platform":"feishu","sequence":0,"created_at":0,"data":{}}'` → should return `{"ok":false,"error":"..."}` (validation error is OK, `{"ok":false,"error":"missing required field"}` means sidecar is working)
3. Test with valid event: include all required fields with `platform: "feishu"` → should return `{"ok":true,"applied":true}`
4. If sidecar works but gateway hook doesn't fire: add debug logging to `hook_runtime.py` `emit_from_hermes_locals` (write to `~/.hermes_feishu_card/debug.log`)
5. After adding logging, restart gateway and send a test message from Feishu → read debug.log

**Observation**: The sidecar process (`hermes-feishu-card start`) frequently dies silently on Windows — shows `start ok` but process exits within minutes (stale PID). The log (`~/.hermes_feishu_card/sidecar.log`) is often empty.

**Root cause**: The `hermes-feishu-card start` CLI spawns the runner as a subprocess. On Windows (git-bash/MSYS), when the parent CLI process exits or the terminal session ends, the child may be killed silently.

**Fix — use `terminal(background=true)` or direct background launch:**

```bash
# Instead of:
hermes-feishu-card start --config ~/.hermes_feishu_card/config.yaml

# Use direct background runner:
python -m hermes_feishu_card.runner \
  --config ~/.hermes_feishu_card/config.yaml \
  --token "$(python -c "import secrets; print(secrets.token_hex(16))")"
```

After starting, update the PID file and verify:

```bash
# Check health
python -c "
import urllib.request, json
r = urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3)
print(r.read().decode())
"

# Update sidecar.pid (extract actual_pid and token from health response)
python -c "
import json
with open('C:/Users/Administrator/.hermes_feishu_card/sidecar.pid', 'w') as f:
    json.dump({'pid': <actual_pid>, 'token': '<token>'}, f)
"
```

### Watchdog: Auto-Restart Cron Job

Set up a Hermes cron job to check and restart the sidecar every 5 minutes:

```bash
hermes cron create --name "feishu-card-watchdog" --schedule "every 5m" \
  --prompt "Check if the Feishu card sidecar (port 8765) is running. If not, restart via direct background runner."
```

Or via the `cronjob` tool:
```
cronjob(action='create', name='feishu-card-watchdog', schedule='every 5m',
        prompt='Check if the Feishu card sidecar (port 8765) is running. If not, restart with python -m hermes_feishu_card.runner...')
```

The watchdog is SILENT — it only acts when the sidecar is down, no notifications when healthy.

## Verification

After setup, send a message to the Feishu bot. The response should appear as an interactive card with:
- A header/title bar
- Structured content with dividers
- Footer showing model name and response time
- (Optional) Streaming updates as the agent thinks and calls tools

> Full setup transcript from a Windows production deploy (including the sidecar crash workaround): `references/2026-06-15-windows-setup-transcript.md`
