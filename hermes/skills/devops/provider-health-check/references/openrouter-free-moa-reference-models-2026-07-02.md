# OpenRouter Free Models for Hermes MoA — 2026-07-02 retest

Purpose: choose deterministic `:free` OpenRouter models as Hermes MoA reference models. Do **not** use `openrouter/free` as a fixed MoA reference because it randomly routes and can pick a model that returns empty `content`.

## Account/model inventory observed

- `/api/v1/models` returned 25 free/zero-priced model IDs.
- Account probe showed the key was present and authenticated; report only quota/limit fields, never the key.
- `google/gemma-4-31b-it:free` existed but was upstream 429 rate-limited during the test.

## Recommended MoA reference set

Use specific model IDs, ordered by expected value for MoA diversity:

```yaml
moa:
  presets:
    default:
      reference_models:
        - provider: openrouter
          model: qwen/qwen3-coder:free
        - provider: openrouter
          model: nvidia/nemotron-3-super-120b-a12b:free
        - provider: openrouter
          model: nvidia/nemotron-3-nano-30b-a3b:free
        - provider: openrouter
          model: google/gemma-4-31b-it:free
```

Rationale:

| Model | Role | Caveat |
|---|---|---|
| `qwen/qwen3-coder:free` | Best long-context/coding/reasoning candidate | Often 429 on free tier; keep as high-value slot if account balance/rate limits allow |
| `nvidia/nemotron-3-super-120b-a12b:free` | Main stable reference, 1M context | May include chain-of-thought-like preamble unless prompt says final only |
| `nvidia/nemotron-3-nano-30b-a3b:free` | Fast contrasting reference | Same preamble risk; still good latency/value |
| `google/gemma-4-31b-it:free` | Chinese/general/vision-adjacent diversity | Can 429 upstream; retest before relying on it |

## Retest results snapshot

Prompt used: Chinese JSON-only BTC short-term judgment, `max_tokens=120`, `temperature=0.2`.

| Model | Result | Latency | Note |
|---|---:|---:|---|
| `nvidia/nemotron-3-super-120b-a12b:free` | HTTP 200 | ~3.4s | Non-empty response, strong candidate |
| `nvidia/nemotron-3-nano-30b-a3b:free` | HTTP 200 | ~1.8s | Fastest useful candidate |
| `liquid/lfm-2.5-1.2b-instruct:free` | HTTP 200 | ~1.5s | Returns output but weak quality; fallback only |
| `google/gemma-4-26b-a4b-it:free` | HTTP 200 | ~13s | Returned `<pad>` garbage; avoid for MoA |
| `qwen/qwen3-coder:free` | HTTP 429 | ~1.3s | Keep as preferred if rate-limit clears |
| `qwen/qwen3-next-80b-a3b-instruct:free` | HTTP 429 | ~1.8s | Rate-limited |
| `google/gemma-4-31b-it:free` | HTTP 429 | ~1.1s | Upstream rate-limited |
| `openrouter/free` | HTTP 200 | ~5.3s | Routed to `openai/gpt-oss-20b:free` and returned empty content; do not use deterministically |
| `openai/gpt-oss-20b:free` | HTTP 200 | ~3.0s | Empty content in this test |
| `cohere/north-mini-code:free` | HTTP 200 | ~8.1s | Empty content in this test |
| `nvidia/nemotron-nano-12b-v2-vl:free` | HTTP 200 | ~122s | Empty content; too slow for MoA |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | HTTP 400 | ~0.8s | Provider error in this test |

## Testing pitfalls for future sessions

1. Score OpenRouter free models on both **HTTP status** and **message content**. HTTP 200 with empty `choices[0].message.content` is not useful for MoA unless the client explicitly extracts a non-content field the model uses.
2. Check `response.model` for `openrouter/free`; it tells which random backend was selected.
3. For MoA, prefer deterministic `:free` IDs and retest 429 models later rather than replacing them permanently with weak but currently available models.
4. Keep `liquid/lfm-2.5-1.2b-instruct:free` as an emergency cheap/fast fallback, not a primary reference model.
