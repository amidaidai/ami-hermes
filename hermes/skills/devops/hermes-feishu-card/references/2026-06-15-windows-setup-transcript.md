# 2026-06-15 — Windows Sidecar Setup Transcript

## Context

User 棠溪 (Feishu DM) asked for all responses to be Feishu interactive cards.
The `hermes-feishu-streaming-card` v3.6.1 plugin was already installed (editable
from `D:\Hermes agent\sandbox\hermes-feishu-streaming-card\`) but not activated.

## Steps Taken

### 1. Check prerequisites
- Feishu credentials: found in `~/.hermes/.env` (FEISHU_APP_ID, FEISHU_APP_SECRET)
- Plugin installed: `pip show hermes-feishu-streaming-card` → v3.6.1
- CLI available: `hermes-feishu-card` in PATH
- Hermes version: v2026.6.5 (≥ minimum v2026.4.23)
- Streaming config: already `enabled: true, transport: edit`

### 2. Create config (pitfall encountered)

Created `~/.hermes_feishu_card/config.yaml` with `bots.items: {default: {}}`.
This caused `ValueError: bot default app_id is required` — `_bot_from_mapping`
requires app_id in every bot item; they are NOT inherited from top-level
`feishu` section.

**Fix**: Removed `items` block entirely. Plugin auto-creates default bot from
top-level `feishu.app_id`/`feishu.app_secret`.

Working config:
```yaml
server:
  host: 127.0.0.1
  port: 8765
feishu:
  app_id: cli_a920641af8b81bb4
  app_secret: lq8mDValvQCXG5jQZVRPHiFIslHrkdsfQalQk
bots:
  default: default
bindings:
  chats: {}
  group_rules:
    enabled: false
card:
  max_wait_ms: 800
  max_chars: 240
  title: 🃏 安禾
  footer_fields:
    - duration
    - model
    - input_tokens
    - output_tokens
    - context
```

### 3. Patch gateway
```bash
hermes-feishu-card setup --config ~/.hermes_feishu_card/config.yaml \
  --hermes-dir "C:/Users/Administrator/AppData/Local/hermes/hermes-agent" --yes
```
Output: `install ok`, patch markers verified with `grep -c (≥ 2)`.

### 4. Start sidecar (recurring failure)
- `hermes-feishu-card start` returned "start ok" but process died silently.
- Even checking `status` after 3 seconds showed "running", but it stopped minutes later.
- Log (`sidecar.log`) had old error from old config, or was empty after clearing.

**Fix**: Use `terminal(background=true)` directly:
```bash
python -m hermes_feishu_card.runner \
  --config "C:/Users/Administrator/.hermes_feishu_card/config.yaml" \
  --token "$(python -c "import secrets; print(secrets.token_hex(16))")"
```

### 5. Restart gateway
```bash
# Get PID from gateway.pid, kill it, then:
hermes gateway run --replace
```
Gateway restarted with PID 18976, all platforms reconnected.

### 6. Smoke test
```bash
hermes-feishu-card smoke-feishu-card \
  --config ~/.hermes_feishu_card/config.yaml \
  --chat-id "oc_c4500490614a85b9b5db83f3f25b626a"
```
→ `smoke ok, message_id: om_x...`

### 7. Watchdog setup
Created cron job (every 5m) that checks port 8765 health and restarts sidecar
if down. No notification when healthy.

## Verification Commands
```bash
# Quick health check
python -c "import urllib.request, json; print(urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3).read().decode())"

# Sidecar status
hermes-feishu-card status --config ~/.hermes_feishu_card/config.yaml

# Gateway + platform status
cat ~/AppData/Local/hermes/gateway_state.json | python -m json.tool

# Smoke test
hermes-feishu-card smoke-feishu-card --config ~/.hermes_feishu_card/config.yaml --chat-id "oc_c4500490614a85b9b5db83f3f25b626a"
```

## Notes
- Chat ID `oc_c4500490614a85b9b5db83f3f25b626a` is 棠溪的飞书 DM 会话
- Existing in-progress sessions still use old text format; user must send a NEW message
- `send_message` tool with target `feishu:<chat_id>` also goes through card pipeline
