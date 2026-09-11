---
name: crypto-ecosystem-mcp
description: "Crypto Ecosystem MCP Servers — BNB Chain MCP, ETH Tools MCP, and blockchain-specific MCP integrations for on-chain queries"
version: 1.0.0
author: Hermes Agent
tags: [crypto, blockchain, mcp, bnb-chain, ethereum, evm]
---

# Crypto Ecosystem MCP Servers

MCP servers for blockchain interaction — query blocks, transactions, contracts, and wallet data.

## Available MCP Servers

### BNB Chain MCP
- Blocks, transactions, and contract data
- ERC20/NFT transfer history
- Wallet balance and activity
- ERC-8004 agent framework
- Greenfield decentralized storage
- Install: `npx @bnb-chain/mcp@latest`

### ETH Tools (austintgriffith)
- Current Ethereum development tools
- abi.ninja for contract ABI resolution
- Foundry integration (cast, forge, anvil)
- Scaffold-ETH 2 deployment scaffold
- Hardhat task runner
- MCP for on-chain queries

### CoinGecko MCP
- Token prices and market data
- DEX pool analytics
- OHLCV chart data
- Trending and top coins
- Already available via FinanceKit MCP

## Configuration

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  bnbchain:
    command: npx
    args: [ "@bnb-chain/mcp@latest" ]
```

## Usage
1. Configure the MCP server
2. Use `hermes mcp test bnbchain` to verify
3. Ask blockchain-specific questions:
   - "Check wallet 0x... on BSC"
   - "What's the latest block on BNB Chain?"
   - "ERC20 transfers for address..."
