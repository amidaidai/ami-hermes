# B.AI (api.b.ai) — Hermes custom provider notes

Official docs: https://docs.b.ai/zh-Hans/llmservice/api/
Console / top-up: https://chat.b.ai/chat

## Wire protocol

B.AI speaks three protocols on the same key:

| Endpoint | Protocol | Hermes `api_mode` |
|---|---|---|
| `POST /v1/chat/completions` | OpenAI Chat Completions | `chat_completions` — **use this for Hermes Agent** |
| `POST /v1/responses` | OpenAI Responses | `codex_responses` only if the user explicitly wants Codex/Responses |
| `POST /v1/messages` | Anthropic Messages | `anthropic_messages` only for Claude-code style clients |

Auth: `Authorization: Bearer <BAI_API_KEY>` or `x-api-key`. Env var: `BAI_API_KEY`.

**Always include `/v1` in `base_url`:** `https://api.b.ai/v1`.

Do not guess model IDs from display names. Call `GET /v1/models` and use the returned `id`.

## Known model IDs (live `GET /v1/models`, 2026-09-12)

Do not use the old Harness example `deepseek-v4-flash` as the live ID.

| Role | Live `id` | context_length |
|---|---|---|
| DeepSeek Flash (default for this install) | `deepseek-v4.1-flash` | 1000000 |
| DeepSeek Pro | `deepseek-v4-pro` | 1000000 |

Display name `DeepSeek-V4.1-Flash` ≠ API id. Official docs still mention `deepseek-v4-flash` as a routed alias in some clients; Hermes should store the live list id.

## Add without flipping the main model

User default for “配置 b.ai 的 api” is **add the custom provider only**. Do **not** change `model.default` / `model.provider` unless they explicitly ask to switch.

Do **not** use `mcp_hermes_studio_use_provider_add` for this path — that tool also rewrites the active model/provider. Write YAML with Python `open()`:

```yaml
custom_providers:
  - name: b.ai
    base_url: https://api.b.ai/v1
    api_key: "sk-..."
    model: deepseek-v4.1-flash
    api_mode: chat_completions
    models:
      deepseek-v4.1-flash:
        context_length: 1000000
      deepseek-v4-pro:
        context_length: 1000000
```

If the file currently has `custom_providers: []`, replace that exact empty list with a YAML list of dicts. `hermes config set` will stringify the list and break it.

After write, verify types + that `model.provider` is still the previous value (often `openai-codex`).

Use later (new session):

```text
/model deepseek-v4.1-flash --provider custom:b.ai
```

## Quota vs bad key

`GET /v1/models` returning **200** means the key is accepted.

Chat returning **400** with:

```json
{"error":{"code":"insufficient_user_quota","message":"credit insufficient balance: balance=0 required=2"}}
```

is **not** a bad key, wrong `api_mode`, or WAF. Top up at chat.b.ai. Do not rotate the key or flip `api_mode` for this code.
