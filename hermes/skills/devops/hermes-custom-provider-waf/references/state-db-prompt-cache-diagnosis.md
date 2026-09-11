# State DB Prompt Cache Diagnosis for Custom Providers

When a custom provider shows **zero cache reads** and Hermes logs warnings like:
```
WARNING: Stored system prompt for session X is null; rebuilding from scratch this turn.
Prefix cache will miss until the rebuild persists.
```

Use the state.db to confirm the root cause.

## Diagnosis Script

Run in `execute_code` or Python terminal:

```python
import sqlite3

db = 'C:/Users/Administrator/AppData/Local/hermes/state.db'
conn = sqlite3.connect(db)

# 1. Count null system_prompt by provider
cur = conn.execute('''
  SELECT billing_provider, COUNT(*) as null_count
  FROM sessions WHERE system_prompt IS NULL
  GROUP BY billing_provider ORDER BY null_count DESC
''')
print("=== Sessions with NULL system_prompt ===")
for r in cur.fetchall():
    print(f"  provider={r[0]} null_count={r[1]}")

# 2. Cache health by provider (non-null SP sessions only)
cur = conn.execute('''
  SELECT billing_provider, COUNT(*) as total,
    SUM(CASE WHEN COALESCE(cache_read_tokens,0) > 0 THEN 1 ELSE 0 END) as cache_read_ok,
    SUM(CASE WHEN COALESCE(cache_write_tokens,0) > 0 THEN 1 ELSE 0 END) as cache_write_ok,
    ROUND(100.0 * SUM(CASE WHEN COALESCE(cache_read_tokens,0) > 0 THEN 1 ELSE 0 END) / MAX(COUNT(*),1), 1) as hit_pct
  FROM sessions WHERE system_prompt IS NOT NULL
  GROUP BY billing_provider ORDER BY total DESC
''')
print("\n=== Cache stats by provider ===")
for r in cur.fetchall():
    print(f"  {r[0]:<20} sessions={r[1]:<5} cache_read_ok={r[2]:<5} ({r[4]}%) cache_write_ok={r[3]}")

# 3. Most recent sessions with null system_prompt
cur = conn.execute('''
  SELECT id, model, billing_provider, 
    COALESCE(cache_read_tokens,0) as cr, 
    COALESCE(cache_write_tokens,0) as cw
  FROM sessions WHERE system_prompt IS NULL
  ORDER BY rowid DESC LIMIT 10
''')
print("\n=== Recent null-system_prompt sessions ===")
for r in cur.fetchall():
    print(f"  {str(r[0])[:16]:<18} model={r[1]:<16} provider={r[2]:<16} cr_tok={r[3]:<10} cw_tok={r[4]}")

conn.close()
```

## Expected Healthy Baseline

From production data (1067 sessions, Jul 2026):

| Provider | Sessions | Cache Hit % | Null SP Count |
|---|---|---|---|
| deepseek | 713 | 99.7% | 2 |
| opencode-go | 105 | 100% | 0 |
| openrouter | 23 | 70% | 0 |
| **custom** (lingsuan, aijws, etc.) | **106** | **81%** | **9** |

`custom` provider consistently underperforms on cache due to:
- Missing `/v1` in `base_url` (model metadata probe fails → context_length unknown)
- Missing `models:` section with explicit `context_length`
- `codex_responses` api_mode has weaker cache metadata passthrough

## Quick Fix

If `custom` provider shows high null system_prompt count:

```yaml
- name: lingsuan.top
  base_url: https://lingsuan.top/v1    # ← fix path
  api_key: sk-...
  model: gpt-5.5
  api_mode: codex_responses
  models:
    gpt-5.5:
      context_length: 400000           # ← add explicit
```

After fix: restart gateway (`hermes gateway restart`). New sessions will probe properly and cache reads will work.

## Concrete Before/After — lingsuan.top (Jul 2026)

| Config Aspect | Before (broken cache) | After (fixed) |
|---|---|---|
| `base_url` | `https://lingsuan.top` ❌ | `https://lingsuan.top/v1` ✅ |
| `models.gpt-5.5.context_length` | missing → probe-down → 256K default | `400000` ✅ |
| state.db `system_prompt` | NULL (every custom session) | non-null (after fix) |
| Prefix cache | miss every turn | hits normally |
| Context length log | `Could not detect context length — defaulting to 256,000 tokens (probe-down)` | gone |

**Why the `/v1` matters**: `https://lingsuan.top/models` returns the web login page HTML. `https://lingsuan.top/v1/models` returns proper API JSON (with auth). Hermes's metadata probe hits `/models` relative to base_url — without `/v1`, it gets HTML, can't parse the model list, and falls back to default 256K context. This cascade causes the system_prompt write path to fail on session init.

**Additional fix — API key truncation**: If you edit the config and the key gets truncated to `sk-1f3...05fe` (the terminal display redaction), the provider returns HTTP 401. Full key recovery pattern documented in SKILL.md §6d.

## State DB Schema Notes

The `sessions` table in `state.db` has these cache-relevant columns:
- `system_prompt` (TEXT) — the persisted system prompt; if NULL, prefix cache misses
- `cache_read_tokens` (INTEGER) — cumulative prompt cache reads
- `cache_write_tokens` (INTEGER) — cumulative prompt cache writes
- `billing_provider` (TEXT) — identifies which provider was used (e.g. `custom`, `deepseek`, `opencode-go`)
