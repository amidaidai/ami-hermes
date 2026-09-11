# api.aijws.com Provider Notes

## Overview

`api.aijws.com/v1` is an OpenAI-compatible API proxy (中转站) that carries GPT models (5.x series) and GPT Image models. It uses Cloudflare as CDN/WAF.

## Available Models (verified via Hermes Studio `/api/hermes/available-models`, 2026-07)

Text / Codex-style models:
- gpt-5.5, gpt-5.5-pro, gpt-5.5-openai-compact
- gpt-5.4, gpt-5.4-2026-03-05, gpt-5.4-mini, gpt-5.4-mini-2026-03-17, gpt-5.4-openai-compact
- gpt-5.3, gpt-5.3-codex, gpt-5.3-codex-spark
- gpt-5.2, gpt-5.2-2025-12-11, gpt-5.2-chat-latest, gpt-5.2-pro, gpt-5.2-pro-2025-12-11
- gpt-4o-audio-preview, gpt-4o-realtime-preview
- codex-auto-review

Image models:
- gpt-image-1, gpt-image-1.5, gpt-image-2

No DeepSeek, Claude, or other non-OpenAI models were listed for this provider in the Hermes Studio catalog.

**Hermes Studio discovery flow**:
1. Use `hermes_studio_api_openapi_get` with tag `Models` to confirm endpoints.
2. Call `GET /api/hermes/available-models` for current profile catalog.
3. In the response, read `groups[]` where `provider == "custom:api.aijws.com"`; `models` are currently visible in UI, `available_models` are provider-discovered candidates.

## Hermes Configuration

```yaml
custom_providers:
  - name: api.aijws.com
    base_url: https://api.aijws.com/v1
    api_key: "sk-..."  # user-provided key — DO NOT store from MCP tool (gets redacted to "***")
    model: gpt-5.4       # primary model per provider docs
    api_mode: chat_completions  # CRITICAL — NOT codex_responses!
    models:
      gpt-5.4:
        context_length: 400000
      gpt-5.5:
        context_length: 400000
```

## Known Issues

### 0. Cloudflare WAF 1010 / Python User-Agent block

**Error pattern**:
- `/v1/models` returns `HTTP 403` with bare body `error code: 1010`.
- `/v1/chat/completions` may return `HTTP 502` with bare body `error code: 502` when called from Python/OpenAI SDK default headers.
- The same chat request succeeds when a browser-like `User-Agent` is included.

**Cause**: Cloudflare WAF/CDN rules on `api.aijws.com` can block or mishandle non-browser Python/OpenAI SDK default request headers.

**Resolution**: Add `model.default_headers` as a real YAML dict, not a string:
```yaml
model:
  default_headers:
    User-Agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    Accept: "application/json"
```

**Verification pattern**: Test `/v1/chat/completions` with the configured key, `api_mode: chat_completions`, and browser UA. In the observed 2026-07 session, `gpt-5.5`, `gpt-5.4`, `gpt-5.3`, and `gpt-5.2` all returned `HTTP 200` with `OK`; `gpt-4o` returned `HTTP 503 Service temporarily unavailable` and should not be used as the primary model on this provider.

### 1. Cloudflare 502 origin_bad_gateway

**Error pattern**: Cloudflare error with `error_category: origin`, `error_name: origin_bad_gateway`, includes `ray_id`.

**Cause**: The origin server behind Cloudflare returned an invalid/incomplete response. All models fail simultaneously with 502 (gpt-5.x) or 503 (gpt-4o).

**Resolution**: Server-side issue — wait for provider to fix. No client-side config change can fix it.

### 2. API key INVALID_API_KEY

This proxy can reject keys with `401 INVALID_API_KEY` if:
- Key was truncated by Hermes redaction (stored as `"***"` in config)
- Key expired or was revoked by provider
- Key hit usage/rate limit

### 3. api_mode Mismatch

Setting `api_mode: codex_responses` causes 502 (no Cloudflare ray_id, just `Service temporarily unavailable`). Must be `chat_completions`.

## Client Setup (from provider docs)

### Cherry / OpenClaw / Gemini CLI / OpenAI-compatible software
1. Type: OpenAI Compatible
2. Name: Toska API
3. Base URL: `https://api.aijws.com/v1`
4. API Key: full key from provider console
5. Model: `gpt-5.4` (primary), `gpt-5.5` (fallback)

### GPT Image API
- POST `https://api.aijws.com/v1/images/generations`
- Header: `Authorization: Bearer <key>`
- Body: `{"model": "gpt-image-2", "prompt": "...", "size": "1024x1024"}`

### Codex (supports_websockets = false)
Codex tries WebSocket first by default, which fails on this proxy (no WebSocket support). Add to `~/.codex/config.toml`:
```toml
supports_websockets = false
```
This forces Codex to use HTTP from the first attempt, eliminating the 75-second reconnect delay.
