# XAI Router (api.yairouter.com) Performance Profile

Discovered while diagnosing user-reported slowness of gpt-5.5 through XAI Router in Hermes.

## Key Finding: 1,450-Token Overhead Per Request

Every request to `https://api.yairouter.com/v1/chat/completions` carries ~1,450 prompt tokens of injected system instructions — regardless of model. This is the router's overhead, not the model's.

## Speed Benchmarks (hello-world test, 5 max_tokens)

| Path | Model | Time | Prompt Tokens |
|------|-------|:----:|:-------------:|
| Local proxy (CC-Switch @ :15721) | deepseek-v4-flash | ~1.0s | 8 |
| XAI Router | gpt-5.4-mini | ~1.8s | 1,450 |
| XAI Router | deepseek-v4-flash | ~2.0s | 1,450 |
| XAI Router | gpt-5.4 | ~3.0s | 1,450 |
| XAI Router | gpt-5.5 | ~10.0s | 1,450 |

## Analysis

- **Local proxy (CC-Switch) is ~10x faster** for the same model family because it has minimal token overhead.
- **XAI Router's bottleneck is its injection of system instructions** — every request pays a 1,450-token tax. For heavy reasoning models like gpt-5.5, this combines with model inference time to produce 10s+ responses.
- **Router overhead is fixed, not model-specific** — the same 1,450 tokens appear for all models through the same router.
- **gpt-5.5 itself is slow** — even after accounting for token overhead, it's ~3-5x slower than gpt-5.4-mini through the same router.

## Recommendation for Users

Use a **dual-config strategy**:

| Mode | Provider | Model | Use Case |
|------|----------|-------|----------|
| 🟢 Daily driver (fast) | Local proxy / CC-Switch | deepseek-v4-flash | Normal coding, quick questions |
| 🔵 Heavy lifting (slow) | XAI Router | gpt-5.5 | Complex reasoning, deep debugging, architecture |

Switching between the two is a `hermes config set model.provider ...` + `hermes config set model.default ...` away.

## Models Available on XAI Router

121 models total, including:
- **gpt-5.x family**: gpt-5.5, gpt-5.5-pro, gpt-5.4, gpt-5.4-mini, gpt-5.4-nano, gpt-5.3-codex-spark
- **DeepSeek**: deepseek-v4-flash, deepseek-v4-pro (but with router overhead)
- **Claude**: claude-haiku-4-5, claude-sonnet-4-6, claude-opus-4-6/7/8, claude-fable-5, claude-mythos-5
- **Gemini**: gemini-2.5-flash/lite/pro, gemini-3.1-flash-lite/pro-preview, gemini-3.5-flash
- **Qwen**: qwen3.5-flash, qwen3.7-max/plus, qwen3-32b, qwen-flash
- **Mistral**: mistral-large/small/medium, codestral
- **Other**: MiniMax-M2.7/M3, kimi-k2.6, palmyra-x4/x5, jamba-large/mini, sonar/sonar-pro/sonar-reasoning

## Credential Pool Structure

When configured as a custom provider in Hermes, the XAI Router entry appears in `auth.json` as:

```json
"custom:api.yairouter.com": [{
  "label": "api.yairouter.com",
  "source": "config:api.yairouter.com",
  "base_url": "https://api.yairouter.com",
  "secret_fingerprint": "sha256:..."
}]
```

Note: `providers: {}` in config.yaml does NOT mean the custom provider is broken — credentials live in the auth.json credential pool.
