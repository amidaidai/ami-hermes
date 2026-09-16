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

## 飞书消息没有回复：先查 Unauthorized user（最高频故障）

**症状**：从飞书给 bot 发消息完全没反应；`logs/gateway.log` 里是

```
INFO  hermes_plugins.feishu_platform.adapter: [Feishu] Inbound dm message received: ... sender=user:ou_xxx text='...'
WARNING gateway.run: Unauthorized user: 6a2e6dcf (None) on feishu
```

**根因（ID 形态不匹配，不是连接问题）**：飞书有三套 ID ——
`open_id`（`ou_…`，app 维度）、`user_id`（租户内短串如 `6a2e6dcf`）、`union_id`（`on_…`）。
`plugins/platforms/feishu/adapter.py::_resolve_sender_profile` 用
`primary_id = user_id or open_id`（**租户 user_id 优先**）填 `SessionSource.user_id`，
而 `gateway/authz_mixin.py::_principal_matches_allowlist` 只对 WhatsApp/SimpleX/Buzz 做别名归一化，
**飞书是纯字符串比较**。于是 `FEISHU_ALLOWED_USERS` 里只写 open_id 时永不匹配 → 每条消息被丢弃。
（`sender=user:ou_…` 日志行显示的是 open_id，授权用的是 `source.user_id`，两者不是一回事。）

**诊断步骤**：

```bash
# 1. 确认是被拒而不是没收到
grep -n "Unauthorized user\|Inbound dm message received" logs/gateway.log | tail -10
# 2. 用飞书 API 反查该 open_id 对应的 user_id / union_id（app_id+secret 在 .env）
#    POST /open-apis/auth/v3/tenant_access_token/internal  → token
#    GET  /open-apis/contact/v3/users/<open_id>?user_id_type=open_id  → data.user.{user_id,union_id}
#    注意：batch_get_id 需要 contact:user.id:readonly 权限，users/{id} 端点通常已授权
```

**修复**：`FEISHU_ALLOWED_USERS` 把三套 ID 都列上（同一 principal，不构成扩权）：

```
FEISHU_ALLOWED_USERS=<user_id>,<open_id>,<union_id>
```

**必须重启 gateway**：授权检查（`gateway/run_inbound.py::_is_user_authorized_for_source`）跑在
per-turn `.env` 重载**之前**，改完 `.env` 不重启的话，下一条飞书消息仍用旧 `os.environ` → 仍被拒，
而且因为被拒就没有 turn，也就永远不会触发重载（自锁）。`hermes gateway restart` 后确认：

```bash
python -c "import psutil,json;d=json.load(open(r'C:/Users/Administrator/AppData/Local/hermes/gateway_state.json'));print(psutil.Process(d['pid']).environ()['FEISHU_ALLOWED_USERS'])"
```

同一形态的坑：`config.yaml` 的 `platforms.feishu.extra.admins` 走的是
`_is_interactive_operator_authorized(open_id)`（传 open_id），那里用 `ou_…` 是对的 —— 两处口径相反，改之前看清传的是哪个 ID。

⚠️ **Pitfall — 必须重启 gateway 才能让新白名单生效**：授权检查在 `_is_user_authorized_for_source` 中执行，该函数在 `gateway/run_inbound.py` 的 `_hm_pre_gateway_dispatch_hook` 之前被调用，而 per-turn `.env` 重载（`_reload_runtime_env_preserving_config_authority`）发生在 turn 内部。如果不重启 gateway，下一条飞书消息仍使用旧的 `os.environ['FEISHU_ALLOWED_USERS']`，依然被拒；被拒后没有 turn，也就永远不会触发重载 —— 形成自锁。

## Sidecar 起不来：插件版本必须跟上 Hermes + 关掉 integrity 监控

Hermes 大版本升级会重构 `gateway/`（run_turn / run_turn_runner / run_inbound / run_busy /
run_startup / run_notifications 拆分，base.py 抽出显式投递契约）。插件落后时：

