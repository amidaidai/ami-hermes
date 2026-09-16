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

### 失败回滚时从这里重建（关键）

`operations` 是**全有或全无**：任一 op 失败整批回滚，而且**错误响应里带回 `current_entries`**
——那是权威的**实时**列表。所以：

- **不要用上下文/摘要里的记忆快照构造这一批**。它可能已被别的会话改写，你对“现在有哪些条目”的认知
  很可能是旧的。发现实际内容与你以为的不符时，以 `current_entries` 为准重建。
- 报错形如 `no entry matched '<片段>'` = 该条已被改写或已删：去 `current_entries` 里取**现文本**
  再写 `old_text`，不要凭记忆重复试。
- **单字符/极短 `old_text` 不要用**：匹配是子串匹配，`.`、`—`、`：` 这类片段几乎每条都命中，
  会误删别的条目。记忆里残留的单字符垃圾条目**放弃清理**——收益 4 字符，代价是可能删掉身份/仓库条目。

### 用 `replace` 重塑，不要 `remove + add`

合并同类条目时，`replace`（old_text 定位 + content 新全文）一条 op 顶两条，且不产生中间态。
同一批里 11 条 replace 比 26 removes + 11 adds 更快、更不容易误伤。
`remove + add` 只在真的能从记忆里删掉一类内容时用（退役的任务、一次性事实）。

### 结果度量（每轮都要报）

- 主信号 = **条目数**（去重成效），次信号 = 字符数。修前修后都要量，并在回复里给出两组数。
- **字符数反而上升 = 这一轮没压缩**（adds 比 removes 长）。实测第一轮 26 removes + 11 adds
  把 2,049 涨到 2,137；第二轮 11 replaces 才降到 1,862；第三轮 5 replaces 到 1,718（78%）。
  收尾判据：条目已合并到位后，再逐条收紧一次就停，不要无限刷。
- 参考量级：27 条 → 11 条 / 2,049 → 1,718 字符（93% → 78%）；另一轮 19 → 9 条 / 98% → 51%。

### 砍什么、留什么（逐条判据）

- **砍**：能在技能/文档里查到的（文档全路径、看门狗/脚本全名）、一次性事实（“依赖已补齐”）、过程叙述。
- **留**：用户偏好（指标聚合覆盖、只有明确授权才外发的通道、push 授权）、操作坑（代理与环境变量注入、
  工具匹配行为、取时区）、治理单点（唯一身份/精度实现），以及**任何会改变判断的阈值与契约**。
- **每条都按“这条会不会改变我下次的行为”过一遍**；答不上就砍。
- 收尾要披露：合并方式（哪几条并成哪条）、砍掉了什么、为什么留下某些、以及有没有未能清理的残留。

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
- `memory_store.db` 是**历史事实层**，而且它**不等于「built-in fact store」**：该库归 `holographic` 记忆插件所有（`plugins/memory/holographic/store.py` 里 `get_hermes_home() / "memory_store.db"`）。它是否进上下文完全取决于插件开关——`config.yaml` 的 `plugins.enabled` 不含 `holographic`、且 `memory.provider` 为空时，该库**一个字符都不会进系统提示**（此时它对 token 的贡献是 0，不是「一小部分」）。使用前先判定状态：① `grep -rl memory_store hermes-agent --include=*.py` 找到读取方；② `grep -n -A 20 "^plugins:" config.yaml` 看它是否 enabled；③ `grep -n "provider" config.yaml`（在 `memory:` 段下）确认当前记忆 provider。三者都指向插件未启用 → 明确写「休眠库·未注入」，不要把它和两个 .md 并列当成同等活跃的存储。
- 确认它休眠后，库里的内容仍然**只作历史层**：先比时间戳、再比现行代码。格式化条款、模型名、路由表、Cron 条数这类会随版本翻页的条目，一旦与现行 `MEMORY.md`/`USER.md` 或代码冲突，就标为「已冲突」而不是悄悄并入。
- Session-specific analysis, prices, expired key levels, and audit outcomes do not belong in durable memory.
- When asked to inspect Studio memory, verify the Studio read path and record the returned evidence. An unavailable/failing API or empty operation catalog is not evidence that Studio has no memory; report it as unverified and do not invent contents.
- Separate “local built-in memory read”, “Studio memory read”, and “repository evidence” in reports. They answer different questions.

A useful review record is: source · timestamp/version · claim · conflict check · authority · action.

## 读记忆请求（用户说「读取记忆」）＝ 三个存储全读

触发：用户说「读取记忆」「读取记忆，好好的读取」「看看记忆里有什么」。
**只读两个 `.md` 交差是错的**——那是「读了一半」，用户会当场叫你重读一遍。本机固定有三个存储：

| 存储 | 路径 | 进上下文？ | 怎么判 |
|:---|:---|:---|:---|
| 用户画像 | `memories/USER.md` | ✅ 每轮全文 | 文件存在即注入 |
| 个人笔记 | `memories/MEMORY.md` | ✅ 每轮全文 | 同上 |
| 历史事实库 | `memory_store.db`（SQLite） | ❌ 除非 `holographic` 插件启用 | 查 `plugins.enabled` + `memory.provider` |

### 执行步骤

1. `ls -la "$HERMES_HOME/memories/"` —— 两个 `.md` + 两个 **0 字节** `.lock`（0 字节 = 未锁定，写入通道正常）。
2. **逐条原样列出**两个 `.md` 的内容。用户要的是内容本身，不是你的摘要或表格改编。
3. 找第三存储：`find "$HERMES_HOME" -maxdepth 3 -iname "*memor*"` —— 会命中 `memory_store.db`（含 `-shm`/`-wal`）。
4. 跑 `scripts/memory_inventory.py` 一次性导出：条目/字符预算/mtime/sha256/注入判定/DB 时间线。
5. 报告必须包含三个部分：
   - **注入判定表**（哪个进上下文、哪个没进、判据是什么）；
   - **冲突对照**（历史层里哪些条目已被现行文件或代码推翻）；
   - **两个不同结论分开写**：「内容没丢」和「上次读全了」不是同一件事，只有全读才能回答后者。
6. 结尾给处置建议，但**不擅自执行破坏性写入**：导出归档 → 让用户点头 → 再删/合并。历史库清理由用户决定。

### 陷阱

- 字符预算按「去掉 `§` 分隔符后的正文」算，报告要**同时给条目数与字符数**。
- 条目数必须由代码数（`len([e for e in txt.split("§") if e.strip()])`），不要目测；报错条目数比不报更怱。
- 历史库里最容易过期的是**格式条款、模型名、路由表、Cron 条数、积分制版本号**——这五类逐条比一遍再下结论。
- 历史库里可能出现**空的/无意义的自动抽取条目**（单字符占位、临时探针语句）。发现时只标不删：单字符 `old_text` 匹配会误伤别的条目。

详见 `references/layered-memory-review.md` 与 `scripts/memory_inventory.py`。

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
