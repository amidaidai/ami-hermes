# Codex / Client TOML Config for Responses Providers (lingsuan example)

From 2026 session where user provided exact TOML and said "使用这个" (use this).

## Exact User Config
```toml
model_provider = "custom"
model = "gpt-5.5"
model_reasoning_effort = "high"
disable_response_storage = true

[model_providers.custom]
name = "灵算"
base_url = "https://lingsuan.top"
wire_api = "responses"
requires_openai_auth = true
```

## Application Steps (Hermes + Client)
- Hermes: already had `api_mode: codex_responses` in custom_providers for lingsuan.top in config.yaml.
- Client (e.g. ~/.codex/config.toml): 
  1. Backup the file.
  2. Replace proxy base_url with direct:
     `sed -i 's|base_url = "http://127.0.0.1:15721/v1"|base_url = "https://lingsuan.top"|' ~/.codex/config.toml`
  3. Remove proxy token line:
     `sed -i '/experimental_bearer_token = "PROXY_MANAGED"/d' ~/.codex/config.toml`
  4. Verify top of file matches user's block.
  5. Restart the client.

## Empirical Cache Result with This Exact Config
Direct curl to /v1/responses (3 identical calls, long stable prefix, gpt-5.5):
- Call 1: input_tokens=50 cached_tokens=0
- Call 2: input_tokens=50 cached_tokens=0
- Call 3: input_tokens=50 cached_tokens=0

Same result as previous tests. Responses wire exposes the metrics (prompt_cache_key present), but actual hits zero.

## Pitfall
Combining "store": false and "reasoning": {"effort": "high"} in one request body can cause "Failed to parse request body" on lingsuan. Test one at a time.

Add similar notes to mid-station-cache-quirks.md when new client configs appear. Link from SKILL.md cache section.