```
hermes-feishu-card doctor  →  Hermes: unsupported
                              [error] gateway/platforms/base.py exact delivery anchors are unsupported
```

继而 HFC runtime integrity fence 写 `manual_review_required / integrity_migration_required`，
`hermes-feishu-card start` 直接拒绝启动 sidecar（8765 不再监听）→ **所有卡片发送全部失效**。

修复顺序：

```bash
cd <plugin-repo> && git fetch origin main && git merge --ff-only origin/main   # 4.4.5 → 4.5.0 才支持 0.21.x
hermes-feishu-card doctor --config ... --hermes-dir ... --explain              # 期望 compatibility full + 全锚点 found
```

Windows 专属障碍（都实测过）：

- `integrity migrate-safe` 在该平台不可用：`secure integrity migration requires directory-relative filesystem operations` —— 改用下面的“清陈旧状态”路径。
- `integrity acknowledge-review` 在 Hermes 已升级后会失败：`manual review fence could not be acknowledged safely`。
- `setup` 报 `legacy backup missing or changed; refusing layout migration`（旧 manifest 指向已不存在的
  `gateway/run.py.hermes_feishu_card.bak`）：把 `~/.hermes/hermes-agent/.hermes_feishu_card_manifest`
  备份后删掉（源码本身是干净的未 patch 版本，manifest 只是死记录），同时删掉
  `~/.hermes_feishu_card/runtime-integrity-fence.json`，readiness 即从
  `degraded/manual_review_required` 转为 `starting/runtime_heartbeat_waiting`。

**启动 sidecar 必须用 venv python**（`~/.hermes/hermes-agent/venv/Scripts/python.exe`）：
base 的 uv python 缺 `yaml`，会以 `ModuleNotFoundError: No module named 'yaml'` 静默退出。
用 detached 方式启动（不要用 CLI `start`，它会 spawn 子进程随终端退出而死）：

```python
subprocess.Popen([PY,'-m','hermes_feishu_card.runner','--config',CFG,'--hermes-dir',HERMES_AGENT,
                  '--env-file',ENVF,'--token',TOK], cwd=REPO,
                 creationflags=0x00000008|0x00000200)   # DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP
```

**sidecar 配置里必须关掉 integrity 监控**（`integrity.mode: off`），否则即使插件版本匹配、Hermes 已升级，完整性看门狗仍会周期性写 fence，导致 readiness 卡在 `degraded/manual_review_required`，看门狗误判为“不健康”并反复杀进程。实测：
- `mode: notify` → 4 分钟内 fence 重现，看门狗每 5 分钟拉起一次
- `mode: off` → fence 不再生成，readiness = `disabled/integrity_disabled`，sidecar 连续存活 20+ 分钟

启动后把真实 pid 写回 `~/.hermes_feishu_card/sidecar.pid`（health 的 `process_pid`），
否则 `status` 报 stale。`readiness` 停在 `starting/runtime_heartbeat_waiting` 是**正常的**——
没有 gateway hook 就没有心跳来源，而直发卡片不需要 hook（`delivery.mode: live` 即可用）。

### 保活：本机当前未启用（2026-09-16 经用户决定移除）

`integrity.mode: off` 之后 sidecar 已不再周期性自杀（实测连续存活 30 分钟以上，且跨 `hermes gateway restart` 存活），
因此本机**不再配置任何自动保活**：无 Hermes cron、无 Windows 计划任务、无 VBS 启动器。

判断标准：只要 sidecar 是 detached 启动（父进程不是 gateway），`hermes gateway restart` 不会杀掉它。
只有「由 Hermes cron / gateway 内置 tick 启动」的 sidecar 才会随 gateway 一起死 —— 这就是当初需要保活的原因，
现已随启动方式改变而消失。

sidecar 挂掉时的单条恢复命令（venv python + detached，见上一节的 `subprocess.Popen` 配方）：

