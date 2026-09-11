---
name: hermes-token-optimization
description: "Reduce Hermes Agent token overhead — Tool Search, skills pruning, context compression tuning, and other strategies to cut per-turn costs. Covers the '73% fixed overhead' problem and practical fixes."
version: 1.0.0
author: Agent-created
tags: [hermes, tokens, cost, optimization, mcp, tool-search, context]
---

# Hermes Token Optimization

Hermes Agent's system prompt carries significant fixed overhead per turn — typically **50%–73%** of each API call before any real work. This skill documents the available mechanisms to reduce that overhead without losing capability.

## Token Cost Anatomy (From Real Session Analysis)

GitHub Issue #4379 analyzed a 31-core-tool Hermes deployment. With MCP servers added, the picture changes dramatically:

| Component | Core Only | 6+ MCP Servers Added | % of 53K Turn |
|-----------|-----------|---------------------|---------------|
| Tool definitions (core ~31 tools) | ~8,759 | ~8,759 | ~16% |
| MCP tool definitions (TV, Binance, etc.) | 0 | ~30-36K | ~60% |
| Skills index (193+ skills) | ~4.5K | ~4.5K | ~9% |
| System prompt (SOUL + instructions) | ~3.5K | ~3.5K | ~7% |
| Memory/profile | ~1.5K | ~1.5K | ~3% |
| Conversation (1 turn) | — | ~5 | <0.1% |
| **Fixed overhead per turn** | **~13,935** | **~48-55K** | ~95% |

A simple 3-word question ("什么模型？") consumed 53K tokens — 95% was fixed overhead.

## Quick Wins (in priority order)

### 1. Tool Search (Biggest Impact — up to ~85% reduction in tool definition tokens)

Replaces all MCP and non-core plugin tool schemas with **3 bridge tools**, cutting tool-definition tokens by ~85%.

**Bridge tools the model sees instead of full MCP schemas:**
- `tool_search(query, limit?)` — find matching tools
- `tool_describe(name)` — get full schema for a specific tool
- `tool_call(name, arguments)` — invoke the real tool

**Cost:** ~300 extra tokens + 1 round trip per cold tool. **Benefit:** 15K–60K tokens saved per turn on typical multi-MCP setups.

**Accuracy impact** (Anthropic MCP evals):
| Model | Without | With | Gain |
|-------|---------|------|------|
| Claude Opus 4 | 49% | 74% | +25pp |
| Claude Opus 4.5 | 79.5% | 88.1% | +8.6pp |

Core Hermes tools (`terminal`, `read_file`, `web_search`, etc.) are **never deferred**.

#### Critical: Understanding the `auto` Mode Threshold

The `auto` mode checks: do deferrable tool schemas exceed **threshold_pct% of the model's total context window**?

```yaml
tools:
  tool_search:
    enabled: auto    # activates when tools > 10% of context window
    threshold_pct: 10
```

This is **not** about the current prompt size — it's about the theoretical maximum context. This makes `auto` mode unreliable on very-large-context models:

| Model | Context Window | 10% Threshold | ~30K Tools Trigger? |
|-------|---------------|---------------|---------------------|
| deepseek-v4-flash | 1,048,576 | ~105K | ❌ |
| gemini-3-pro | 1M+ | ~100K | ❌ |
| claude-opus-4 | 200K | ~20K | ✅ |
| claude-sonnet-4-6 | 200K | ~20K | ✅ |
| gpt-5.5 | 128K | ~12.8K | ✅ |

**Wrong assumption in earlier versions of this skill:** "15+ MCP tools → typically activates" is FALSE for any model with a 1M+ context window. 15+ tools generate ~30K schemas, but 10% of 1M = 100K — well above the trigger point.

#### Solution: Use `enabled: on` for Large-Context Models

When you have many MCP tools (15+) AND a large-context model (1M+), force Tool Search on:

```yaml
tools:
  tool_search:
    enabled: on              # was: auto
    threshold_pct: 10        # irrelevant when 'on', kept for clarity
    search_default_limit: 5
    max_search_limit: 20
```

**Effect on a 53K/turn system:** drops to ~17-20K fixed overhead (saves ~33K per turn).

```yaml
# Minimal form:
tools:
  tool_search: true
```
(This sets `enabled: auto` — NOT sufficient for 1M-context models. Use the full form above.)

**Trade-off:** 1-2 extra model calls on the first `tool_search → tool_describe → tool_call` sequence per turn, but subsequent re-use of the same tool within the turn has zero overhead (schema already loaded).

