# Model Availability Check on API Proxies

## Scenario

A user has an API key + endpoint for an OpenAI-compatible relay proxy, and a specific model (e.g., `deepseek-v4-flash`, `claude-opus-4-6`) returns errors even though the endpoint is reachable and other models work.

## Root Cause

Most Chinese relay proxies (aijws.com, timicc.cc, right.codes, ccapi.us, micuapi.ai) curate their own model catalogs. They only route a subset of upstream models through their gateway. Common patterns:

| Error Surface | Real Meaning |
|---|---|
| `{"error":{"message":"Service temporarily unavailable","type":"api_error"}}` | Model not carried by this proxy at all |
| `{"error":{"message":"Model not found"}}` | Wrong model name spelling or missing variant suffix |
| `{"error":{"message":"Insufficient balance"}}` | Key has no credits left |

## Diagnostic Steps

### 1. Double-check: one API, two model calls

Use Python (not curl — avoids MSYS quoting issues) to test both a known-good model and the problematic model with the SAME key and endpoint:

```python
import requests, json, sys

BASE = "https://api.aijws.com/v1"  # Replace with target endpoint
KEY = "sk-..."                       # Replace with test key
HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

def test_model(model_id):
    """Returns (success: bool, detail: str)"""
    try:
        r = requests.post(f"{BASE}/chat/completions",
            headers=HEADERS, timeout=20,
            json={"model": model_id, "messages": [{"role":"user","content":"say hi"}], "max_tokens":5})
        data = r.json()
        if r.status_code == 200 and "choices" in data:
            return True, f"OK: {data['choices'][0]['message']['content'][:30]}"
        else:
            err = data.get("error", {}).get("message", str(data))
            return False, f"HTTP {r.status_code}: {err[:100]}"
    except Exception as e:
        return False, f"EXCEPTION: {str(e)[:80]}"

# 1) List available models
models = requests.get(f"{BASE}/models", headers=HEADERS, timeout=10)
print("=== ALL MODELS ON THIS PROXY ===")
for m in models.json().get("data", []):
    print(f"  {m['id']}")
print()

# 2) Test a cheap, widely-available model first
ok, detail = test_model("gpt-4o-mini")
print(f"[KEY-VALIDATION] gpt-4o-mini → {detail}")

# 3) Test the problematic model
ok, detail = test_model("deepseek-v4-flash")
print(f"[TARGET] deepseek-v4-flash → {detail}")
```

### 2. Interpretation

| Pattern | Conclusion |
|---|---|
| Known-good model OK, target model → HTTP 200 + error body | Target model **not carried** on this proxy. Switch model or switch proxy. |
| Known-good model FAILS → HTTP 401 | Key is invalid or truncated (common after config recovery — see hex check in SKILL.md) |
| Known-good model FAILS → Connection timeout | Endpoint unreachable — check network, DNS, proxy settings |
| Known-good model FAILS → HTTP 404 | Wrong endpoint path — try `/v1/chat/completions` vs `/chat/completions` |
| Both models OK | Proxy working, issue is elsewhere (e.g., Hermes config/model mapping) |

## Real-World Example (2026-07-01)

```
Endpoint: https://api.aijws.com/v1
Key:      sk-24e24899...23910

Models listed: gpt-5.2, gpt-5.3, gpt-5.4, gpt-5.5, gpt-4o variants, gpt-image-*
               → OpenAI SERIES ONLY. No DeepSeek, no Claude.

Test gpt-5.5:     ✅ Returns "Hello!" in < 1s
Test deepseek-v4-flash: ❌ {"error":{"message":"Service temporarily unavailable","type":"api_error"}}

Verdict: aijws.com is an OpenAI-only proxy. deepseek-v4-flash will NEVER work here.
```

## Prevention

- **Before buying**: Ask the proxy provider for their model list or curl `/v1/models`. If they advertise "all OpenAI models" and you need DeepSeek/Claude, they won't have it.
- **Before debugging Hermes**: Always verify the model is **on the proxy's catalog** before touching Hermes config. Save hours of config-yak-shaving.
- **Fallback chains**: If a proxy's catalog is limited, set up fallback_providers in Hermes config.yaml so a model-not-available doesn't cascade to silent fallback to an even worse provider.
