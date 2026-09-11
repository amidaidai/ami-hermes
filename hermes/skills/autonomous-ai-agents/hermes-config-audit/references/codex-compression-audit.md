# Codex Compression Audit

## Purpose

Use this reference when checking whether a Hermes session using an `openai-codex` provider will compress automatically. It records the evidence sequence and the interpretation rules; current values must always be read live.

## Safe evidence sequence

```bash
hermes config path
hermes config get model
hermes config get compression
hermes config get auxiliary.compression
hermes config get model.context_length
hermes config check
```

`hermes config get model.context_length` may return `Config key not set`. That is a valid finding: the absolute context capacity is not explicitly configured and should be reported as unknown unless a runtime/model catalog lookup supplies it. Never read or print `.env` merely to answer a compression question.

## Field interpretation

| Field | Meaning |
|---|---|
| `compression.enabled` | Hermes local compressor master switch |
| `threshold` | Fraction of effective context window used when `threshold_tokens` is null |
| `threshold_tokens` | Absolute trigger when explicitly set |
| `target_ratio` | Tail-retention ratio used by Hermes compression |
| `codex_app_server_auto` | App Server compaction route: `hermes`, `native`, or `off` |
| `codex_responses_native` | Direct Codex Responses server-side compaction switch |
| `codex_responses_compact_threshold` | Native Responses trigger; do not call it active while native compaction is disabled |
| `codex_gpt55_autoraise` | GPT-5.5 Codex OAuth special-case threshold only |
| `in_place` | Stable same-id compaction when true; legacy session rotation when false |
| `auxiliary.compression.provider/model` | Provider/model used to summarize; `auto` + empty model means automatic selection |

## Verified configuration example from an audit

The inspected runtime reported:

```text
model.default = gpt-5.6-luna
model.provider = openai-codex
compression.enabled = true
compression.threshold = 0.5
compression.threshold_tokens = null
compression.target_ratio = 0.2
compression.tail_mode = lean
compression.protect_last_n = 20
compression.codex_app_server_auto = hermes
compression.codex_responses_native = false
compression.codex_responses_compact_threshold = 200000
compression.in_place = false
auxiliary.compression.provider = auto
auxiliary.compression.model = empty
model.context_length = not set
config check = passed (version 39)
```

This means the active safety net is Hermes' fractional-threshold compressor. Codex native compaction is not active on either inspected route, and the `200000` native threshold is not evidence that native compaction is enabled. Because the context length was not configured, the audit could say “approximately 50% of the effective window” but could not honestly state the corresponding number of tokens. The GPT-5.5 autoraise flag was irrelevant to the GPT-5.6 model in this example.

## Reporting rule

Lead with “automatic compression: on/off”. Then distinguish:

1. Hermes local compaction;
2. Codex App Server native compaction;
3. Codex Responses native compaction;
4. the known/unknown absolute token trigger; and
5. session-id behavior (`in_place`).

Do not claim that a model name alone determines compression behavior; the route flags and live resolved configuration do.