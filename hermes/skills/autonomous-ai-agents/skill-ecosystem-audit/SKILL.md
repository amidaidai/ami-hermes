---
name: skill-ecosystem-audit
description: >-
  Audit external skill marketplaces against the Hermes skill catalog to identify gaps,
  source candidates, and prioritize imports. Use when the user asks to compare skill
  ecosystems, discover what's missing, or evaluate external skill quality.
triggers:
  - "对比我们的系统，补充缺少的"
  - "看看别人有什么技能我们没有"
  - "skill marketplace comparison"
  - "which skills are we missing"
  - "what can other agents do that we can't"
  - "全部补齐"
  - "还有其他的备注记忆需要吗"
  - "从多维度，多渠道来审计"
  - "看看有什么技能是不需要的"
---

# Skill Ecosystem Audit

Systematic comparison of external skill marketplaces against the local Hermes skill library to identify gaps worth filling.

## Known Skill Marketplaces

| Marketplace | URL | Size | Characteristics |
|---|---|---|---|
| **skills.sh** | https://www.skills.sh | 871K+ installs | Publisher-driven; Microsoft/Anthropic/Vercel/Matt Pocock |
| **SkillsMP** | https://skillsmp.com/zh | 1.8M+ SKILL.md files | SOC occupation classification (23 groups, 867 roles); API access |
| **Agent Skills Hub** | https://agentskillshub.top | 118K+ tools | Security-graded (10 dimensions); MCP + Claude + Codex |
| **CryptoSkills** | https://cryptoskills.dev | 97 skills | Pure Crypto/DeFi/Web3 — vertical specialist |
| **Heurist Mesh** | https://mesh.heurist.ai/console/skill-marketplace | 74 skills | Verified crypto & finance, per-version review |
| **browse.sh** | https://browse.sh | 400+ skills | Site-specific browser automation (pre-optimized selectors) |
| **Hermes Skills Hub** | https://hermes-agent.nousresearch.com/docs/skills | 88K+ | Hermes primary aggregator |

## Audit Workflow (Batched Parallel)

For maximal efficiency with multiple candidate marketplaces:

1. Load Hermes skills: `skills_list()` — note the count and categories.
2. **Batch fetch** all marketplaces in one `web_extract(urls=[...])` call (max 5 per call).
3. For each marketplace, extract:
   - Total skill count and taxonomy
   - Top skills by install/popularity
   - Categories and domains covered
   - Any unique classification system (SOC, security grading, etc.)
4. Build a **gap matrix** — map each external skill to: Have / Partial / Missing.
5. Prioritize: P0 (critical/unique ecosystem) > P1 (high-value publisher) > P2 (nice-to-have).
6. Present concise findings + recommendations.
7. **Execute immediately** — do not stop at recommendations. Create the missing class-level umbrella skills and populate them.

## Gap Taxonomy

Classify missing skills by type:

| Type | Description | Example |
|------|-------------|---------|
| **Ecosystem Gap** | Entire domain missing (0 coverage) | Crypto/Web3/DeFi → missing 30+ protocols |
| **Publisher Gap** | Missing curated publisher's skill series | TraderMonty, Azure, Vercel |
| **Site Gap** | Missing website-specific automation | Amazon, Airbnb, Zillow selectors |
| **Framework Gap** | Missing best-practice guidance | React patterns, architecture review |
| **Data Gap** | Missing data source integrations | Unusual Whales, SEC EDGAR |

## After Audit: Creating Skills at Scale

When filling many gaps at once:

1. **Prefer class-level umbrella skills** — one skill per domain (e.g. `defi-protocols` not individual `aave-skill`, `compound-skill`)
2. **Use `skill_manage(action='create', name='...', category='...')`** — use the right category dir so skills don't end up uncategorized in root
3. **Batch create** — each skill_manage call is one creation, so sequence calls efficiently
4. **After creation, verify categories** — `skills_list()` and check for `"category": null` entries. If any new skills lack a category:
   ```bash
   mv ~/.hermes/skills/<name> ~/.hermes/skills/<category>/
   ```
