---
name: professional-finance-data
description: "Professional Finance Data Skills — Unusual Whales options flow, dark pool prints, SEC EDGAR filings, earnings analysis, and market structure data"
version: 1.0.0
author: Hermes Agent
tags: [finance, options, earnings, sec, market-data, dark-pool]
---

# Professional Finance Data Skills

Access professional-grade financial data sources beyond standard stock quotes.

## Skills Included

### Unusual Whales API
- Unusual options flow (large/block trades)
- Dark pool prints and off-exchange volume
- Market tide indicator (put/call sentiment)
- Stock Greek exposure (Delta, Gamma, Vega)
- Sweep detection and whale tracking
- Install: `npx @heurist-network/skills add unusual-whales-api`

### SEC EDGAR Access
- Full-text search of SEC filings (10-K, 10-Q, 8-K)
- Insider trading forms (Form 4)
- Beneficial ownership (Form 13D/13G)
- Institutional holdings (Form 13F)
- API: `https://efts.sec.gov/LATEST/search-index?q=QUERY`
- Use `site-browser-automation` skill for browser-based access

### Earnings Analysis
- Pre-earnings preview: consensus estimates, whisper numbers
- Post-earnings recap: beat/miss analysis, stock reaction
- Estimate revision trends (EPS, revenue)
- Use `earnings-preview` and `earnings-recap` community-stars skills

### Options Chain Analysis
- Full options chain via FinanceKit MCP
   - `mcp_financekit_options_chain(symbol, expiration)`
- Implied volatility surface
- Greeks analysis (Delta, Gamma, Theta, Vega, Rho)
- Open interest and volume trends

## Workflow
1. For options flow: use Unusual Whales or FinanceKit MCP
2. For SEC filings: use SEC EDGAR search
3. For earnings: use earnings-preview/recap skills
4. For dark pool: use Unusual Whales
5. Cross-reference multiple sources before making analysis claims
