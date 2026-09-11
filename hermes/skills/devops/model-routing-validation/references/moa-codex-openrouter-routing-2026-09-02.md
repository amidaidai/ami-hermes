# MoA + OpenRouter Free + Codex Luna/Sol 路由参考

## Scope

This note records the non-secret runtime evidence and design used for the
2026-09-02 Hermes profile audit. It is a reference for future model-routing
reviews, not a promise that volatile free endpoints will remain available.

## Observed active profile

- Hermes: v0.20.6.
- Main route: `openai-codex:gpt-5.6-luna`.
- MoA preset `default` existed but had `enabled: false`; therefore reference
  fan-out was disabled and the active top-level route was not MoA.
- Current references were `openrouter:minimax/minimax-m3:free` and
  `openrouter:nvidia/nemotron-3-ultra-550b-a55b:free`.
- Current aggregator was `openai-codex:gpt-5.6-luna`.
- `reference_max_tokens` was unset; aggregator `max_tokens` was 5000.
- No top-level `fallback_providers` or explicit delegation model/provider was
  configured. Auxiliary tasks were set to `auto`.
- The config check passed and both OpenRouter and OpenAI Codex credentials had
  configured entries. Credentials themselves were never printed.

## Live probe results

Each probe used `hermes chat -q` and a real tool intent where marked. Elapsed
seconds include Hermes startup, prompt injection, provider queueing, network
round-trip, and tool handling; they are not pure model latency.

| Route | Probe | Elapsed | Interpretation |
|---|---|---:|---|
| `openai-codex:gpt-5.6-luna` | real terminal call and result | 18s | tool-capable in this run |
| `openai-codex:gpt-5.6-sol` | real terminal call and result | 18s | tool-capable in this run |
| `openrouter:minimax/minimax-m3:free` | real terminal call and result | 41s | usable reference candidate |
| `openrouter:nvidia/nemotron-3.5-lightning:free` | real terminal call and result | 32s | usable faster heterogeneous candidate |
| `openrouter:nvidia/nemotron-3-ultra-550b-a55b:free` | real terminal call and result | 69s | usable but too slow for every short turn |
| `openrouter:openrouter/free` | real terminal call and result | 33s | reachable once, but dynamic and non-deterministic |
| `openrouter:nvidia/nemotron-3-super-120b-a12b:free` | request | failed: upstream temporarily overloaded | do not promote until re-probed |
| `openrouter:cohere/north-mini-code:free` | request | timed out at 180s | do not promote from this probe |

The Codex context cache contained 272000 tokens for both
`gpt-5.6-luna@https://chatgpt.com/backend-api/codex` and
`gpt-5.6-sol@https://chatgpt.com/backend-api/codex`. Do not replace this
runtime value with a public catalog maximum.

## Recommended two-preset shape

For short-turn trading, keep the everyday fan-out small and bounded:

```yaml
moa:
  default_preset: default
  active_preset: default
  presets:
    default:
      enabled: true
      reference_models:
        - provider: openrouter
          model: minimax/minimax-m3:free
        - provider: openrouter
          model: nvidia/nemotron-3.5-lightning:free
      aggregator:
        provider: openai-codex
        model: gpt-5.6-luna
      reference_max_tokens: 600
      max_tokens: 5000
      fanout: user_turn
      reference_temperature: 0.35

    deep:
      enabled: true
      reference_models:
        - provider: openrouter
          model: minimax/minimax-m3:free
        - provider: openrouter
          model: nvidia/nemotron-3-ultra-550b-a55b:free
      aggregator:
        provider: openai-codex
        model: gpt-5.6-sol
      reference_max_tokens: 1000
      max_tokens: 6500
      fanout: user_turn
      reference_temperature: 0.35
```

Use `default` for ordinary analysis and `deep` only for major data conflicts,
event windows, or architecture/risk review. Do not add a third preset until
shadow comparisons show independent out-of-sample value.

If MoA should be the persistent main route, the top-level model selection must
also be changed to:

```yaml
model:
  default: default
  provider: moa
```

A direct `openai-codex` fallback such as `gpt-5.6-sol` is an emergency direct
route, not a second aggregator. Never set delegation to the `moa` provider or
create recursive MoA trees.

## Operational lessons

1. Fixed `:free` IDs are preferable to `openrouter/free` for persistent
   advisors because they preserve model identity, role reproducibility, and
   more predictable latency.
2. Luna is the default aggregator because it was already the active user
   route and passed the real tool probe. Sol is a separate deep aggregator or
   direct fallback; there was no live evidence that it should replace Luna on
   every turn.
3. Hermes runs reference advisors in parallel, but the turn waits for the
   slowest advisor. `reference_max_tokens` and `fanout: user_turn` are the
   main latency controls for this design.
4. References do not execute tools. The installed MoA loop flattens tool calls
   and results into text for advisory review; the aggregator retains the normal
   tool schema and must perform live collection and artifact generation.
5. A full reference→aggregator MoA fan-out was not claimed as verified in this
   audit because the active preset was disabled. Individual route probes and
   the disabled-preset aggregator path are not equivalent to an enabled full
   MoA run.
6. After a multi-reference edit, verify `hermes moa list`, the top-level
   `model.provider/model.default`, each slot, `enabled`, and a real
   reference→aggregator→tool-result test before calling the route production
   ready.
