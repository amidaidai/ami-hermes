# Ollama Cloud provider research notes

Use this reference when Tang Xi asks whether Ollama Cloud is worth using, what its plans/models/limits are, or whether it can be wired into Hermes as a provider.

## Official plan facts

Source: `https://ollama.com/pricing`, `https://docs.ollama.com/cloud`, `https://docs.ollama.com/openai`.

| Plan | Price | Cloud usage | Concurrent cloud models | Best fit |
|---|---:|---|---:|---|
| Free | $0 | Light usage; no fixed public token/request quota | 1 | Testing and light chat with smaller cloud models |
| Pro | $20/mo or $200/yr | 50x Free | 3 | Daily coding, research, heavier individual usage |
| Max | $100/mo | 5x Pro, about 250x Free | 10 | Sustained agents, multiple concurrent agents, heavy long sessions |
| Team | Coming soon | Shared team usage | TBD | Central billing, SSO, access controls, MDM, priority support |

## How usage is measured

- Officially **not** a fixed token or request cap.
- Usage reflects actual utilization of Ollama cloud infrastructure, primarily GPU time.
- Consumption varies by model size, request duration, output length, context length, and cache reuse.
- Each plan has both a session limit that resets every 5 hours and a weekly limit that resets every 7 days.
- The settings page shows session usage %, weekly usage %, reset timers, and plan tier.
- Pro/Max users can buy extra usage balance; included plan limits are consumed first.

## Model usage levels

Ollama labels cloud model cost from lighter level 1 models to heavy level 4 models. Official pricing gives examples:

| Usage level | Example | Note |
|---|---|---|
| Level 1 | `gpt-oss:20b` | Lighter; best for stretching Free quota |
| Level 4 | `deepseek-v4-pro` | Extra heavy; burns quota quickly |

Community guidance: on Free, stick to level 1–2 where possible. Heavy Kimi/DeepSeek/GLM-class models can work but may hit limits quickly.

## Cloud model access and API shape

- Cloud models require an Ollama account and `ollama signin` for local CLI use.
- Direct cloud API uses `https://ollama.com/api` with an API key from `https://ollama.com/settings/keys`.
- Local Ollama proxy remains `http://localhost:11434/api` and can offload cloud models when signed in.
- OpenAI-compatible endpoints are partly supported at `/v1/chat/completions`, `/v1/completions`, `/v1/models`, `/v1/embeddings`, `/v1/responses` and experimental `/v1/images/generations`.
- Supported OpenAI chat features include streaming, JSON mode, vision, tools, and reasoning controls; not all OpenAI fields are supported (`tool_choice`, `logprobs`, etc. have gaps depending on endpoint).

## Current cloud model families observed from official pages/API

Observed around 2026-07 from official cloud list/API tags. Treat as moving target; check `https://ollama.com/search?c=cloud` and `https://ollama.com/api/tags` live before configuring.

| Family/model | Notes |
|---|---|
| `gpt-oss:20b`, `gpt-oss:120b` | OpenAI open-weight reasoning/agent models; 20B is a good Free test candidate |
| `glm-5.2`, `glm-5.1`, `glm-5`, `glm-4.7` | Z.ai/GLM agentic engineering and coding family |
| `kimi-k2.7-code`, `kimi-k2.6`, `kimi-k2.5` | Moonshot/Kimi coding and multimodal agentic models |
| `deepseek-v4-flash`, `deepseek-v4-pro`, `deepseek-v3.1`, `deepseek-v3.2` | DeepSeek heavy reasoning models; Pro/Max preferred for Pro-class variants |
| `qwen3.5`, `qwen3-coder:480b`, `qwen3-coder-next` | Qwen general/coding cloud models |
| `minimax-m3`, `minimax-m2.7`, `minimax-m2.5`, `minimax-m2.1` | MiniMax coding/productivity/agentic models |
| `gemma4:31b`, `gemma3:*` | Google Gemma family; smaller/lighter models may be Free-friendly |
| `nemotron-3-ultra`, `nemotron-3-super`, `nemotron-3-nano:30b` | NVIDIA Nemotron family |
| `mistral-large-3:675b`, `devstral-*`, `ministral-*` | Mistral/dev coding families |
| `gemini-3-flash-preview` | Preview cloud model; deprecation risk |

## Free models: wording and caveat

Ollama does not provide a stable public "free model whitelist" on pricing/docs. It says Free can access cloud models, while Pro unlocks larger/more powerful cloud models. Community posts have reported Free access to examples such as:

- `minimax-m2.5:cloud`
- `kimi-k2.5:cloud`
- `glm-5:cloud`
- `gemma4:31b-cloud`
- `gpt-oss:20b`

Treat this as empirical and volatile. Verify with the user's account by pulling/running/listing before promising access.

## Community estimates and risk notes

Community estimates are useful for intuition but not billing-grade facts:

| Estimate/source type | Claim |
|---|---|
| Community token-equivalent estimates | Free about 5M tokens/week; Pro about 250M/week; Max about 1.25B/week |
| HN anecdote | Free qwen3-coder cloud hit an hourly/session wall after roughly 250k input tokens |
| GitHub/CodexBar issue | Settings page exposes session %, weekly %, reset timers, plan tier |
| Reddit/Note sentiment | Pro is usually enough for individual daily coding; Max for parallel agents |

Caveats:
- Limits and model availability have changed before.
- Peak-time latency, stream cutoffs, and instability are reported by community users.
- No strong production SLA; avoid positioning as mission-critical primary provider without fallback.

## Recommendation pattern for Tang Xi

For Tang Xi's Hermes / coding / multi-agent workflow:

1. Start with Free only to test network, account, API key, streaming, and model availability.
2. If using it for real coding/Hermes agent work, recommend Pro $20/mo as the default value point.
3. Recommend Max only if multiple concurrent agents or sustained long jobs are required.
4. Do not claim precise tokens as official; explain that official accounting is GPU-time based and only relative multipliers are published.
5. For Hermes provider setup, verify live first:
   - `https://ollama.com/api/tags` with API key if needed
   - `/v1/models` for OpenAI-compatible client path
   - `/v1/chat/completions` streaming and non-streaming
   - tool calling payload
   - long-context behavior and reset/usage page visibility

## Example commands

Local signed-in cloud path:

```bash
ollama signin
ollama pull gpt-oss:120b-cloud
ollama run gpt-oss:120b-cloud
```

Direct API path:

```bash
export OLLAMA_API_KEY=...
curl https://ollama.com/api/chat \
  -H "Authorization: Bearer $OLLAMA_API_KEY" \
  -d '{"model":"gpt-oss:120b","messages":[{"role":"user","content":"hi"}],"stream":false}'
```

OpenAI-compatible smoke test:

```bash
curl https://ollama.com/v1/chat/completions \
  -H "Authorization: Bearer $OLLAMA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss:20b","messages":[{"role":"user","content":"Say ok"}],"max_tokens":10}'
```

If the `/v1` host path differs in future docs, prefer the current official docs and verify with `/v1/models` before editing Hermes config.
