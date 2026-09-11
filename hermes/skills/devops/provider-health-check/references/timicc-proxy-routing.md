# timicc custom provider proxy-routing benchmark

Session pattern captured for future custom-provider latency diagnosis.

## Context

A Hermes custom provider was configured as:

- Provider: `custom:timicc.com`
- Base URL: `https://timicc.com`
- Model: `gpt-5.5`
- Local proxy env: `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` pointed at `http://127.0.0.1:7897`
- System proxy process: Clash Verge / `verge-mihomo.exe`

The user asked whether slow responses were caused by the proxy or model/provider routing.

## Benchmark method

Use the same endpoint, model, prompt, and token cap for every path. Run 8-12 repetitions and compare distribution, not a single request.

Paths to compare:

1. `env_default`: `requests.Session().trust_env = True`, no explicit `proxies`.
2. `force_proxy`: `trust_env = False`, `proxies = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}`.
3. `force_direct`: `trust_env = False`, `proxies = {}`.

Record:

- Success count and failures
- HTTP status codes
- Median latency
- Average latency
- Min/max latency
- p90 when enough samples exist

## Observed result in this session

Endpoint: `https://timicc.com/v1/chat/completions`  
Model: `gpt-5.5`  
Prompt: one short Chinese reply  
Samples: 12 per path

- Forced proxy `127.0.0.1:7897`: median `2.774s`, avg `3.469s`, max `6.894s`, failures `0/12`.
- Forced direct: median `1.764s`, avg `2.816s`, max `8.735s`, failures `0/12`.
- Env default: median `2.534s`, avg `3.196s`, max `10.096s`, failures `0/12`.

Conclusion: direct routing was materially better on median/average latency, while long-tail spikes still existed, indicating some backend/model-router variability too.

## Durable fix pattern

Do not remove all proxy variables if the user relies on proxy for other APIs. Add the provider hostname to both uppercase and lowercase no-proxy variables in Hermes `.env`:

```bash
NO_PROXY=localhost,127.0.0.1,<existing-hosts>,timicc.com
no_proxy=localhost,127.0.0.1,<existing-hosts>,timicc.com
```

Keep:

```bash
HTTP_PROXY=http://127.0.0.1:7897
HTTPS_PROXY=http://127.0.0.1:7897
ALL_PROXY=http://127.0.0.1:7897
```

Then restart or reload Hermes so the new environment is loaded.

## Verification pattern

After editing `.env`, simulate a fresh process loading that `.env` and repeat a shorter 6-8 request benchmark with `trust_env=True`. Confirm the provider still returns HTTP 200 and median/average latency is closer to direct than forced proxy.

## Pitfall

A locally open port is not necessarily a usable HTTP proxy. In this session `127.0.0.1:7892` was listening, but HTTP-proxy requests to it failed with connection resets. Probe candidate ports before recommending them.
