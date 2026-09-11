# Free-model probe recipe + Cross-model rule enforcement

Session: 2026-08-29. Two problems solved, both reproducible.

## A) Probing an OpenRouter free model WITHOUT shell-mangling the prefill

The naive `curl -d "{...中文多行prefill...}"` fails with **HTTP 400** — the shell
escapes Chinese quotes/newlines into invalid JSON. (Also the first probe returned a
blank html payload with `KeyError('choices')`, which was the same mangling.)

**Working path = Python `urllib` via execute_code**, never curl for CN payloads:

```python
import json, urllib.request, time
key = [l.split("=",1)[1].strip().strip('"') for l in
       open(r"C:\Users\Administrator\AppData\Local\hermes\.env",encoding="utf-8")
       if l.startswith("OPENROUTER_API_KEY")][0]
payload = {"model":"nvidia/nemotron-3-ultra-550b-a55b:free","max_tokens":650,
  "messages":[{"role":"system","content":SYSTEM_RULES},
              {"role":"user","content":"看下BTC"}]}
req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
with urllib.request.urlopen(req, timeout=120) as r:
    d = json.loads(r.read().decode("utf-8"))
c = d["choices"][0]["message"]["content"]
```

Key facts:
- **Real key lives in `~/.hermes/.env`, NOT the workspace `.env`.** The workspace
  `.env` held a 12-byte stub (`sk-or-xxxx` => HTTP 401, `resp_model=None`). The real
  one is `sk-or-v1-...` (73 bytes). Always read from `~/.hermes/.env`.
- `max_tokens>=650` for a real behavior probe; `<=120` truncates the reasoning tokens
  and the model looks like it "garbled"/refused (it was just cut off).
- Use `execute_code` (urllib) so the JSON body is built by Python, not the shell.

## B) Cross-model rule enforcement — prefill as the hard switch

The user's real worry: **"switch models, will it still follow the cockpit rules?"**
Answer: the rules are in a config-level **prefill**, not in the model, so every model
sees them. Concretely: `~/.hermes/prefill_trading_rules.json` (referenced by
`agent.prefill_messages_file: prefill_trading_rules.json` in config.yaml) injects a
user-message BEFORE the first user turn, every API call. Adding a
`【必加载技能·不分模型】做任何品种分析前，第一步必须用 skill_view 依次加载
crypto-multisource-analysis、tradingview-indicator-analysis...禁止凭记忆跳过技能直接答题`
makes any model (including a mediocre free one) assert that it MUST load skills first.

**Verified empirically**: nemotron-3-ultra-550b, given the prefill + "看下BTC", DID
replay the correct tier ("看下=轻量", "must first skill_view load ...",
"MEDIA first line, BTC main tf 15m"). So prefill works as an enforcement layer
independent of model.

**BUT** — two hard ceilings remain that prefill cannot fix, and they are model
capability, not memory/instruction:

1. **Tool-calling shape.** Ultra-550b, despite knowing the rules, emitted
   `{"tool":"skill_view","args":{"names":[...]}}` as a *JSON string in prose*, not a
   real tool_use block — it "knows to load skills" but CANNOT invoke them. A model
   that returns tools as text is NOT tool-capable (state 4 fails) and must not be the
   main cockpit model even though it recollects the rules.
2. **Fabrication when no real tool result.** nemotron-3-super-120b, lacking a live
   screenshot, *invented* `![BTC 15m chart](https://example.com/btc15m.png)` — a
   placeholder/fake. This is the P0 red line ("TV不可用不得用旧截图/假图冒充"). Free
   models that fabricate must be barred from producing live analysis cards.

## Selection conclusion (this session, reaffirmed)

- Main cockpit model stays DeepSeek `deepseek-v4-flash-vision-exp` (correct tool
  calls, real TV screenshots, fast enough).
- Free OpenRouter models (nemotron-3-super-120b, ultra-550b) are fine for **deep
  review / conflict arbitration / architecture audits** — the "no-time-pressure, does
  the thinking" roles — NOT the main cockpit seat, because they either won't call
  tools properly or will fabricate missing outputs.
