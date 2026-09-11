# OpenRouter Free Models — MoA Shortlist (session note)

Date: 2026-07-02

## Practical ranking for MoA reference models

| Rank | Model | Why |
|---|---|---|
| 1 | `nvidia/nemotron-3-super-120b-a12b:free` | Best balance of quality, speed, and uptime; 1M context |
| 2 | `nvidia/nemotron-3-ultra-550b-a55b:free` | Highest-capacity NVIDIA free option; stronger but slower/more variable |
| 3 | `qwen/qwen3-coder:free` | Excellent coding/repo reasoning when the free endpoint is available |
| 4 | `google/gemma-4-31b-it:free` | Strong multimodal + multilingual option; direct routing can vary by region/provider |

## Page / provider facts to re-check before trusting stale assumptions

- `openrouter/free` is random routing, not deterministic.
- Model pages show provider-specific latency / throughput / uptime; use them to compare free endpoints instead of relying only on the model headline.
- For `qwen/qwen3-coder:free`, the OpenRouter model page highlights 1M context and agentic coding focus.
- For `nvidia/nemotron-3-super-120b-a12b:free`, the OpenRouter model page shows 1M context and very strong provider uptime/throughput.
- For `nvidia/nemotron-3-ultra-550b-a55b:free`, the OpenRouter model page shows 1M context but slower throughput than Super.

## Session-specific observation

In this session, direct testing showed:
- `nvidia/nemotron-3-super-120b-a12b:free` was the most consistently usable.
- `nvidia/nemotron-3-ultra-550b-a55b:free` worked but was less stable.
- `qwen/qwen3-coder:free` and `google/gemma-4-31b-it:free` could surface upstream/provider routing issues depending on request and route.

Use this file as a quick checklist, but prefer live `/models` page data plus one short probe before changing MoA defaults.