5. **Update the audit skill afterwards** with this session as a reference example

## Worked Example: 2026-06-23 Full Ecosystem Audit

### Context
User posted 7 skill marketplace URLs: browse.sh, Hermes Skills Hub, CryptoSkills.dev, skills.sh, Heurist Mesh, Agent Skills Hub, SkillsMP. Asked to "对比我们的系统，补充缺少的" (compare and fill gaps).

### Result
236 → 260 skills (+24 new). Added `crypto-web3` category (7 skills). Added `social-media` category.

### Source Marketplaces Audited

| Marketplace | URL | Size | Key Takeaway |
|---|---|---|---|
| **browse.sh** | https://browse.sh | 400+ | Site-specific browser automation (Amazon, Airbnb, Zillow) |
| **Hermes Skills Hub** | https://hermes-agent.nousresearch.com/docs/skills | 88K+ | Hermes primary aggregator |
| **CryptoSkills.dev** | https://cryptoskills.dev | 97 | Pure Web3 vertical — biggest gap found |
| **skills.sh** | https://www.skills.sh | 871K+ installs | Publisher ecosystem (Microsoft, Vercel, Matt Pocock) |
| **Heurist Mesh** | https://mesh.heurist.ai/console/skill-marketplace | 74 | Verified crypto+finance (TraderMonty, Binance Web3, OKX) |
| **Agent Skills Hub** | https://agentskillshub.top | 118K+ | Security-graded, trending tools |
| **SkillsMP** | https://skillsmp.com/zh | 1.8M+ SKILL.md | SOC occupation classification, API |

### Gaps Found & Filled

| Priority | Gap | Skills Created |
|----------|-----|---------------|
| P0 | **Crypto/Web3/DeFi** — 0 coverage before | `crypto-agent-toolkits`, `defi-protocols`, `cross-chain-bridges`, `crypto-data-analytics`, `crypto-wallet-nft`, `crypto-trading-signals`, `crypto-ecosystem-mcp`, `heurist-mesh-integration` |
| P1 | **Publisher Skills** — TraderMonty, Azure, Vercel | `trader-monty-analytics`, `azure-cloud-skills`, `vercel-react-best-practices` |
| P1 | **Code Review & Architecture** — mattpocock, grill-me | `code-review-architecture` |
| P1 | **Professional Finance** — Unusual Whales, SEC EDGAR | `professional-finance-data` |
| P2 | **Site Browser Automation** — Amazon, Airbnb, Zillow | `site-browser-automation`, `browse-cli-integration` |
| P2 | **Social Data MCP** — Twitter/X, news | `social-data-mcp` |
| P2 | **UI/UX Design System** — 50+ styles, 161 palettes | `ui-ux-pro-design` |
| P2 | **Creative Brainstorming** — structured ideation | `creative-brainstorming` |
| P2 | **Video Editing** — ComfyUI video workflows | `video-edit-comfyui` |
| P2 | **Agent Durability** — memory tools, trending | `agent-memory-tools`, `agent-skills-hub-trending` |
| P2 | **Security Grading** — 10-dimension quality scoring | `skill-security-audit` |
| P2 | **Skill Catalog Organization** — SOC classification | `skill-catalog-organization` |

### Post-Creation Classification
After all skills were created, they sat in root directory (no category). Had to manually move them:

```bash
mv agent-memory-tools autonomous-ai-agents/
mv browse-cli-integration community/
mv code-review-architecture software-development/
# ...16 moves total across 9 category dirs
```

**Lesson learned:** Always pass `category='...'` when creating skills, or file them immediately after creation.

### ⚠️ Critical Pitfall: Directory Name ≠ skills_list Name

`skills_list()` returns **clean names** (e.g. `canvas-design`, `ab-test-analysis`, `handoff`), but the **actual directories** on disk have **publisher prefixes**:

