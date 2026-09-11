---
name: crypto-exchange-connectors
description: "Crypto Exchange Connectors — Bybit, OKX, Coinbase Advanced, HTX, 3Commas trading APIs and automated trading bots"
version: 1.0.0
author: Hermes Agent (adapted from CryptoSkills.dev trading collection)
tags: [crypto, exchange, trading, bybit, okx, coinbase, api]
---

# Crypto Exchange Connectors

Trading API connectors for major crypto exchanges.

## Bybit
- Spot & derivatives trading
- REST + WebSocket APIs
- SDK: `pip install pybit` / `npm i bybit-api`
- Unified margin, inverse perpetual, USDC contracts
- Leverage, position management, stop-loss/take-profit

## OKX
- Spot, margin, futures, options
- 20+ chains for DEX aggregation
- SDK: `pip install okx` / `npm i okx-api`
- CEX + DEX in one platform
- Trading bots, copy trading

## Coinbase Advanced
- Spot trading API
- SDK: `npm i coinbase-api` / `pip install coinbase-advanced-py`
- Real-time feeds via WebSocket
- Portfolio management, fee tiers
- Requires API key + secret from coinbase.com

## HTX (formerly Huobi)
- Spot & futures trading
- SDK: `pip install huobi` / `npm i huobi-api`
- Cross-margin, isolated margin
- API: htx.com

## 3Commas
- Smart trading bots (DCA, Grid, Composite)
- Portfolio management, signal trading
- SDK: `npm i 3commas-api-node`
- Connects to Binance, Bybit, OKX, Coinbase, HTX, etc.

## Comparison

| Exchange | Spot | Futures | Options | SDK Maturity | Fee Structure |
|----------|------|---------|---------|--------------|---------------|
| Bybit | ✓ | ✓ | ✗ | ⭐⭐⭐⭐ | Maker -0.01%, Taker 0.06% |
| OKX | ✓ | ✓ | ✓ | ⭐⭐⭐⭐⭐ | Maker 0.02%, Taker 0.05% |
| Coinbase | ✓ | ✗ | ✗ | ⭐⭐⭐ | Maker 0.00%, Taker 0.40% |
| HTX | ✓ | ✓ | ✗ | ⭐⭐⭐ | Maker 0.02%, Taker 0.04% |

## Companion Skills

Load **`binance-trading`** for Binance-specific spot/futures trading (already configured).
Load **`crypto-trading-signals`** for on-chain signals and meme coin analysis.
Load **`trader-monty-analytics`** for professional market analysis (stocks/macro).

## Workflow
1. Choose exchange based on trading needs
2. Generate API key with appropriate permissions
3. Store credentials securely (not in code)
4. Use exchange SDK for order management
5. Implement risk controls (max position, stop-loss)