```bash
curl -s http://127.0.0.1:8765/health   # 先确认
# 未通就重跑一节里的 detached 启动配方，然后把 health 的 process_pid 写回 ~/.hermes_feishu_card/sidecar.pid
```

**若日后要重新启用自动保活**，两条已实测的路径（按侵入度排序）：

1. Hermes cron（零权限门槛，但 sidecar 会成为 gateway 子进程，每次 gateway 重启需 5 分钟内自愈）：
   `hermes cron create "*/5 * * * *" --name "飞书卡片sidecar看门狗" --script <脚本名> --no-agent --deliver local`，
   注意 **cron 只认 `workdir/scripts/<script>`**（默认 workdir 由 job 决定），放 `~/.hermes/scripts/` 会报
   `Script not found: D:\Hermes agent\scripts\…`。
2. Windows 计划任务 + VBS 隐藏启动器（真正解耦，但 `/create` 需要管理员权限，本机普通权限下返回 `WinError 5 拒绝访问`）：
   `schtasks /create /tn "HermesFeishuCardSidecarWatchdog" /tr "wscript.exe \"<vbs路径>\"" /sc MINUTE /mo 5 /f /rl HIGHEST`

两种方案的看门狗脚本逻辑都一样：探 `/health` → 通就静默退出 → 不通就 detached 拉起并记一行日志。
现成模板留在本技能 `scripts/` 下（`feishu_sidecar_watchdog.py`、`feishu_sidecar_hidden.vbs`），需要时直接取用；本机当前未启用。

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
- **⚠ Gateway hook silently fails**: The gateway patch wraps `emit_from_hermes_locals` in `try/except Exception: pass`. If the import or event-building fails, it's invisible with no log output. The sidecar reports `events_received: 0` even though the gateway appears healthy.
  - **Diagnosis**: Add debug logging to `hook_runtime.py`'s `emit_from_hermes_locals` function to capture what step fails (import, build_event, asyncio.get_running_loop, HTTP POST).
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

### Windows-Specific: uv python vs venv python（关键坑）

- **uv python**（`~/.local/hermes/python/...` 或 `AppData/Roaming/uv/python/...`）：`pip install -e` 后 `import yaml` 失败（`ModuleNotFoundError: No module named 'yaml'`），sidecar 启动秒退。
- **venv python**（`~/.hermes/hermes-agent/venv/Scripts/python.exe`）：自带 `yaml`/`lark-oapi` 等依赖，`hermes_feishu_card` 可直接 import。**必须用 venv python 启动 sidecar**。

```bash
# 正确
PY="C:/Users/Administrator/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
$PY -m hermes_feishu_card.runner --config ... --token ...

# 错误（会静默退出）
PY="C:/Users/Administrator/AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe"
$PY -m hermes_feishu_card.runner ...
```

⚠️ **Pitfall — sidecar 配置必须设 `integrity.mode: off`**：默认 `mode: notify` 会导致完整性看门狗周期性生成 fence（`runtime-integrity-fence.json`），readiness 卡在 `degraded/manual_review_required`，看门狗误判为不健康并每 5 分钟杀进程重启。实测：
- `mode: notify` → 4 分钟 fence 重现 → 看门狗反复拉起
- `mode: off` → fence 不再生成 → readiness = `disabled/integrity_disabled` → sidecar 连续存活 20+ 分钟

```yaml
# ~/.hermes_feishu_card/config.yaml
integrity:
  mode: off
```

⚠️ **Pitfall — 启动方式决定 sidecar 的生死**：detached 启动（父进程非 gateway）的 sidecar 能跨 `hermes gateway restart` 存活；
而由 Hermes cron / gateway 内置 tick 启动的 sidecar 是 gateway 的子进程，会随 gateway 一起被杀。
选启动方式时先想清楚这一点，不要靠保活去补启动方式的坑。