#### ⚠️ `hermes config set` 不能设置 `enabled: on`

`hermes config set tools.tool_search.enabled on` 会把值写入为 YAML 布尔 `true`，而非字符串 `on`。
由于 `enabled: true` 在 Hermes 内部映射为 `auto` 模式（而非 `on` 强制模式），
对 1M 上下文模型不会触发 Tool Search。

**必须直接用 Python/正则修改 config.yaml 文件：**
```python
import re
path = 'C:/Users/Administrator/AppData/Local/hermes/config.yaml'
with open(path, 'r') as f:
    content = f.read()
content = re.sub(
    r'(tool_search:\n\s+enabled:) true',
    r'\1 on',
    content
)
with open(path, 'w') as f:
    f.write(content)
```

或配合降低 `threshold_pct` 做双重保障：
```yaml
tools:
  tool_search:
    enabled: on              # 强制启用（不是 auto）
    threshold_pct: 3         # 3% × 1M ctx = 30K < ~36K MCP 工具
```

#### Alternative: Lower Threshold

```yaml
tools:
  tool_search:
    enabled: auto
    threshold_pct: 3         # was 10
```

For 1M context: 3% = 30K, matching ~30K tool schemas → activates.
For 128K context: 3% = 3.8K → activates easily.

**Pros:** Conditional, zero overhead on small tool sets. **Cons:** May flicker on/off, harder to reason about.

### 2. Skills Pruning

Every installed skill's name + description (~60 chars/description) adds to the system prompt. 200+ skills contribute ~15KB before trimming.

**Strategy:** Prune skills that are irrelevant to your daily workflow. Keep class-level skills; delete narrow one-off skills.

**Commands:**
```bash
hermes skills list          # See all installed skills
hermes skills uninstall N   # Remove a hub skill
# Or delete from ~/.hermes/skills/<category>/<name>/
```

### 3. Memory Compression

Keep `memory` notes concise. Avoid task-progress logging, PR numbers, commit SHAs, or anything stale within 7 days. Use `session_search` for recalling past session details instead.

### 4. Context Compression Tuning

In `config.yaml`:
```yaml
compression:
  threshold: 0.50    # Fire compression at 50% context (default)
  target_ratio: 0.20 # Keep 20% of conversation after compression
```

- Higher `threshold` (e.g. 0.75) → less frequent compression, larger per-turn cost
- Lower `target_ratio` → more aggressive compression saves tokens but loses detail

#### Codex App Server: prevent silent compression bypass

For `openai-codex` sessions, inspect `compression.codex_app_server_auto` before changing the global threshold. The `native` mode can skip Hermes preflight compression; if native Responses compaction is not actually enabled/available, the transcript grows until the provider hard limit and emits the misleading `compression.enabled: false` overflow warning even when the YAML global flag is `true`.

For a reliable Hermes-managed path, set the routing pair explicitly:
```bash
hermes config set compression.codex_app_server_auto hermes
hermes config set compression.codex_responses_native false
```

Then verify `compression.enabled: true` and the two route keys with `hermes config` or by reading the config. Restart the CLI/Desktop session: compression settings are snapshotted at startup, so changing YAML does not repair the already-running agent. On the already-overflowing session, run `/compact`; if it cannot respond, start `/new` after restart.

Do not merely hide or deduplicate the warning. Verify the effective route in `agent.log`: a healthy Hermes path should no longer repeatedly log a request growing beyond the model context while `codex_app_server_auto=native` is active. See `references/codex-app-server-compression.md` for the reproduction and evidence checklist.

## Prompt Cache / Provider Cache Diagnostics

Use this when the user reports low cache hit rate, unexpected token burn, or a provider-specific cache regression.

### 5. Distinguish real cache misses from missing provider usage fields

Do not assume a low Hermes-reported cache hit rate means the system prompt changed. First verify whether the provider is returning cache accounting fields at all.

**Hermes log behavior:**
- Chat Completions path logs `cache=x/y (%)` only when normalized `cache_read_tokens > 0`.
- Codex Responses path maps cache reads from `usage.cachedInputTokens`.
- OpenAI-style chat paths typically map cache reads from `usage.prompt_tokens_details.cached_tokens`.
- If the provider omits those fields, Hermes records 0 cached tokens even when upstream may be caching internally.

