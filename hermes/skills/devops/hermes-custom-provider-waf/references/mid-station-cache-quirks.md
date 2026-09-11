# Mid-Station Prompt Cache Quirks (codex_responses / Responses API)

Captured during diagnosis of low input/output cache reads on lingsuan.top (gpt-5.5) in Hermes (2026 session).

## Observed Configuration
```toml
# client / Codex-style
wire_api = "responses"
model = "gpt-5.5"
model_reasoning_effort = "high"
disable_response_storage = true

[model_providers.custom]
name = "灵算"
base_url = "https://lingsuan.top"
```

Hermes equivalent:
```yaml
custom_providers:
  - name: lingsuan.top
    base_url: https://lingsuan.top
    api_mode: codex_responses   # or responses
    model: gpt-5.5
```

Used in delegation aggregator for gpt-5.5.

## Key Findings from Live Tests
- Responses path returns structured usage:
  ```json
  "usage": {
    "input_tokens": 52,
    "input_tokens_details": { "cached_tokens": 0 },
    ...
  }
  ```
  plus `prompt_cache_key` and `prompt_cache_retention: "24h"`.
- But cached_tokens stayed **0** across 3 identical calls (input_tokens flat).
- Chat/completions path reports `prompt_tokens` (also flat, ~52) but **no cache fields** at all.
- Mid-station pooling + load balancing destroys KV cache affinity — identical prefixes often hit different backend instances.
- High reasoning + tool schemas + long history + delegation context destroy prefix stability.
- Hermes local caches (`response_cache`, `prompt_caching` ttl 300s/5m) ≠ upstream model cache discount.
- Even when provider exposes cache metadata, actual discount frequently zero for these workloads.

## Recommended Verification (key-safe, repeatable)
Extract without printing full key:
```bash
LING_KEY=$(sed -n '/- name: lingsuan.top/,/^[ ]*- name:/p' /c/Users/Administrator/AppData/Local/hermes/config.yaml \
  | grep -A1 'api_key:' | head -1 | sed 's/.*api_key: *//;s/"//g;s/,//g;s/ //g')
BASE="https://lingsuan.top"
MODEL="gpt-5.5"
```

Responses test (3x identical):
```bash
for i in 1 2 3; do
  echo -n "Responses Call $i: "
  curl -s -X POST "$BASE/v1/responses" \
    -H "Authorization: Bearer $LING_KEY" -H "Content-Type: application/json" \
    -d '{"model":"'$MODEL'","instructions":"Fixed system... long stable prefix...","input":"Reply exactly: CACHE-REPEAT-TEST","max_output_tokens":5}' \
  | python -c '
import sys,json
d=json.load(sys.stdin)
u=d.get("usage",{})
cd = u.get("input_tokens_details",{}).get("cached_tokens",-1)
print("input_tokens=" + str(u.get("input_tokens")) + " cached=" + str(cd))
'
  sleep 2
done
```

Chat comparison (same prompt):
```bash
... similar loop to /v1/chat/completions with messages array ...
# Expect flat prompt_tokens and no cache fields
```

## Pitfalls
- Presence of `cached_tokens` field does **not** mean hits occur — it can be exposed but always 0.
- Responses/codex_responses is the wire that at least reports cache metrics on providers that support it.
- Delegation aggregator + high reasoning are cache killers.
- Do not confuse local Hermes response_cache with upstream savings. Always inspect the actual `cached_*` / `input_tokens_details` fields.

## Related Patterns
- lingsuan.top: Codex/GPT-5.5 focused, ¥1=$1 pricing, OpenAI-compatible, but cache passthrough weak on responses (empirical hits 0).
- General Chinese mid-stations: Prefer `chat_completions` (or wire_api chat) for cache-sensitive work.
- Common: dual-provider (chat path for daily/cache, responses only for Codex-specific needs).

## Session-Specific Test Data
- Responses (lingsuan gpt-5.5): input_tokens=52, cached=0 (x3)
- Chat (same): prompt_tokens=52 (x3), no cache fields reported
- Confirmed /v1/responses returns 200 + full response object with prompt_cache_key

Update this file + the cache section in SKILL.md when new providers or wire behavior is observed.