# 7-Marketplace Skill Audit (2026-06-23)

## Marketplaces Audited

| Marketplace | URL | Scale | Focus |
|---|---|---|---|
| browse.sh | https://browse.sh | 420 skills | Site-specific browser automation |
| skills.sh | https://www.skills.sh | 871K+ installs | Publisher ecosystem (Vercel, Microsoft, Matt Pocock) |
| CryptoSkills.dev | https://cryptoskills.dev | 97 skills | Pure Web3/DeFi vertical |
| Heurist Mesh | https://mesh.heurist.ai/console/skill-marketplace | 74 skills | Verified crypto+finance |
| Agent Skills Hub | https://agentskillshub.top | 118K+ tools | Security-graded, trending |
| SkillsMP | https://skillsmp.com/zh | 1.8M+ SKILL.md | SOC occupation classification |
| Hermes Docs | https://hermes-agent.nousresearch.com/docs/skills | 88K+ | Hermes primary aggregator |

## Findings

### skills.sh Top-43 Coverage (Full Coverage Achieved)

After audit, all top-43 skills by install count are covered. Final 4 P1 additions:
- `agent-browser` (vercel-labs, 474.2K) — browser agent capability
- `microsoft-foundry` (microsoft/azure-skills, 409.2K) — AI Foundry platform
- `grill-with-docs` (mattpocock/skills, 301.7K) — doc-grounded code review
- `public-apis-live` (Agent Skills Hub #5 trending, 128⭐) — aggregated free APIs

### Heurist Mesh (74 skills)
All crypto/DeFi/trading skills covered by umbrella skills in crypto-web3/ and trading/ categories. TraderMonty skills (market-top-detector, macro-regime-detector, position-sizer, uptrend-analyzer, market-breadth-analyzer) covered by trader-monty-analytics.

### browse.sh (420 skills)
Covered by 4 umbrella skills: site-browser-automation, browse-cli-integration, browser-use-python, opencli-browser, agent-browser. No need for individual site skills.

### CryptoSkills (97 skills)
All covered by 10 crypto-web3 umbrella skills (defi-protocols, crypto-agent-toolkits, cross-chain-bridges, crypto-data-analytics, crypto-wallet-nft, crypto-trading-signals, crypto-ecosystem-mcp, ethereum-smart-contract-dev, crypto-security-audit-tools, heurist-mesh-integration).

## Bulk Deletion Learned

Skills were reduced from 282 → 222 (−60) to reduce system prompt overhead. Categories removed entirely: media, research. Types of skills deleted:
- Creative/design tools (p5js, ascii-art, manim, etc.)
- baoyu duplicates (comic, xhs-images, slide-deck, etc.)
- Business/strategy models (lean-canvas, swot, pricing, etc.)
- Writing/entertainment (webnovel, patent, copyright, etc.)
- One-time workflow tools (handoff, receiving-code-review, etc.)