**Fast diagnosis pipeline:**
1. Parse `~/.hermes/logs/agent.log*` for `API call #`, `provider=`, `base_url=`, `model=`, `cache=`.
2. Bucket by hour and base URL; look for a step-change from high hit rate to all-zero hits.
3. Compare request mode:
   - `codex_stream_request` / `request_complete` → Responses API; expect `cachedInputTokens`.
   - `chat_completion_stream_request` / `stream_request_complete` → Chat Completions; expect `prompt_tokens_details.cached_tokens`.
4. Check for simultaneous provider errors (`server_error`, `upstream_error`, `context window exceeded`) before blaming Hermes prompt churn.
5. Only after usage-field verification, inspect dynamic prompt causes: MCP tool refresh, tool schema changes, skills/memory changes, compression, model switching, or changed base URL.

**Interpretation rule:**
- If the same Hermes config/base URL had 80%–99% hits earlier and then suddenly every call is 0%, treat it as a provider/upstream usage-field regression first.
- If only the first call in each new session is low but later calls return high cache, this is normal warmup/TTL/session behavior.
- If all calls through `/v1` chat are 0 while Responses calls report cache, the gateway likely does not expose `prompt_tokens_details.cached_tokens` on chat completions.

**Provider escalation wording:** ask the provider to verify whether their endpoint passes through:
- Responses API: `usage.cachedInputTokens`
- Chat Completions: `usage.prompt_tokens_details.cached_tokens`

### Example log parser

See `references/provider-cache-diagnostics.md` for a compact script and interpretation checklist.

## Reference
## Prompt Cache / Provider Cache Diagnostics

Use this when the user reports low cache hit rate, unexpected token burn, or a provider-specific cache regression.

### 5. Distinguish real cache misses from missing provider usage fields

Do not assume a low Hermes-reported cache hit rate means the system prompt changed. First verify whether the provider is returning cache accounting fields at all.

**Hermes log behavior:**
- Chat Completions path logs `cache=x/y (%)` only when normalized `cache_read_tokens > 0`.
- Codex Responses path maps cache reads from `usage.cachedInputTokens`.
- OpenAI-style chat paths typically map cache reads from `usage.prompt_tokens_details.cached_tokens`.
- If the provider omits those fields, Hermes records 0 cached tokens even when upstream may be caching internally.

**Fast diagnosis pipeline:**
1. Parse `~/.hermes/logs/agent.log*` for `API call #`, `provider=`, `base_url=`, `model=`, `cache=`.
2. Bucket by hour and base URL; look for a step-change from high hit rate to all-zero hits.
3. Compare request mode:
   - `codex_stream_request` / `request_complete` → Responses API; expect `cachedInputTokens`.
   - `chat_completion_stream_request` / `stream_request_complete` → Chat Completions; expect `prompt_tokens_details.cached_tokens`.
4. Check for simultaneous provider errors (`server_error`, `upstream_error`, `context window exceeded`) before blaming Hermes prompt churn.
5. Only after usage-field verification, inspect dynamic prompt causes: MCP tool refresh, tool schema changes, skills/memory changes, compression, model switching, or changed base URL.

**Interpretation rule:**
- If the same Hermes config/base URL had 80%–99% hits earlier and then suddenly every call is 0%, treat it as a provider/upstream usage-field regression first.
- If only the first call in each new session is low but later calls return high cache, this is normal warmup/TTL/session behavior.
- If all calls through `/v1` chat are 0 while Responses calls report cache, the gateway likely does not expose `prompt_tokens_details.cached_tokens` on chat completions.

**Provider escalation wording:** ask the provider to verify whether their endpoint passes through:
- Responses API: `usage.cachedInputTokens`
- Chat Completions: `usage.prompt_tokens_details.cached_tokens`

### Example log parser

See `references/provider-cache-diagnostics.md` for a compact script and interpretation checklist.

## Reference

See `references/tool-search-research.md` for the detailed research findings, BM25 retrieval details, and configuration reference.
See `references/provider-cache-diagnostics.md` for provider cache-hit log parsing and missing-usage-field diagnostics.
See `references/provider-cache-state-db.md` for the state.db confirmation workflow that separates “current session has 0 cache” from “Hermes cache accounting is broken”.

## When to Apply

- **New Hermes user with 3+ MCP servers** → enable Tool Search immediately
- **Seeing 40K+ tokens per turn** → check Tool Search + skills count
- **User reports '73% overhead' or '53K for a simple query'** → first diagnosis step
- **User reports provider cache hit rate suddenly collapsed** → run Provider Cache Diagnostics before changing prompts/tools/memory

