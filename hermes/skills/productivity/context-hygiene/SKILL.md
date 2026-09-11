---
name: context-hygiene
description: >-
  Periodically prune and compress Hermes persistent context (memory, user_profile,
  fact_store) to control static token overhead. Also diagnose root cause of high
  token usage — skills list vs memory vs MCP overhead. Use when user complains
  about token usage, context feels sluggish, or session has accumulated many
  tool calls without pruning.
triggers:
  - token too big / 太多token / context太重
  - memory too long / 记忆太多了
  - prune memory / 精简记忆
  - fact store cleanup
  - user profile too full
tools_required:
  - memory
  - fact_store
---

# Context Hygiene — Pruning Persistent Memory

## Signs to Prune

- User says "token太多" / "一次太多" — immediate signal
- User Profile > 70% capacity (~1,000/1,375 chars)
- Memory > 50% capacity (~1,100/2,200 chars)
- fact_store > 8 entries
- System prompt feels heavy (static overhead eating into reasoning budget)

## fact_store Cleanup Rules

**KEEP** (durable facts that save future effort):
- Data source preferences (OANDA/Binance/krill API chains)
- Trading periods and execution conventions
- Core system architecture rules (engine expectations, config keys)
- Proxy/routing configurations (micu NO_PROXY, x.ai proxy)
- Ops procedures (monitor restart, lock file handling)
- Tool usage patterns (patch vs sed, git-bash quirks)

**REMOVE** (task-progress / session outcomes — per memory rule):
- Dated analysis snapshots ("2026-06-18 BTC analysis: ...")
- Session logs ("P0 audit completed", "F轮变更执行")
- Lock snapshots with specific commit SHAs
- Anything referencing a specific date without durable value

**REMOVE** (duplicates):
- Same info written to multiple facts with minor reformatting
- Earlier version when a later one supersedes it

## memory Cleanup Rules

**Consolidate** overlapping entries into one compact entry:
- Cron + alert routing + stop-loss rules → single "Cron & routing" entry
- TG chat IDs + routing rules → single entry

**Trim verbosity**: keep < 200 chars per fact when possible. Use · separators instead of periods.

## user_profile Cleanup Rules

**Remove** redundant entries that repeat info already in the first/foundational entry:
- "搜源顺序" separate entry → already in foundational entry
- "监控优先no_agent" separate entry → already in foundational entry
- "账户规则" separate entry → already in foundational entry
- "回复格式" separate entry → already in foundational entry

**Target**: keep user profile at 40-60% capacity for headroom.

## Memory Operations Array (Batch Technique)

The most efficient way to compress memory: use the `operations` array to batch all removes, replaces, and adds in a single call.

```python
memory(
    target="user",  # or "memory"
    operations=[
        # Remove redundant/overlapping entries (use short unique substring)
        {"action": "remove", "old_text": "short unique identifier"},
        # Replace verbose entries with compact versions
        {"action": "replace", "old_text": "old text exact...", "content": "compact · version · here"},
        # Add new consolidated entries
        {"action": "add", "content": "Consolidated rule here."}
    ]
)
```

### Batch Strategy (proven pattern)

1. **Identify overlapping entries** — e.g. 4 entries about screenshots, 3 about time format, 2 about direct recommendations
2. **Remove all redundants** — use short unique substrings as `old_text`, avoid quotes/smart quotes
3. **Replace verbose survivors** — shorten to ≤100 chars using · separators
4. **Add consolidated groups** — 1-2 umbrella entries covering 5-10 removed ones

### Real session result (2026-06-30)
- Before: 19 entries / 98% (1,369/1,375 chars)
- After: 9 entries / 51% (707/1,375 chars)
- Operations: 12 removes + 4 replaces + 2 adds = 18 ops in one call

### Pitfalls

- **Quote mismatch**: `old_text` with smart quotes ("/") won't match input-box typed quotes ("/"). Use short unique substrings that avoid quotes entirely, or surround with single quotes.
- **Don't over-batch**: 18 is fine. The API is synchronous and atomic — if any op fails, all roll back.
- **No need to chunk**: 18 ops in one batch is faster and cleaner than 3 sequential calls of 6.

## Batch Command (Legacy Single-Call Approach)