| skills_list name | Actual directory |
|---|---|
| `canvas-design` | `anthropic-canvas-design` |
| `ab-test-analysis` | `pm-ab-test-analysis` |
| `handoff` | `matt-handoff` |
| `executing-plans` | `superpowers-executing-plans` |
| `company-valuation` | `finance-company-valuation` |

This means:
- `skill_manage(action='delete', name='canvas-design')` will fail because the directory is `anthropic-canvas-design`, not `canvas-design`
- Bulk `rm -rf` via terminal must use the directory name, not the clean name
- Always verify with `ls <category>/` before assuming the directory name

**Workaround for bulk operations:** Use terminal directly on the skills directory and check actual directory names first.

### ⚠️ Root-Level Duplicate Skills
Skills created without a `category` parameter end up in root. If they're later moved into a category dir, the root copy persists as a stale duplicate. The `find -name SKILL.md` count double-counts these. Always check root-level SKILL.md files when verifying the total count.

### ⚠️ Deletion Is Hard to Undo — Show the Full List First

**Critical lesson from 2026-06-23:** Never delete skills based on counts or summary categories alone. The user may agree to a prune in concept, then realize they want everything back. Once deleted, skills can only be restored by **recreating from scratch** — there's no git history for SKILL.md files.

**Required workflow before any skill deletion:**

1. Generate the **full named list** of every skill proposed for deletion — not counts, not categories, not "about 60". Every single `name:`.
2. Present it as a formatted list the user can scan:
   ```
   Proposed for removal (29 skills):
   ┌────────────────────────────────────────────┐
   │ html-ppt · guizang-ppt-skill              │
   │ gpt-image2-ppt · ppt-image-first          │
   │ anthropic-pptx · claude-design            │
   │ html-artifact · sketch · matt-prototype   │
   │ ... (full list)                           │
   └────────────────────────────────────────────┘
   ```
3. Wait for explicit confirmation with the list visible.
4. **If the user later says "补充回去吧" (restore them):** Use **parallel delegation** — spawn 3 subagents via `delegate_task(tasks=[{goal, context, toolsets:['skills']}])`, each recreating ~30 skills by name. Each subagent generates fresh SKILL.md content from the skill name and description. This is the fastest recovery path (~7 minutes for 90 skills in parallel).

**Why it's hard to undo:**
- No undo command for `rm -rf`
- No git tracking on the skills directory
- Each SKILL.md is uniquely written — can't be regenerated from metadata alone
- The `skill_manage(action='delete')` removes the directory entirely

**Alternative: Disable instead of delete**
For skills the user is unsure about, consider moving them to a `_disabled/` subdirectory rather than deleting. This way they can be restored instantly with:
```bash
mv ~/AppData/Local/hermes/skills/_disabled/<name> ~/AppData/Local/hermes/skills/<category>/
```

## Token Efficiency: Skill List Overhead

The skills list in the system prompt (`<available_skills>` block) contributes ~55% of per-turn input tokens. Each skill adds ~100 chars of description overhead.

**Rule of thumb:** 100 skills ≈ 10K chars ≈ ~2,500-3,500 tokens per turn.

To reduce overhead:
- Delete skills that are decorative/irrelevant to the user's domain (design tools for a trader, business models for an engineer, etc.)
- Keep umbrella/class-level skills (they cover many narrow cases in one entry)
- Each 10 skills removed saves ~1K chars ≈ ~250-350 tokens per turn

## Memory vs Skill Trade-off
Many user-preference facts stored in memory are better served as pointers to the master index skill. The master index (`skill-master-index`) is the authoritative directory — memory should only hold workspace paths, error-recovery patterns, and critical rules the user enforced with frustration. Everything else (what skills exist, which are relevant) belongs in the master index skill.

See `references/marketplace-audit-2026-06-23.md` for full audit results (7 marketplaces, 282 skills final state, token overhead note).

### Key Insight from Classifying 260 Skills
The `community` category has become a catch-all (72 skills). When auditing for gaps, treat each of the 18+ categories as a separate domain.
