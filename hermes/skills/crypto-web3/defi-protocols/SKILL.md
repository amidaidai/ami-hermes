---
name: defi-protocols
description: "DeFi Protocol Skills — Aave, Compound, Curve, Lido, EigenLayer, Jupiter, Kamino, Drift, Fluid for lending, staking, swaps, and yield"
version: 1.0.0
author: Hermes Agent
tags: [crypto, defi, lending, staking, swaps, yield, aave, compound, curve, jupiter]
---

# DeFi Protocol Skills

## Lending Protocols

### Aave V3
- Supply, borrow, repay, withdraw, flash loans
- E-Mode, health factor monitoring
- Chains: Ethereum, Arbitrum, Optimism, Base, Polygon
- SDK: `npm i @aave/core-v3`

### Compound V3 (Comet)
- Supply/borrow/repay/withdraw, liquidation
- Governance proposals, cross-chain deployments
- SDK: `npm i @compound-finance/comet`

### Fluid
- Lending (ERC-4626 fTokens) and vaults (T1–T4)
- Deposit/withdraw/borrow/repay
- On-chain resolvers, no API keys

## DEX / Swaps

### Jupiter (Solana)
- Ultra Swap, Lend, Perps, Trigger, Recurring
- Tokens, Price, Portfolio, Prediction Markets
- SDK: `npm i @jup-ag/api`

### Kamino (Solana)
- Lending, borrowing, automated liquidity strategies
- Leverage trading
- SDKs: klend-sdk, kliquidity-sdk, scope-sdk

### Curve
- StableSwap, CryptoSwap (Tricrypto)
- crvUSD with LLAMMA soft-liquidation
- Gauge voting, factory pools

## Staking / Restaking

### Lido
- Liquid staking ETH → stETH/wstETH
- Withdrawal queue, share rate

### EigenLayer
- Restaking ETH and LSTs to secure AVSs
- Operator registration, delegation, reward claiming, slashing

### Drift (Solana)
- Perpetual futures, spot trading
- Position management, vaults

## Workflow
1. Identify the protocol by chain + task
2. Install the protocol SDK
3. Configure RPC URLs / API keys
4. Follow protocol-specific methods