```python
# Full prune script (cut/adapt from here)
from hermes_tools import memory, fact_store

# 1. List fact_store, identify stale entries
facts = fact_store(action="list")

# 2. Remove session-progress facts (date-stamped analysis, commit logs)
for fid in [3, 6, 7, 9]:  # adjust IDs
    fact_store(action="remove", fact_id=fid)

# 3. Trim verbose facts
fact_store(action="update", fact_id=4,
    content="compact version of the same info")

# 4. Remove redundant user_profile entries
memory(action="remove", target="user",
    old_text="unique substring identifying the redundant entry")

# 5. Consolidate memory entries
memory(action="add", target="memory",
    content="Cron 4个(清理12:00/日间8:30/信号5m/学习8:30)。路由BTC→386/XAU→385/山寨→416。止损ATR×2+0.5ATR缓冲。连亏≥3缩半仓·≥5暂停。格式：每行≤38字·display_name优先·patch改大文件。")
```

## Pitfalls

- **Don't remove everything useful**: fact_store entries about data source chains and proxy configurations save real time. They're durable knowledge, not session progress.
- **Don't overwrite user_profile you can't match**: `memory(action="replace")` requires exact `old_text`. Use `remove` + `add` instead when text match fails.
- **Don't prune during active work**: prune between sessions or at natural breaks, not mid-debugging.
- **User profile entries are hard to edit**: once written, you can only remove by matching old_text or add new (up to 1,375 char total). Compact foundational entry is the most valuable — put everything essential there.

## Token Consumption: The Full Breakdown

Persistent storage (memory + user_profile + fact_store) is only **~8%** of per-turn input tokens. The real pie:

```
来源               占比    估算
skills list (282)   ~55%  ~28K chars (7K-10K tokens)
System prompt        ~25%  Hermes base instructions
对话历史              ~12%  Current turn's state
memory+user+facts    ~8%   What pruning controls
```

**Key takeaway**: Trimming memory from 98% to 37% saves ~1,300 chars (~350 tokens) — about 2-3% of total. It's worth doing, but don't promise the user it'll solve "token太多" by itself. The real lever is the skills list.

#### Raw Files vs Runtime-Enabled Skills

Do not report recursive `SKILL.md` count as the number of active skills. Raw files may include root-level duplicates, publisher-prefixed copies, builtins, hub entries, or disabled skills.

Use two measurements for different questions:

```bash
# Disk/library inventory only
find "$HERMES_HOME/skills" -name SKILL.md | wc -l

# Runtime truth: enabled vs disabled
hermes skills list
```

The summary line from `hermes skills list` is authoritative for enabled/disabled counts. Report raw file count only as “SKILL.md files on disk.” This avoids claiming that every installed copy contributes to the active prompt.

#### Root-Level Skill Duplicates (New Finding 2026-06)
Skills created without `category` land in the root skills dir. After moving to a category dir, the root copy persists. Detection:
```bash
cd ~/AppData/Local/hermes/skills/
for d in */; do [ -f "${d}SKILL.md" ] && echo "ROOT DUPE: $d"; done
```

### Directory Name Mismatch (Bulk Delete Pitfall)
`skills_list()` returns **clean names** but directories have **publisher prefixes**:
```
skills_list "canvas-design"   → dir "anthropic-canvas-design"
skills_list "ab-test-analysis" → dir "pm-ab-test-analysis"
skills_list "handoff"         → dir "matt-handoff"
skills_list "executing-plans" → dir "superpowers-executing-plans"
```
Always verify actual dir names before bulk delete.

## Memory Authority and External Studio Verification

Treat memory as layered state, not one undifferentiated truth source:

- Current `MEMORY.md` and `USER.md`, plus the latest explicit user correction, are the active preference layer.
- `memory_store.db` facts are a historical fact layer. Before using them as workflow rules, check timestamps and conflicts against the active files and current code. Retire or flag stale formatting, model, routing, and execution claims rather than silently merging them.
- Session-specific analysis, prices, expired key levels, and audit outcomes do not belong in durable memory.
- When asked to inspect Studio memory, verify the Studio read path and record the returned evidence. An unavailable/failing API or empty operation catalog is not evidence that Studio has no memory; report it as unverified and do not invent contents.
- Separate “local built-in memory read”, “Studio memory read”, and “repository evidence” in reports. They answer different questions.

A useful review record is: source · timestamp/version · claim · conflict check · authority · action.

