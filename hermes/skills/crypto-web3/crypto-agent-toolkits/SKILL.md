---
name: crypto-agent-toolkits
description: "Crypto AI Agent Frameworks — Solana Agent Kit, Coinbase AgentKit, GOAT, Eliza, Brian API, and x402 for building onchain agents"
version: 1.0.0
author: Hermes Agent
tags: [crypto, web3, solana, ethereum, agents, onchain, defi]
---

# Crypto AI Agent Toolkits

Use this skill when building crypto/blockchain agents or integrating onchain capabilities. Load the specific sub-skill for your framework of choice.

## Available Frameworks

### Solana Agent Kit (SendAI)
- 60+ actions for Solana
- LangChain/Vercel AI integration
- MCP server setup
- Install: `npx solana-agent-kit`

### Coinbase AgentKit
- Wallet, transfers, swaps, NFT minting, ENS
- LangChain + Vercel AI SDK
- Chains: Base, Ethereum, Arbitrum, Polygon
- Install: `npm i @coinbase/agentkit`

### GOAT (Great Onchain Agent Toolkit)
- 200+ protocol integrations, 30+ chains
- Modular plugins for AI agents
- Works with AI SDK, LangChain, Eliza
- Install: `npm i @goat-sdk/core`

### Eliza (Multi-Agent Framework)
- Character files, plugin system, trust scoring
- RAG knowledge, Solana wallet integration
- Install: `git clone https://github.com/elizaOS/eliza`

### Brian API
- Natural language → executable Web3 transactions
- Swap, bridge, transfer, deposit across chains
- REST API + LangChain integration
- API key: brian-api.com

### x402 (AI Agent Payments)
- HTTP 402 payment protocol
- ERC-3009 transfers, agent-to-agent payments
- Chains: Base, Ethereum, Arbitrum, Optimism, Polygon, Solana

## Workflow
1. Choose framework based on chain/task
2. Install via npm/pip/npx
3. Configure API keys in ~/.hermes/.env
4. Use the framework's SDK to build onchain capabilities
