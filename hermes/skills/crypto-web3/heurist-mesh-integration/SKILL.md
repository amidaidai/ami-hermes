---
name: heurist-mesh-integration
description: "Heurist Mesh Verified Skill Marketplace — install trusted crypto and finance skills directly from the @heurist-network/skills CLI"
version: 1.0.0
author: Hermes Agent
tags: [crypto, finance, heurist, mesh, marketplace, verification]
---

# Heurist Mesh Integration

Heurist Mesh is a verified skill marketplace for crypto and finance agent skills. Every skill is audited before appearing.

## Installation

```bash
npx @heurist-network/skills add <skill-name>
```

## Available Skills by Category

### Crypto
| Skill | Description | Installs |
|-------|-------------|----------|
| heurist-mesh | Real-time token data, DeFi analytics, wallet intelligence | 107 |
| bitget-wallet | Market data, token info, swap quotes, security audits | 66 |
| opensea-skill | NFT metadata, collection stats, listings/offers | 58 |
| binance-web3-spot | Binance Spot requests via API | 55 |
| binance-web3-meme-rush | Meme token fast-trading, launchpad lists | 51 |
| binance-web3-query-token-info | Token details with real-time market data | 47 |
| binance-web3-trading-signal | On-chain smart money signals | 46 |
| okx-dex-swap | Swap tokens across 20+ chains | 51 |
| okx-dex-token | Token search, metadata, trending | 49 |
| smart-money-miner | Mine/find smart money addresses | 52 |
| four-meme-ai | Meme tokens on Four.Meme (BSC) | 52 |
| elytro | EIP-4337 smart wallet | 45 |
| fluid | Lending and vaults (ERC-4626) | 51 |
| dune | Dune SQL queries, decoded contract tables | 46 |

### Stocks / Macro
| Skill | Description | Installs |
|-------|-------------|----------|
| market-top-detector | O'Neil Distribution Days, Minervini | 75 |
| macro-regime-detector | Cross-asset ratio analysis | 61 |
| position-sizer | Risk-based position sizes | 61 |
| uptrend-analyzer | Market breadth dashboard | 61 |
| market-breadth-analyzer | Breadth health 0-100 composite | 52 |
| unusual-whales-api | Options flow, dark pool, GEX | 47 |

### Developer
| Skill | Description | Installs |
|-------|-------------|----------|
| bnbchain-mcp | MCP server for BNB Chain | 55 |
| eth-tools | Ethereum tools (Foundry, Hardhat) | 54 |

### Social
| Skill | Description | Installs |
|-------|-------------|----------|
| opennews-mcp | Crypto news + trading signals | 55 |
| opentwitter-mcp | Twitter/X data access | 50 |
| arguedotfun | Argumentation markets | 49 |

## Usage

Load this skill when:
- User needs crypto data or DeFi interactions
- User asks about stock market technical analysis
- User needs on-chain analytics or NFT queries
- User wants social sentiment analysis

Then look up the specific skill in the tables above and install with `npx @heurist-network/skills add <name>`.
