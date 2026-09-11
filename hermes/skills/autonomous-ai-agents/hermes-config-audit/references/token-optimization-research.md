# Token Optimization Research — Community Findings

> Discovered 2026-06-22 during system health review + token bloat investigation.
> Source: Hermes Agent official docs + community discussions.

## Key Discovery: "Tool Descriptions Are Not Fixed"

The agent's initial assumption that tool schemas and skills list are "unchangedable fixed costs" was **wrong**. Multiple configurable levers exist.

## Configurable Levers (in order of impact)

### 1. Skills Pruning (highest impact on static overhead)

Source: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills

```bash
# Remove ALL bundled skills (safe — agent-created ones survive)
hermes skills opt-out --remove
hermes skills opt-in --sync  # undo

# Remove specific skills
hermes skills remove <name>
```

The skills list at Level 0 (names + descriptions) is ~3,000 chars injected every turn. Skills with `fallback_for_toolsets` or `requires_toolsets` in their frontmatter conditionally hide based on tool availability — not all 65+ listed skills are actually active.

### 2. Compression Threshold Tuning

Source: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/context-compression-and-caching.md

Default: threshold=0.50 (trigger at 50% context), target_ratio=0.20 (keep 20% as tail)

Tighter: `hermes config set compression.threshold 0.35` and `hermes config set compression.target_ratio 0.15`

### 3. Manual /compress Command

Built-in slash command. Type `/compress` mid-session when responses slow down.

### 4. AGENTS.md / SOUL.md Awareness

Both files are auto-injected. AGENTS.md at project root, SOUL.md at `$HERMES_HOME/`. Docs explicitly warn: "Every character counts against your token budget since they're injected into every message."

### 5. Memory / Profile Pruning

Memory max ~2,200 chars. User profile max ~1,375 chars. Both grow by accumulation. Common bloat: duplicate entries, dated session outcomes, verbose rules already in template files.

Holo fact_store: separate injection. Prune duplicates, dated analysis logs, overly verbose entries.

## What Is Truly Fixed

- **Tool JSON schemas** (~8,000 chars) — MCP parameter definitions, intrinsic to function calling
- **Core system prompt** (~2,000 chars) — agent instructions
- **Skills metadata Level 0** (~3,000 chars) — names + descriptions only (full content is lazy-loaded)

## Testing Methodology

To verify which lever had an effect:
1. Measure `len(system_prompt)` before/after via hermes config or token counting
2. Test `/compress` effectiveness by comparing response latency before/after
3. Confirm skills pruning by checking `ls "$HERMES_HOME/skills/" | wc -l` before/after

## Related

- Dual compression system: Gateway Session Hygiene (85% threshold, pre-agent) + Agent ContextCompressor (50% threshold, in-loop)
- For gpt-5.5 on Codex OAuth: `codex_gpt55_autoraise: true` raises trigger to 85%
- `protect_last_n: 20` ensures recent messages are never compressed away
