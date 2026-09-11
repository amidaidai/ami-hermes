# Provider Cache Diagnostics

Use this reference when a Hermes provider/model shows unexpectedly low cache hit rate.

## What to check first

A low reported cache hit rate can mean either:
1. the prompt prefix genuinely changed, or
2. the provider stopped returning cache usage fields.

Do not jump to prompt churn. In Hermes logs, cache is only visible when normalized cache-read tokens are non-zero.

## Fields Hermes depends on

| API mode | Expected provider usage field | Hermes symptom if missing |
|---|---|---|
| Codex Responses | `usage.cachedInputTokens` | `API call #...` has no `cache=x/y` suffix; cache counted as 0 |
| Chat Completions | `usage.prompt_tokens_details.cached_tokens` | `API call #...` has no `cache=x/y` suffix; cache counted as 0 |
| Anthropic-style | cache read/write fields via native adapter | cache output depends on adapter/provider support |

## Minimal parser pattern

```python
import re, glob, collections

call_re = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} (?P<hour>\d{2}):[\d:,]+).*?"
    r"\[(?P<sid>[^\]]+)\].*?API call #(?P<num>\d+): "
    r"model=(?P<model>\S+) provider=(?P<provider>\S+) "
    r"in=(?P<inp>\d+) out=(?P<out>\d+) total=(?P<total>\d+) "
    r"latency=(?P<lat>[\d.]+)s(?: cache=(?P<cache>\d+)/(?:\d+) \((?P<pct>\d+)%\))?"
)

rows = []
for path in glob.glob(r"C:/Users/Administrator/AppData/Local/hermes/logs/agent.log*"):
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = call_re.search(line)
        if not m:
            continue
        d = m.groupdict()
        d["inp"] = int(d["inp"])
        d["cache"] = int(d["cache"] or 0)
        rows.append(d)

by_hour = collections.defaultdict(list)
for r in rows:
    by_hour[r["hour"]].append(r)

for hour, rs in sorted(by_hour.items()):
    inp = sum(r["inp"] for r in rs)
    cache = sum(r["cache"] for r in rs)
    zeros = sum(1 for r in rs if r["cache"] == 0)
    print(hour, "calls", len(rs), "zero", zeros, "hit%", round(cache / inp * 100, 1) if inp else 0)
```

For provider-specific diagnosis, extend the parser with `run_agent: OpenAI client created/closed` lines and attribute each session/call to `base_url` and request reason (`codex_stream_request`, `chat_completion_stream_request`, etc.).

## Interpretation checklist

| Pattern | Likely cause | Next action |
|---|---|---|
| High hit rate for hours, then all-zero after a timestamp | provider/upstream stopped returning usage cache fields | ask provider to pass through cache usage fields |
| First call low, later calls high | normal cache warmup or TTL | no fix needed |
| New session after long pause low, later high | TTL expired | consider provider TTL; do not treat as bug |
| `/responses` all-zero but `/v1/chat` high, or inverse | endpoint-specific usage-field mapping | test both modes and pin the mode that reports correctly |
| Low hits coincide with model/base URL switching | cache namespace changed | stabilize provider/model/base URL |
| Low hits after compression or tool schema changes | prompt prefix genuinely changed | inspect system prompt/tool snapshot changes |

## Escalation wording

Ask the provider:

> Please verify whether this endpoint passes through cache usage fields. For Responses API we need `usage.cachedInputTokens`; for Chat Completions we need `usage.prompt_tokens_details.cached_tokens`. Hermes can only report cache hits when those fields are present and non-zero.

Avoid saving a durable claim that a provider is broken; record the diagnostic method and exact fields instead.
