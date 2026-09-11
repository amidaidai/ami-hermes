---
name: github-stars-system-learning
description: Use when learning from a user's GitHub Stars to improve Hermes skills, workflows, and personal agent system design.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [github, stars, skills, system-design, personalization]
    related_skills: [github-auth, github-repo-management, slowmist-agent-security, hermes-agent]
---

# GitHub Stars System Learning

## Overview

Use this workflow to study a user's GitHub Star list and turn it into concrete Hermes improvements: installed skills, reports, recommendations, route maps, and safety boundaries.

The goal is not to blindly install everything. Treat Stars as a preference graph: what the user repeatedly bookmarks reveals their desired agent capabilities, domains, tools, and risk tolerance.

## When to Use

- User asks to study their GitHub Stars, favorites, starred repos, or bookmarks.
- User wants to improve their Hermes setup based on repositories they follow.
- You need to discover relevant community Skills, MCP servers, browser tools, memory systems, finance tooling, or automation workflows.
- You need to create a structured roadmap from a large collection of repos.

Don't use this to execute unknown code from starred repos without explicit need and safety review.

## Workflow

1. **Load GitHub skills**
   - Load `github-repo-management` for GitHub API and cloning patterns.
   - Load `github-auth` if unauthenticated API calls fail or rate-limit.
   - Load `slowmist-agent-security` before installing or running unknown community code.

2. **Fetch Stars metadata**
   - Prefer GitHub API with authentication. Unauthenticated calls hit the 60 req/hr limit fast.
   - **Auth fallback chain**: try `gh auth status` → try `GITHUB_TOKEN` from Hermes `.env` → try `~/.git-credentials` (extract token with regex `https://[^:]+:([^@]+)@github.com`). Pass token as `Authorization: Bearer <token>` header.
   - Use pagination: `?per_page=100&page=N`, stop when response is empty array. Add `time.sleep(0.3)` between pages to stay under secondary rate limits.
   - Save raw metadata to `outputs/github-stars/<user>-stars.json`.
   - Save reduced metadata to `outputs/github-stars/<user>-stars-summary.json` with: `full_name`, `url`, `description`, `language`, `topics`, `stars`, `forks`, `updated_at`, `archived`, `homepage`.

3. **Classify the collection**
   - Count languages and topics.
   - Extract likely categories: AI agents, skills, Hermes/OpenClaw, browser automation, finance/trading, memory/RAG, dashboards/UI, security, media/content, monitoring/digest.
   - Identify repeated patterns rather than over-weighting a single popular repo.

4. **Find installable Skills**
   - Shallow clone likely skill repos into `sandbox/star-skill-audit/repos/`:
     ```bash
     git clone --depth 1 --filter=blob:none --no-checkout <url> <dir>
     cd <dir> && git sparse-checkout init --cone && git sparse-checkout set . && git checkout -q
     ```
   - Use `git ls-tree -r --name-only HEAD | grep -Ei 'SKILL\.md|skills/'` to find nested skills before waiting for checkout.
   - **Windows pitfall**: `sparse-checkout` then `git checkout` often fails to materialize files on Windows (directories appear empty despite `ls-tree` showing files). **Fix**: `git sparse-checkout disable && git checkout -f HEAD`. This does a full working-tree checkout and is the only reliable path on Windows.
   - Install only selected Skill directories under `~/AppData/Local/hermes/skills/community-stars/` on Windows or `~/.hermes/skills/community-stars/` on POSIX.

5. **Install safely**
   - Copy Skill directories only; do not run repo scripts during installation.
   - Ignore `.git`, `node_modules`, virtualenvs, caches, and large media unless required.
   - Skip or quarantine Skills involving account posting, cookies, browser profiles, CAPTCHA bypass, pentesting, token extraction, auto-trading, or persona overrides unless the user explicitly wants them.

6. **Post-install audit** (mandatory after installing third-party skills)
   - Scan every installed `SKILL.md` for risk keyword patterns:
     - HIGH: credential/token, publish/post-to, browser/captcha/playwright, reverse-engineer/unofficial-api
     - MEDIUM: API/endpoint, scrape/crawl, trade/order
   - Assign risk tiers: 🟢 LOW / 🟡 MEDIUM / 🔴 HIGH.
   - Save audit results to `outputs/github-stars/community-stars-audit.json`.
   - For HIGH-risk skills, flag them explicitly in the report for human review.

6. **Post-install audit** (mandatory after installing third-party skills)
   - Scan every installed `SKILL.md` for risk keyword patterns:
     - HIGH: credential/token, publish/post-to, browser/captcha/playwright, reverse-engineer/unofficial-api
     - MEDIUM: API/endpoint, scrape/crawl, trade/order
   - Assign risk tiers: 🟢 LOW / 🟡 MEDIUM / 🔴 HIGH.
   - Save audit results to `outputs/github-stars/community-stars-audit.json`.
   - For HIGH-risk skills, flag them explicitly in the report for human review.

7. **Verify**
   - Scan every installed `*/SKILL.md`.
   - Confirm frontmatter starts with `---` and has a `name` field.
   - Count installed skills and write an `installed-star-skills.json` manifest.

8. **Write a report**
   - Include counts, themes, installed Skills, skipped risky repos, audit tier summary, and recommended next phases.
   - Also generate a **skill index** (`<user>-skills-index.md`) — all installed community skills grouped by category (design/engineering/finance/security...) as a Markdown table.
   - Use concrete local paths in Markdown.
   - Use concrete local paths in Markdown.
   - Suggest `/reload-skills` or a fresh Hermes session.

9. **TradingView / finance star triage**
   - When the user's goal is TradingView or trading analysis, use `references/tradingview-finance-stars-triage.md` to classify finance/quant/trading-agent repos and decide what is safe to install.
   - Keep TradingView desktop readers, CDP/browser-cookie readers, exchange/broker integrations, and order-placement tools as explicit-approval candidates; report them, but do not auto-install or run them.

## Safety Rules

- Never blindly execute install scripts from a starred repository.
- Never enable social posting, browser cookie extraction, or trading execution by default.
- Treat memory-system replacements as architecture references unless isolated tests are requested.
- Treat security/pentest tools as review references unless the user requests a legal, scoped assessment.
- Preserve raw metadata and reports for auditability.

## Verification Checklist

- [ ] Stars metadata saved locally (both raw + summary JSON).
- [ ] Auth fallback chain exercised if API rate-limited.
- [ ] Language/topic classification generated.
- [ ] Candidate skill repositories cloned and `ls-tree` scanned for `SKILL.md`.
- [ ] Windows sparse-checkout fix applied if files not materialized.
- [ ] Selected skills copied into a community folder.
- [ ] Risky skills explicitly skipped or quarantined.
- [ ] Post-install audit run: every `SKILL.md` scanned for risk patterns, tiers assigned, audit JSON saved.
- [ ] All installed `SKILL.md` files pass frontmatter/name checks.
- [ ] A human-readable report + skill index written under `outputs/github-stars/`.
- [ ] `/reload-skills` or new session recommended to user.
- [ ] `/reload-skills` or new session recommended to user.
