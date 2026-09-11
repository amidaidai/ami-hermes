# CLI-Side Provider Model Cache (provider_models_cache.json)

The **CLI-side provider model cache** at `~/.hermes/provider_models_cache.json` is separate from the Web UI cache (`~/.hermes-web-ui/cache/provider-model-catalog.json`). It records what models each provider's API discovery endpoint returned during Hermes startup.

**Path (Windows):** `C:\Users\<user>\AppData\Local\hermes\provider_models_cache.json`

## Why This File Exists

Hermes auto-discovers available models from each configured provider by calling their `/v1/models` (or equivalent) endpoint at startup. The result is cached so subsequent launches don't re-discover. This is the **authoritative view of what models the CLI session can actually use** — a model present here can be invoked; one absent from here was either never discovered or explicitly filtered out.

## File Structure

```json
{
  "deepseek": {
    "fp": "bdf5a88fcaf16b96",
    "at": 1781494130.628914,
    "models": ["deepseek-v4-flash", "deepseek-v4-pro"]
  },
  "openrouter": {
    "fp": "4797f0fa6670733f",
    "at": 1781494128.1939082,
    "models": [
      "anthropic/claude-opus-4.8",
      "openai/gpt-5.5",
      "poolside/laguna-m.1:free",
      "nvidia/nemotron-3-super-120b-a12b:free",
      "nvidia/nemotron-3-ultra-550b-a55b:free"
    ]
  }
}
```

- `fp` — a content fingerprint (hash of the raw API response); changes when the provider's model list changes
- `at` — last discovery timestamp (unix epoch seconds)
- `models` — array of model IDs the provider returned

## OpenRouter Free Model Identification

### Method 1: `:free` suffix (in this file)

On OpenRouter, the `:free` suffix in a model ID means it is a **free-tier model** (no API key charges). This cache typically only has a few free models because OpenRouter's `/v1/models` discovery endpoint may return a limited subset:

| Model | Free? |
|-------|-------|
| `poolside/laguna-m.1:free` | ✅ Free |
| `nvidia/nemotron-3-super-120b-a12b:free` | ✅ Free |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | ✅ Free |
| `anthropic/claude-opus-4.8` | ❌ Paid |
| `openai/gpt-5.5` | ❌ Paid |

**Note:** The `:free` suffix is specific to OpenRouter's convention. Some free models (like `openrouter/owl-alpha`) do NOT have a `:free` suffix but are still $0 cost.

### Method 2: models_dev_cache.json (full catalog — more comprehensive)

**This is the authoritative source for ALL free OpenRouter models.** The file at `%APPDATA%/hermes/models_dev_cache.json` (Windows) or `~/.hermes/models_dev_cache.json` contains the full model catalog synced from Hermes' model catalog API, with complete pricing info per model.

Query it to find all models where both input and output cost are $0:

```bash
cat /c/Users/<user>/AppData/Local/hermes/models_dev_cache.json | python -c "
import json, sys
data = json.load(sys.stdin)
or_models = data.get('openrouter', {}).get('models', {})
for k, v in sorted(or_models.items()):
    cost = v.get('cost', {})
    if isinstance(cost, dict) and cost.get('input') == 0 and cost.get('output') == 0:
        ctx = v.get('limit', {}).get('context', '?')
        print(f'{k}  ({v.get(\"name\",\"?\")})  context={ctx}')
"
```

This reveals **26+ free models** (vs ~3 from Method 1), including:
- `openrouter/owl-alpha` — 1M context, agent-capable, no `:free` suffix but $0 cost
- `nvidia/nemotron-3-ultra-550b-a55b:free` — 1M context, frontier reasoning
- `google/gemma-4-31b-it:free` — 262K context, Google's latest
- `openai/gpt-oss-120b:free` — 131K context, OpenAI's open model
- `qwen/qwen3-coder:free` — 262K context, code specialist
- `poolside/laguna-m.1:free` — 262K context, coding agent
- `meta-llama/llama-3.3-70b-instruct:free` — 65K context
- `openrouter/free` — meta-router that auto-selects best available free model

### Method 3: OpenRouter website (official collection)

The OpenRouter website maintains a curated free models collection page:
https://openrouter.ai/collections/free-models

This also lists free models that may not yet be in the Hermes model catalog cache (e.g., `bytedance-seed/seedream-4.5`), so cross-reference web data when the local cache seems incomplete.

## When to Use Each Cache

| Scenario | Use This | Use Web UI Cache |
|----------|----------|------------------|
| User asks "what models can I use in the CLI?" | ✅ Yes | ❌ |
| User asks "what models appear in the dashboard?" | ❌ | ✅ Yes |
| User asks about OpenRouter free models | ✅ Best source (`:free` suffix visible) | Depends on whitelisting |
| User says "a model I used before is gone" | ✅ Check `fp` + `at` for cache staleness | ❌ |
| Diagnosing model-not-found errors | ✅ Check if the model is in the list at all | ❌ |
| Checking Web UI model visibility filtering | ❌ | ✅ |

## Pitfalls

- **Cache can be stale** — if `at` is more than a few hours old and models changed on the provider side, the cache won't reflect it. Force re-discovery by deleting the file or restarting Hermes.
- **Not the same as "authorized"** — a model being in this cache means it was discovered, not necessarily that the API key has access to it. Some providers return all available models regardless of key tier.
- **`models_dev_cache.json` is different** — this is a separate cache for development-time exploration (model benchmarks, capability tags). Don't confuse the two.
