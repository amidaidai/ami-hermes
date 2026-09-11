---
name: skill-catalog-organization
description: "SkillsMP-style Occupation-Based Skill Classification — organize skills by SOC occupation groups for easier discovery and browsing"
version: 1.0.0
author: Hermes Agent (adapted from SkillsMP methodology)
tags: [organization, classification, catalog, discovery]
---

# Skill Catalog Organization System

Organize skills using the SOC (Standard Occupational Classification) occupation-based system from SkillsMP. Browse 23 occupation groups and 867 SOC roles.

## 23 Occupation Groups

| # | Group | Skill Count (market) |
|---|-------|---------------------|
| 01 | **Computer & Mathematical** | 1,230,339 |
| 02 | **Business & Financial Operations** | 185,719 |
| 03 | **Arts, Design, Entertainment, Sports & Media** | 82,154 |
| 04 | **Office & Administrative Support** | 40,578 |
| 05 | **Legal** | 32,352 |
| 06 | **Life, Physical & Social Science** | 20,062 |
| 07 | **Educational Instruction & Library** | 19,286 |
| 08 | **Management** | 11,773 |
| 09 | **Architecture & Engineering** | ~8,500 |
| 10 | **Healthcare Practitioners** | ~6,200 |
| 11 | **Sales & Related** | ~5,800 |
| 12 | **Installation, Maintenance & Repair** | ~4,500 |
| 13 | **Construction & Extraction** | ~3,800 |
| 14 | **Transportation & Material Moving** | ~3,200 |
| 15 | **Production** | ~2,900 |
| 16 | **Food Preparation & Serving** | ~2,500 |
| 17 | **Community & Social Service** | ~2,300 |
| 18 | **Protective Service** | ~2,000 |
| 19 | **Building & Grounds Cleaning** | ~1,500 |
| 20 | **Personal Care & Service** | ~1,200 |
| 21 | **Healthcare Support** | ~1,000 |
| 22 | **Farming, Fishing & Forestry** | ~800 |
| 23 | **Military** | ~400 |

## By Category (8 top-level)

| Category | Skills |
|----------|--------|
| Tools | 426,384 |
| Business | 326,476 |
| Development | 248,468 |
| Testing & Security | 186,319 |
| Data & AI | 164,182 |
| DevOps | 141,176 |
| Documentation | 120,985 |
| Content & Media | 109,550 |

## Hermes Current Categories (2026-06-23, 260 skills)

Our current 19 categories map against these as:

| Hermes Category | Skills | SOC Group Match | Type |
|----------------|--------|-----------------|------|
| `autonomous-ai-agents` | 8 | Computer & Mathematical | Agent core |
| `community` | 72 | Cross-cutting | Catch-all |
| `community-stars` | 42 | Cross-cutting (curated) | Curated picks |
| `creative` | 21 | Arts/Design/Media | Design & video |
| `crypto-web3` | 7 | Business & Financial Ops | ⭐ New — Web3 domain |
| `data-science` | 2 | Data & AI | Python analysis |
| `devops` | 6 | DevOps / Architecture & Engineering | Infra |
| `email` | 1 | Office & Admin Support | Himalaya |
| `github` | 6 | Development | Git platform |
| `media` | 3 | Content & Media | GIFs, audio |
| `mlops` | 3 | Data & AI + DevOps | Model lifecycle |
| `note-taking` | 1 | Office & Admin Support | Obsidian |
| `productivity` | 11 | Business / Office | Office tools |
| `research` | 5 | Life, Physical & Social Science | Academic |
| `security` | 2 | Testing & Security | Audit |
| `smart-home` | 1 | Tools | Philips Hue |
| `social-media` | 2 | Content & Media | ⭐ New — Twitter/X/news MCP |
| `software-development` | 15 | Development | Code frameworks |
| `trading` | 14 | Business & Financial Ops | 棠溪 + finance data |

### Category Growth Rule
When a new domain gets 3+ skills, consider creating a new top-level category (e.g. `crypto-web3` went from 0→7 in one session). Keep single-skill categories lean — merge into parent categories unless they're qualitatively different domains.

## Search Strategy
When searching for a skill:
1. Identify the user's occupation/role
2. Map to the SOC group
3. Filter by top-level category
4. Search within matching skills
