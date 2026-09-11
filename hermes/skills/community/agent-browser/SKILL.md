---
name: agent-browser
description: "Agent Browser — Vercel's browser automation skill (474.2K installs on skills.sh). Gives AI agents the ability to navigate, click, type, and extract data from web pages. Complementary to browser-use-python and opencli-browser."
version: 1.0.0
author: Hermes Agent
tags: [browser, automation, vercel, agent, web-scraping, navigation]
---

# Agent Browser (Vercel Labs)

Vercel Labs' official browser automation skill — 474.2K installs, top-5 ranked on skills.sh.

## Installation
```bash
npx skills add vercel-labs/agent-browser
```

## Key Capabilities
- Navigate to URLs and wait for page load
- Click elements by CSS selector, text, or aria-label
- Type text into input fields
- Extract page content (text, HTML, structured data)
- Take screenshots
- Handle forms, multi-step workflows
- 20+ supported agents (Claude Code, Cursor, Codex, Windsurf, etc.)

## When to Use
| vs | Choose this when |
|---|-----------------|
| `browser-use-python` | Need Vercel-style API, working in JS/TS ecosystem |
| `opencli-browser` | Need Hermes-native browser control (selector-first) |
| `site-browser-automation` | Need pre-optimized site-specific workflows |
| `web-access` | Need general web fetching without full browser |

## Common Tasks
```bash
# Install + use via Claude Code
npx skills add vercel-labs/agent-browser

# Then in Claude Code:
# "Navigate to example.com, search for 'React components', 
#  click the first result, and summarize the page"
```

## Integration
Compatible with all Hermes browser-related skills:
- `browser-use-python` — Python alternative
- `site-browser-automation` — site-specific workflows  
- `opencli-browser` — Hermes native
- `webapp-testing` — Playwright testing

> Source: [skills.sh](https://www.skills.sh) — #4 ranked skill by install count (474.2K)
