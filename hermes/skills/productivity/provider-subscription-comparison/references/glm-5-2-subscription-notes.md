# GLM-5.2 subscription notes — 2026年7月7日

Condensed notes from a Hermes-provider subscription comparison where the user clarified that the target model is **GLM-5.2** and the metric is **included consumption allowance / value for money**, not generic multi-model access.

## Direct recommendation pattern

If the user wants GLM-5.2 specifically:

1. **Trial / cheapest entry:** OpenCode Go, $10/month after $5 first month.
2. **Sustained main plan:** Z.ai GLM Coding Plan Pro. Public page showed $72/month monthly, or about $50.4/month on annual billing (-30%).
3. **Heavy multi-agent use:** Z.ai GLM Coding Plan Max. Public page showed $160/month monthly, or about $112/month annualized.
4. **Fallback/router:** OpenRouter GLM-5.2 provider routing.
5. **Transparent energy billing:** NeuralWatt, especially fast/short variants, but do not assume full 1M GLM-5.2 beats OpenCode Go on per-request cost.

## Verified public data points used

### OpenCode Go

Official docs listed:

- Subscription: $5 first month, then $10/month.
- Included usage limits: $12 per 5 hours, $30 per week, $60 per month.
- GLM-5.2 included.
- Estimated GLM-5.2 request counts: about 880 requests per 5 hours, 2,150 per week, 4,300 per month.
- Typical GLM-5.2 request estimate: 700 input tokens, 52,000 cached tokens, 150 output tokens.
- Listed token prices: input $1.40/M, cached read $0.26/M, output $4.40/M.

Derived values:

- Typical token-cost request ≈ `700/1e6*1.40 + 52000/1e6*0.26 + 150/1e6*4.40 = $0.01516`.
- OpenCode Go package effective monthly value: $10 for ~4,300 GLM-5.2 requests ≈ $0.0023/request.

### Z.ai GLM Coding Plan

Public subscription page / devpack docs listed:

- Lite: $18/month monthly, about $12.6/month annualized.
- Pro: $72/month monthly, about $50.4/month annualized.
- Max: $160/month monthly, about $112/month annualized.
- All plans support GLM-5.2, GLM-5-Turbo, and GLM-4.7.
- Usage limits are prompt/workflow oriented:
  - Lite: up to ~80 prompts per 5 hours, ~400 prompts/week.
  - Pro: up to ~400 prompts per 5 hours, ~2,000 prompts/week.
  - Max: up to ~1,600 prompts per 5 hours, ~8,000 prompts/week.
- One prompt may invoke the model 15-20 times.
- GLM-5.2 and GLM-5-Turbo may deduct quota at higher multipliers: public docs stated peak 3x and off-peak 2x, with a limited-time off-peak 1x benefit through end of September.
- Peak hours: 14：00–18：00 (UTC+8 / same as Chinese local time).

Interpretation:

- Z.ai plan is best framed as coding-workflow quota, not raw request quota.
- For sustained GLM-only development, Pro is the first serious tier; Lite can be too tight after multiplier effects.

### Z.ai direct API

Official pricing page listed GLM-5.2:

- Input: $1.40/M tokens.
- Cached input: $0.26/M tokens.
- Cached input storage: limited-time free.
- Output: $4.40/M tokens.

Use direct API when usage is controlled and budgeted. Avoid letting unattended agents run without caps if using pure PAYG.

### OpenRouter GLM-5.2

OpenRouter model page showed GLM-5.2 with 1M context and multiple providers. Examples:

- Discounted providers around $0.9086/M input and $2.856/M output.
- Z.ai direct listing around $1.40/M input, $4.40/M output, $0.26/M cache read.
- OpenRouter also reported effective weighted averages after prompt caching, which can be much lower depending on cache hit rate.

Interpretation:

- OpenRouter is useful for fallback, routing, and price/latency benchmarking.
- It is PAYG; it is usually not the best fixed GLM-5.2 subscription if the user wants predictable monthly allowance.

### NeuralWatt

Pricing page showed:

- Basic: $20/month, 6 kWh included.
- Standard: $50/month, 16 kWh included.
- Pro: $100/month, 33 kWh included, overage $5/kWh.
- GLM-5.2 token alternative around input $1.45/M, cached input $0.36/M, output $4.50/M.
- GLM-5.2 average energy per typical request examples:
  - full GLM-5.2: about 1.75 Wh.
  - fast: about 1.18 Wh.
  - short: about 1.45 Wh.
  - short fast: about 414.72 mWh.

Derived values at $5/kWh PAYG:

- full: about $0.00875/request.
- fast: about $0.0059/request.
- short: about $0.00725/request.
- short_fast: about $0.00207/request.

Interpretation:

- NeuralWatt is attractive for transparency and fast/short variants.
- Full GLM-5.2 is not automatically cheaper than OpenCode Go.
- If comparing, distinguish 1M full-context GLM from 200K short/fast variants.

## Output lesson from this session

The user corrected that the prior generic recommendation over-weighted Nous Portal and under-weighted GLM-5.2-specific economics. Future comparisons should ask: “what model/workflow is the plan for?” and, if the user states GLM-5.2, lead with GLM-specific plan economics.

Also, the user objected to long Markdown tables not appearing as real tables on Telegram. For this class of report, generate visual table cards and keep text short.