---
name: crypto-wallet-nft
description: "Crypto Wallet & NFT Skills — OpenSea, Bitget Wallet, Elytro, and wallet interactions across chains"
version: 1.0.0
author: Hermes Agent
tags: [crypto, nft, wallet, opensea, erc-4337]
---

# Crypto Wallet & NFT Skills

## NFT Marketplaces

### OpenSea
- NFT metadata, collection stats, listings/offers
- Seaport trades, ERC20 swaps
- SDK: `npm i @opensea/seaport-js`
- API: docs.opensea.io

### Elytro (ERC-4337)
- EIP-4337 smart wallet
- Account abstraction, gas sponsorship
- Bundle transactions

## Wallet Tools

### Bitget Wallet
- Market data, token info, swap quotes
- Security audits
- Chains: ETH, SOL, BSC, Base, etc.
- Web: bitget.com

### OKX DEX
- Swap tokens across 20+ chains
- Aggregates 500+ DEX sources
- Slippage control, price impact protection
- SDK: `npm i @okxdex/swap-sdk`

### OKX Token API
- Token search, metadata, market cap, liquidity
- Volume, trending rankings, holder distribution
- 20+ chains supported

## Workflow
1. Identify chain and wallet type (EOA vs smart wallet)
2. Use OpenSea SDK for NFT operations
3. Use OKX DEX for multi-chain swaps
4. Use Bitget for wallet-level queries/audits
