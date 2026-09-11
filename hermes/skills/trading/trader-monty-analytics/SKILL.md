---
name: trader-monty-analytics
description: "TraderMonty Professional Market Analytics — market-top-detector, macro-regime-detector, position-sizer, uptrend-analyzer, market-breadth-analyzer"
version: 1.0.0
author: Hermes Agent (adapted from TraderMonty/Heurist)
tags: [trading, stocks, macro, market-breadth, position-sizing, regime-detection]
---

# TraderMonty Professional Market Analytics

A suite of professional market analysis tools from TraderMonty, available via the Heurist Mesh skill marketplace.

## Skills Included

### Market Top Detector
- O'Neil Distribution Days analysis
- Minervini breakdown detection
- Defensive rotation identification
- Composite 0–100 score
- 2–8 week tactical timing for 10–20% corrections

### Macro Regime Detector
- Cross-asset ratio analysis
  - RSP/SPY (equal vs cap-weighted)
  - Yield curve (2yr/10yr)
  - Credit spreads
  - Size factor
  - Equity-bond correlation
  - Sector rotation
- 1–2 year horizon
- 5 regime states

### Position Sizer
- Risk-based position sizes
- Stop-loss calculation
- ATR-based sizing
- Kelly criterion
- Volatility scaling
- Sector concentration checks

### Uptrend Analyzer
- Market breadth via Uptrend Ratio Dashboard
- 0–100 composite from 5 components
- No API key needed

### Market Breadth Analyzer
- Breadth health from public CSV
- 0–100 composite (6 components)
- No API key needed

## Installation
```bash
npx @heurist-network/skills add market-top-detector
npx @heurist-network/skills add macro-regime-detector
npx @heurist-network/skills add position-sizer
npx @heurist-network/skills add uptrend-analyzer
npx @heurist-network/skills add market-breadth-analyzer
```

## Usage
Load this skill when the user asks about:
- Market tops or potential corrections
- Current macro regime
- Position sizing recommendations
- Market breadth / uptrend health
- Multi-asset regime analysis
