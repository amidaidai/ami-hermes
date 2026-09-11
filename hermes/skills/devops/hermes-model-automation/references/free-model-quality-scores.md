# Free Model Quality Scores (CostGoat + Community)

Sources:
- CostGoat quality scores: https://costgoat.com/pricing/openrouter-free-models
- OpenRouter popularity ranking: https://openrouter.ai/collections/free-models
- Community: Reddit r/LocalLLaMA, TeamDay.ai, Kilo Code rankings

## Quality Score Ranking (2026-06-23)

Only models confirmed free (pricing.prompt=0, completion=0) + tool-supporting.

| Rank | Model | Quality | Context | Capabilities |
|------|-------|---------|---------|-------------|
| 1 | google/gemma-4-31b-it:free | **65** 🥇 | 262K | Vision, Tools |
| 2 | nvidia/nemotron-3-super-120b-a12b:free | **60** 🥈 | 1M | Tools |
| 3 | openai/gpt-oss-120b:free | **55** 🥉 | 131K | Tools |
| 4 | google/gemma-4-26b-a4b-it:free | **52** | 262K | Vision, Tools |
| 5 | qwen/qwen3-coder:free | **41** | 1M | Tools |
| 6 | openai/gpt-oss-20b:free | **41** | 131K | Tools |
| 7 | nvidia/nemotron-3-nano-30b-a3b:free | **40** | 256K | Tools |
| 8 | nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free | **36** | 256K | Vision+Audio, Tools |
| 9 | qwen/qwen3-next-80b-a3b-instruct:free | **33** | 262K | Tools |
| 10 | nvidia/nemotron-nano-12b-v2-vl:free | **25** | 128K | Vision, Tools |
| 11 | meta-llama/llama-3.3-70b-instruct:free | **24** | 131K | Tools |
| 12 | nvidia/nemotron-nano-9b-v2:free | **24** | 128K | Tools |

## OpenRouter Popularity (from costgoat table)

| Model | Popularity Rank |
|-------|----------------|
| openrouter/owl-alpha | #5 |
| openai/gpt-oss-120b:free | #18 |
| nvidia/nemotron-3-super-120b-a12b:free | #12 |

## Multi-Modal (Vision) Free Models — Detailed

Only 5 free + tools + vision models on OpenRouter as of 2026-06-23:

| Model | Context | Modality | Quality |
|-------|---------|----------|---------|
| google/gemma-4-31b-it:free ⭐ | 262K | text+image+video→text | 65 |
| google/gemma-4-26b-a4b-it:free | 262K | text+image+video→text | 52 |
| nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free | 256K | text+image+audio+video→text | 36 |
| openrouter/free (route) | 200K | text+image→text | — |
| nvidia/nemotron-nano-12b-v2-vl:free | 128K | text+image+video→text | 25 |

## Best for Each Use Case

| Use Case | Top Pick | Why |
|----------|----------|-----|
| General purpose | gemma-4-31b:free | Quality 65 highest, Vision+Tools |
| Long context | nemotron-3-super:free | 1M ctx, quality 60 |
| Coding | qwen3-coder:free | 1M ctx, programming specialist |
| Vision/multimodal | gemma-4-31b:free | Best quality + vision + tools |
| Reasoning | nemotron-3-ultra:free | 1M ctx, frontier reasoning |
| Auto-routing | openrouter/free | Routes to cheapest free endpoint |
| Smart-routing | openrouter/owl-alpha | 1M ctx, routes intelligently |
