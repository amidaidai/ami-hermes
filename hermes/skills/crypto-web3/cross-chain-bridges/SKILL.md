---
name: cross-chain-bridges
description: "Cross-Chain Bridge & Interop Skills — LayerZero, Wormhole, Hyperlane, Axelar, deBridge for cross-chain messaging and token transfers"
version: 1.0.0
author: Hermes Agent
tags: [crypto, cross-chain, bridges, layerzero, wormhole, interoperability]
---

# Cross-Chain Bridges & Interoperability

## LayerZero V2
- OApp framework for omnichain apps
- OFT (Omnichain Fungible Token)
- DVN configuration, message lifecycle
- Chains: Ethereum, Arbitrum, Base, Optimism, Polygon
- SDK: `npm i @layerzerolabs/lz-v2-sdk`

## Wormhole
- VAA-based messaging and token transfers (NTT)
- Guardian network, automatic/manual relayers
- Wormhole Queries for cross-chain reads
- Chains: Ethereum, Solana, Arbitrum, Base, Optimism
- SDK: `npm i @wormhole-foundation/sdk`

## Hyperlane
- Permissionless interoperability
- Mailbox messaging, Interchain Security Modules
- Warp Routes for token bridging, hooks, interchain accounts
- SDK: `npm i @hyperlane-xyz/sdk`

## Axelar
- General Message Passing (GMP)
- Interchain Token Service (ITS)
- AxelarExecutable contract pattern
- Multichain

## deBridge
- Cross-chain bridges, message passing
- Token transfers between Solana and EVM chains
- Trustless external calls

## Workflow
1. Choose bridge based on target chains and task type
2. Install SDK
3. Configure RPC endpoints
4. Submit cross-chain message/token transfer
