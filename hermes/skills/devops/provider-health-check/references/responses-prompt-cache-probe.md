# Responses API prompt-cache hit probe for custom providers

Use this when a user reports 0% cache hit on a Hermes custom provider, especially `api_mode: codex_responses` / GPT-5.x routes.

## What to verify

1. Confirm the active route from `config.yaml`:
   - `model.default`
   - `model.provider`
   - matching `custom_providers[]` entry
   - `base_url`
   - `api_mode`
2. Confirm Hermes is sending a stable cache key:
   - Search request dumps under `C:/Users/<user>/AppData/Local/hermes/sessions/` for `prompt_cache_key`.
   - For `agent/transports/codex.py`, Hermes should generate a content-addressed key from `instructions + tools`, e.g. `pck_<sha256>`, rather than a per-session timestamp.
3. Do a direct two-call probe against the provider with the same long static prefix and the same `prompt_cache_key`.
4. Inspect returned usage fields, not the visible answer:
   - OpenAI/Responses style: `usage.input_tokens_details.cached_tokens`
   - Chat style: `usage.prompt_tokens_details.cached_tokens`
   - Anthropic style: `cache_read_input_tokens` / `cache_creation_input_tokens`

## Interpretation

| Observation | Likely meaning |
|---|---|
| `prompt_cache_key` absent | Hermes/request construction issue; inspect `api_mode` and transport path. |
| `prompt_cache_key` present, second identical call still `cached_tokens: 0` | Upstream does not support cache for this route/model, did not route both calls to same cache backend, or does not report cache fields. Treat as provider behavior unless direct OpenAI proves otherwise. |
| First call has write/creation tokens, second has read tokens | Cache is working; use this provider for cache-sensitive sessions. |
| Usage omits cache fields entirely | Provider may not expose cache accounting. Do not claim a hit from latency alone. |

## Minimal probe shape

Use a long but deterministic static prefix; keep the cache key fixed. Do not rely on normal chat text because short prompts may be below the provider's cache threshold.

```python
import json, time, requests

base_url = "https://provider.example"
api_key = "sk-..."  # read from config without printing
model = "gpt-5.5"
cache_key = "probe-static-prefix-v1"

instructions = "You are testing prompt caching. " + ("stable prefix. " * 1500)
payload = {
    "model": model,
    "instructions": instructions,
    "input": [{"role": "user", "content": "Reply exactly: ok"}],
    "store": False,
    "prompt_cache_key": cache_key,
    "reasoning": {"effort": "low", "summary": "auto"},
}
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

for i in range(2):
    t0 = time.time()
    r = requests.post(base_url.rstrip('/') + "/responses", headers=headers, json=payload, timeout=60)
    data = r.json()
    print(json.dumps({
        "run": i + 1,
        "seconds": round(time.time() - t0, 2),
        "status": r.status_code,
        "usage": data.get("usage"),
    }, ensure_ascii=False))
```

## Pitfalls found in live audits

- **Stale/duplicate custom-provider aliases can silently switch API mode.** If a provider appears twice (for example `custom:lingsuan.top` on `/responses` with `api_mode: codex_responses`, plus a stale `custom:lingsuan.top-codex` on `/v1/chat/completions` with `api_mode: chat_completions`), choosing the wrong alias sends `/chat/completions` requests with no `prompt_cache_key`. Cache reads will show 0 even though the same upstream supports Responses cache. Check both `config.yaml` and Web UI caches such as `~/.hermes-web-ui/cache/provider-model-catalog.json`.
- **Web UI usage DB can lag or mis-map cache counters.** Treat `session_usage.cache_read_tokens=0` as a dashboard symptom, not proof. Cross-check `~/.hermes/logs/agent.log` lines like `cache=26880/27319`, request dumps, and a direct streaming/non-streaming probe.
- **First call after a provider/model/system-prompt change is expected to be 0.** A healthy route should show reads on the second identical/near-identical call within the provider TTL.

## Reporting rule

Report in three buckets:

1. **Hermes request construction** — whether `prompt_cache_key` is present/stable and the request path is `/responses`, not `/chat/completions`.
2. **Provider behavior** — whether repeated direct calls produce non-zero cached tokens.
3. **Recommended routing** — if one custom provider stays at 0%, test another provider with the same model and promote the one that reports cache hits.

Avoid writing a durable rule that a provider “does not support cache” unless the same probe remains 0 across repeated attempts and the provider docs/usage fields confirm it. State it as current route behavior.
