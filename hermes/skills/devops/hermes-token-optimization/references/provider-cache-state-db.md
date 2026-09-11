# Provider cache diagnostics via Hermes state.db

Use this when a user says “缓存没有 / cache is missing” and the active provider is a custom OpenAI-compatible endpoint.

## What this session taught

A zero cache display in the current turn is not enough to conclude Hermes caching is broken. Hermes may be working correctly while the active provider omits the usage fields Hermes can parse.

Observed pattern:
- Active model/provider: `gpt-5.5` via `custom:jbbtoken.cn`.
- Active custom provider used `api_mode: chat_completions`.
- Current session had high `input_tokens` but `cache_read_tokens=0` and `cache_write_tokens=0`.
- The same `state.db` contained many recent sessions with non-zero `cache_read_tokens`, including cron and CLI sessions.
- Source code confirmed Chat Completions cache extraction only reads `response.usage.prompt_tokens_details.cached_tokens` and `cache_write_tokens`.

Conclusion pattern:
- If current session cache is zero but historical sessions in `state.db` show non-zero cache, Hermes cache accounting/database are not broken.
- For Chat Completions custom providers, the most likely cause is missing `usage.prompt_tokens_details.cached_tokens` passthrough from the relay, or a real miss caused by changed prompt/tool prefix.

## Fast state.db query

```bash
python - <<'PY'
import sqlite3, pathlib
p = pathlib.Path(r'C:/Users/Administrator/AppData/Local/hermes/state.db')
con = sqlite3.connect(p)
con.row_factory = sqlite3.Row
cols = [r['name'] for r in con.execute('pragma table_info(sessions)')]
order = 'ended_at' if 'ended_at' in cols else 'started_at'

print('recent sessions usage:')
for r in con.execute(f'''
    select id, source, title, model,
           input_tokens, output_tokens,
           cache_read_tokens, cache_write_tokens, reasoning_tokens,
           estimated_cost_usd, cost_status, cost_source,
           started_at, ended_at
    from sessions
    order by coalesce({order}, started_at) desc
    limit 15
'''):
    print(dict(r))

print('\ncache nonzero count:')
print(dict(con.execute('''
    select count(*) as n,
           sum(cache_read_tokens) as read_sum,
           sum(cache_write_tokens) as write_sum
    from sessions
    where coalesce(cache_read_tokens,0)>0
       or coalesce(cache_write_tokens,0)>0
''').fetchone()))
PY
```

## Source-code checkpoints

For `api_mode: chat_completions`, inspect:

```text
agent/transports/chat_completions.py::extract_cache_stats
```

Expected logic:

```python
details = getattr(usage, "prompt_tokens_details", None)
cached = getattr(details, "cached_tokens", 0) or 0
written = getattr(details, "cache_write_tokens", 0) or 0
```

For `api_mode: codex_responses`, Hermes usually maps cache reads from a Responses-style field such as `usage.cachedInputTokens`.

## Interpretation table

| Evidence | Interpretation |
|---|---|
| Current session cache 0, historical sessions non-zero | Hermes accounting is functioning; focus on provider/mode/prompt stability |
| All sessions cache 0 after provider switch | Provider likely does not pass through cache usage fields, or route changed |
| Chat Completions cache 0, Responses cache non-zero | Chat relay likely omits `prompt_tokens_details.cached_tokens` |
| First call per new session 0, later calls non-zero | Normal warmup / cache TTL behavior |
| `cost_status: unknown` for custom provider | Hermes lacks pricing/usage metadata; do not infer billing from displayed cost alone |

## Recommended user-facing conclusion

Say clearly:

> 缓存功能没坏；数据库也没坏。当前没有显示缓存，是因为这一路 custom provider 没给 Hermes 返回可识别的缓存明细，或者当前会话前缀没有命中。

Then recommend testing an alternate provider/wire mode only if the user wants proof:
- Try the same long stable prompt through another configured custom provider.
- Compare `chat_completions` vs `codex_responses` when both are supported.
- Inspect the raw `usage` object for `prompt_tokens_details.cached_tokens` or `cachedInputTokens`.
