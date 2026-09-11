# Tool Search Research — Session Findings

## Context

On 2026-06-23, user asked "什么模型？" (a 3-word question) and the turn consumed **53K tokens**. Investigation revealed:

- The system prompt carries ~50K tokens fixed overhead on every turn
- MCP tools (Binance × 20+, TradingView × 60+, FinanceKit, Jin10, Stock API, Hermes Studio, context7) are the heaviest component
- Skills index (193 skills × name+description) is the second-largest

## Root Cause: auto Mode + 1M-Context Model

The user's config had:

```yaml
tools:
  tool_search:
    enabled: auto
    threshold_pct: 10
```

deepseek-v4-flash has a **1,048,576 token** context window. 10% of 1M = ~105K threshold. The user's MCP tool schemas total ~30-36K — well under the trigger point. **Tool Search never activated.**

### Key Community Discussion

**GitHub Issue #4379** — "73% of each API call is fixed overhead (~13.9K tokens)":
- Measured a 31-core-tool Hermes deployment
- 8,759 tokens (46%) from tool definitions alone
- 5,176 tokens (27%) from system prompt + skills catalog
- 3K-8K tokens from conversation context
- This was BEFORE MCP tools — adding MCP servers triples the tool definition overhead

Issue discussion confirmed:
- Tool Search is the "easy win" (lbatalha, alexferrari88)
- `platform_toolsets` config exists but underused
- Compression threshold 0.5 is already aggressive

**GitHub Issue #13332** — "Hybrid Tool Pre-Selection":
- Alternative approach: RAG-style pre-selection without extra LLM round trips
- Measures ~14K tokens on default hermes-cli with 30+ tools
- Proposes semantic + keyword hybrid search
- Not yet implemented — Tool Search is the preferred shipped solution

### Community Resources Used

1. **Hermes docs** — https://hermes-agent.nousresearch.com/docs/user-guide/features/tool-search
2. **MarkTechPost article** — https://www.marktechpost.com/2026/05/29/hermes-agent-ships-tool-search-for-mcp/
3. **GitHub Issue #4379** — Token overhead breakdown
4. **GitHub Issue #13332** — Hybrid pre-selection proposal
5. **deepseek-v4 specs** — 1M context (HuggingFace), 284B MoE, 13B activated

## The Fix: enabled: on

```yaml
tools:
  tool_search:
    enabled: on              # force on regardless of context window
```

Effect on the user's system: ~53K/turn → ~17-20K/turn (saves ~33K per turn).

### Why not just lower threshold?

| Threshold | 1M Context Trigger | 128K Context Trigger |
|-----------|-------------------|---------------------|
| 10% | 100K — tools (30K) don't trigger | 12.8K — tools trigger |
| 3% | 30K — tools barely trigger | 3.8K — tools trigger |
| 1% | 10K — tools trigger | 1.3K — tools trigger |

Lowering to 3% would work for 1M models but is fragile — if tool count grows, still works; if model context grows, breaks again. `enabled: on` is the reliable fix.

## Other Findings

### Skills Index Overhead

- 193 skills × ~20-25 chars average = ~4.5K tokens
- Each skill entry: name + truncated description (~60 chars max)
- If every description is full length: 193 × 65 chars ≈ 12.5K chars ≈ ~5K tokens
- Mitigation: `/curator prune` stale skills, delete narrow one-off entries

### Context Compression Settings (for reference)

Current user settings:
```yaml
compression:
  enabled: true
  threshold: 0.5     # trigger at 50% context
  target_ratio: 0.2  # keep 20% after compress
  protect_last_n: 20 # keep last 20 messages
```

For tighter budgets: threshold 0.3, target_ratio 0.15, protect_last_n 10.

### Memory Overhead

Current user: memory ~1,533 chars + user profile ~152 chars = ~1,685 chars ≈ ~700 tokens. Already reasonable — not worth tuning further.

## Verification

After applying `enabled: on`, a single-turn query on deepseek-v4-flash should show:
- **System prompt size:** ~17-20K (was ~50K)
- **Tool definitions:** 3 bridge tools + ~31 core tools (was 31 core + ~80 MCP)
- **No functional loss** — tool_search finds any MCP tool within 1-2 calls