## Skills List: The #1 Token Drain

Each installed skill injects its `name + description + category` into the system prompt. With 282 skills at ~100 chars avg entry, that's ~28K chars (~7-10K tokens) every single turn:

```bash
hermes skills list | wc -c  # rough estimate
```

**Real levers** (not memory trimming):

1. **skills opt-out** — Remove unused skills (platform-specific, Chinese-platform, service-dependent)
2. **Compression settings** — Aggressive context compression
3. **/compress** — Manual mid-session compression

## Systematic Token Bloat Diagnosis

When user says "token太多" or "一次太多", run this checklist:

### 1. REAL CAUSE FIRST: Skills list overhead
```bash
hermes skills list | wc -c
```
If this is >20K chars, it's the dominant cause. Don't blame memory — show the real number.

### 2. Check static overhead (memory + user_profile + fact_store)
Target: Memory < 50%, User Profile < 60%, Fact Store < 8 entries.

### 3. Check AGENTS.md / SOUL.md auto-injection
```bash
cat "$HERMES_HOME/SOUL.md" | wc -c
```
These are injected EVERY turn.

### 4. Check compression settings
```bash
grep -E "compression|threshold|target_ratio" "$HERMES_HOME/config.yaml"
```
Defaults: threshold=0.5, target_ratio=0.2. Consider lowering to 0.35/0.15.

### 5. Use /compress mid-session
If the user says "速度慢了", tell them to type `/compress`.

### 6. Prune unused skills
```bash
hermes skills opt-out --remove
```

### 7. Check MCP server bloat
```bash
grep -A 3 "mcp_servers:" "$HERMES_HOME/config.yaml"
```

### 8. fact_store: What NOT to Save
Must NOT contain:
- Dated analysis snapshots
- Session logs or progress markers
- Lock snapshots with commit SHAs
- Task-progress or session outcomes

## fact_store Cleanup: Real Session Patterns

### Duplicate Facts (most common)
Multiple entries containing the same rule reformatted differently:
- Same format rule written as "v4.2 lock" vs "交易铁律" with different verbosity → keep the shortest
- User profile consolidation leaves orphaned fact_store entries → must clean up manually

### Placeholder/Test Artifacts
`memory()` and `fact_store()` calls generate permanent entries:
- `"placeholder to check memory system state"` — accumulates silently
- `"batch remove stale facts"` — self-referential garbage

### Version-Numbered Stale Facts
Anything with a specific version tag (v6.9.15, v6.8.2) is stale within days. Remove when upgrading.

### Batch Removal Strategy
```python
stale_ids = [36, 37, 42, 43, 44]  # placeholders + stale dupes
for fid in stale_ids:
    fact_store(action="remove", fact_id=fid)
```
Note: No batch API — each is a separate tool call.

## user_profile Cleanup: Smart-Quotes Trap

user_profile entries use **smart quotes** (""/"") when written by LLMs. The `remove` API requires exact `old_text` match:

```
# WON'T match — smart vs regular quote difference
memory(action="remove", target="user", old_text="用户说"错了"")

# Use short unique substrings avoiding quotes
memory(action="remove", target="user", old_text="用户说错了")
```

**Prevention**: Use `operations` array with `remove` using short substrings that avoid quotes. Never use `replace` on user_profile — it will fail on quote mismatch. Use `remove + add` instead.

## Pitfalls (Updated)

- **Skills list is 55% of overhead, not 8%**: Don't tell the user "memory is why tokens are high" — run the skills list size check first.
- **fact_store accumulates silently**: Every `memory()` and `fact_store()` call creates durable entries. Even test placeholders. They must be manually removed.
- **User profile is nearly uneditable**: Once written, you can only remove by matching smart-quoted text or add new up to 1,375 chars. Only write what MUST persist across sessions.
- **Don't write analysis to fact_store**: Daily analysis, price levels, trade ideas = session context. Write to fact_store only for infrastructure/procedure/configuration facts.
- **/compress only affects conversation history**: It doesn't touch persistent storage. Those must be pruned separately.
- **Communication when pruning**: Always tell the user "合并压缩，不是删除" (merged, not deleted). Report before/after sizes and entry counts. If user asks to restore, read back the consolidated entries to verify completeness. Never just say "done" — show what changed.
