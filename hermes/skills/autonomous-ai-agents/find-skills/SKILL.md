---
name: find-skills
description: "Find & Discover Agent Skills — search 20,000+ skills across the ecosystem. Based on vercel-labs/skills — the #1 most installed skill (2.1M+ installs)"
version: 1.0.0
author: Hermes Agent (adapted from vercel-labs/skills)
tags: [skills, discovery, search, find, install]
---

# Find Skills

The #1 most installed skill in the agent skills ecosystem (2.1M+ installs on skills.sh). Use this to discover the right skill for any task.

## Usage

When the user asks to do something that might have an existing skill:

1. **Search skills.sh**
```bash
# Browse trending
open https://www.skills.sh/trending

# Search by keyword
open https://www.skills.sh/search?q=<query>

# Filter by publisher
open https://www.skills.sh/microsoft/azure-skills
```

2. **Search Hermes Skills Hub**
```bash
hermes skills search <query>
hermes skills browse
```

3. **Search community sources**
```bash
# Agent Skills Hub (118k+ security-graded)
npx @agentskillshub/cli search "<query>" --safe

# SkillsMP (1.8M+ SKILL.md files)
open https://skillsmp.com/search?q=<query>

# Heurist Mesh (verified crypto/finance)
npx @heurist-network/skills list

# CryptoSkills
npx cryptoskills search <query>
```

4. **Install found skill**
```bash
hermes skills install <id-or-url>
```

## Search by Task Type

| Task | Where to Search |
|------|----------------|
| Code review | skills.sh / SkillsMP |
| Design/UI | skills.sh (anthropics/skills, vercel-labs) |
| Crypto/DeFi | CryptoSkills / Heurist Mesh |
| Finance/Stocks | Heurist Mesh (TraderMonty) |
| Cloud (Azure) | skills.sh (microsoft/azure-skills) |
| Browser automation | browse.sh (360+ sites) |
| Video editing | skills.sh (agentspace-so) |
| React/Next.js | skills.sh (vercel-labs) |
| Security audit | Agent Skills Hub |
| Any/Unknown | Start with skills.sh #1 ranked |

## Pro Tips

- Use `find-skills` **before** building a custom solution — there's often a 500MB+ skill already available
- Check install count as a quality signal (higher ≠ always better, but indicates community validation)
- Check last update date — stale skills are risky
- Prefer publishers: vercel-labs, microsoft, anthropics, mattpocock

> *Based on vercel-labs/skills find-skills (2.1M+ installs) — the #1 skill in the ecosystem.*
