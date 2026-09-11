---
name: crypto-data-analytics
description: "Crypto Data & Analytics — CoinGecko, Dune Analytics, Metengine, on-chain data queries and market analytics"
version: 1.0.0
author: Hermes Agent
tags: [crypto, analytics, data, coingecko, dune, onchain]
---

# Crypto Data & Analytics

## CoinGecko API
- Token prices, DEX pool data, OHLCV charts
- Trades, market analytics, trending coins
- Search: `mcp_financekit_crypto_search` / `mcp_financekit_crypto_price`
- Pro API: coingecko.com/api

## Dune Analytics
- DuneSQL queries against decoded contract tables
- Saved queries, credit monitoring
- CLI: `npm i @duneanalytics/cli`
- Web: dune.com

## Metengine
- Real-time smart money analytics
- Polymarket, Hyperliquid, Meteora
- 63 endpoints, pay-per-request via x402
- No API keys needed

## Heurist Mesh
- Real-time token data, DeFi analytics
- Wallet intelligence, project research
- Twitter/X sentiment
- Install: `npx @heurist-network/skills add heurist-mesh`

## CoinGecko (via FinanceKit MCP + Pro API Key)

**Pro Key 已全面激活**（2026-06-28，`CG-tkuaqHxNbpTQ92HgpvEc4QXY`）。500 req/min，所有 CG 脚本已灌注：

| 脚本 | 状态 |
|------|------|
| `coingecko_collector.py` | ✅ Pro |
| `data_gatherer.py` | ✅ Pro |
| `multi_source_collector.py` | ✅ Pro |
| `trading_system.py` | ✅ Pro |
| `orion_screener_radar.py` | ✅ Pro |

### Pro 专属端点（multi_source_collector.py）

- `cg_categories()` — 板块/分类 24h 涨幅排名，资金轮动检测
- `cg_coin_detail("bitcoin")` — 流动性评分/社区/开发者/CG 评分/情绪投票
- `cg_exchange_volumes("bitcoin")` — BTC 交易所成交量明细，信任评分假量检测
- `cg_top_coins(10)` — Top 10 排名 + BTC 山寨轮动（已有，现 Pro 加速）
- `cg_trending()` — 热搜币种（已有，现 Pro 加速）

### 缓存策略

所有 CG 函数使用 `_cached()` 缓存层（TTL 300-600s），避免 Orion cron 竞争 Key。

Built-in via `mcp_financekit_crypto_price`, `mcp_financekit_crypto_search`, `mcp_financekit_crypto_top_coins`, `mcp_financekit_crypto_trending`

## Workflow
1. For quick price/data: use FinanceKit MCP (already configured)
2. For Pro-grade market data: use `multi_source_collector.py` (cg_categories/cg_coin_detail/cg_exchange_volumes) — all CG scripts now run with Pro Key
3. For deep onchain analysis: Dune SQL queries (free tier 40req/min, needs free account)
4. For real-time/meme/smart-money: Metengine (paid, skip)
5. For comprehensive research: Heurist Mesh
6. For BTC ETF flow: SoSoValue public page via `web_extract("https://m.sosovalue.com/assets/etf/us-btc-spot")` — free, no key needed

## Free Data Sources (no paid plan required)

### SoSoValue ETF Flow
- BTC spot ETF daily net inflow/outflow, cumulative totals, per-fund breakdown
- **Free, no key**: just `web_extract("https://m.sosovalue.com/assets/etf/us-btc-spot")`
- Signal: net inflow > +$100M = institutional bullish / net outflow > -$100M = caution
- Write into analysis card as "ETF Flow" row

### Dune Analytics
- Free tier: 40 API requests/min, SQL queries on blockchain data
- Requires free account signup at dune.com
- Pre-built public queries available for: exchange BTC balance changes, stablecoin supply, whale movements
- CLI available: `npm i @duneanalytics/cli`
