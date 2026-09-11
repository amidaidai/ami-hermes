---
name: financial-data-setup
description: >
  Set up free financial data sources (MCP servers, APIs) for Hermes Agent.
  Covers FinanceKit MCP, akshatbindal/finance-mcp-server, and stock/technical
  analysis tools via yfinance. Use when user asks "add financial data",
  "free finance MCP", "stock market data setup", or "金融数据".
  Also use when installing financial MCPs or troubleshooting adapter issues.
tags:
  - finance
  - MCP
  - stock-market
  - free-data
  - yfinance
---

# Financial Data Setup

Set up free (no API key / free-tier) financial data sources for Hermes Agent.

## Available Free Financial MCP Servers

### 1. FinanceKit MCP

**GitHub**: `vdalhambra/financekit-mcp`
**Cost**: 0 yuan (self-hosted unlimited via uvx)
**Data Source**: Yahoo Finance (free) + CoinGecko API (free tier) + ta library (local calc)

**17 Tools:**
- `stock_quote`, `multi_quote`, `company_info` — stock data
- `crypto_price`, `crypto_trending`, `crypto_search`, `crypto_top_coins` — crypto
- `technical_analysis`, `price_history` — technical indicators (RSI, MACD, BB, ADX, Stochastic, ATR, OBV)
- `market_overview`, `sector_rotation` — market health
- `compare_assets`, `portfolio_analysis`, `risk_metrics`, `correlation_matrix` — portfolio
- `earnings_calendar`, `options_chain` — events & derivatives

**Install:**
```bash
hermes mcp add financekit --command uvx --args --from financekit-mcp financekit
```

### 2. akshatbindal/finance-mcp-server

**GitHub**: `akshatbindal/finance-mcp-server`
**Cost**: 0 yuan (yfinance free data)
**Data Source**: Yahoo Finance (free) via yfinance Python library

**11 Tools:**
- `get_comprehensive_stock_info` — company + market + financial + analyst
- `get_historical_data` — customizable period/interval
- `get_options_data` — options chain (calls/puts, OI, IV)
- `get_institutional_holders` — institutional & major holders
- `get_earnings_calendar` — earnings history + analyst targets
- `get_analyst_recommendations` — upgrades/downgrades
- `get_financial_statements` — income statement, balance sheet, cash flow
- `get_news` — latest news
- `get_technical_analysis` — SMA/EMA/RSI/MACD/BB/support-resistance
- `get_sector_performance` — multi-stock comparison
- `get_dividend_history` — dividend history & stats

## Installation

### Known Pitfall: akshatbindal/finance-mcp-server Binary

The `finance-mcp-server.exe` binary (Windows PE) does NOT start the MCP stdio transport correctly when invoked directly. **Workaround**: use the venv Python to run the async main function directly:

```bash
# ❌ Does NOT work:
# hermes mcp add finance --command finance-mcp-server

# ✅ Works:
hermes mcp add finance --command "<hermes-venv-python.exe>" --args -c "from finance_mcp.server import main; import asyncio; asyncio.run(main())"
```

On Windows the venv Python path is typically:
`C:/Users/<user>/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe`

### FinanceKit MCP Installation

```bash
# FinanceKit works via uvx — no binary issues:
hermes mcp add financekit --command uvx --args --from financekit-mcp financekit
```

## Verification

```bash
# Test connection
hermes mcp test financekit
hermes mcp test finance

# List all MCP servers
hermes mcp list
```

## Coverage Comparison

| Feature | FinanceKit | akshatbindal/finance | Notes |
|---|---|---|---|
| Technical Analysis | ✅ 10+ indicators + signals | ✅ SMA/EMA/RSI/MACD/BB | Complement each other |
| Fundamentals | ❌ Basic | ✅ 3 statements + dividends | Finance is better here |
| Options Chain | ✅ Basic | ✅ Full (strike, OI, IV, Greeks) | Both good |
| Crypto | ✅ Price + trending + top coins | ❌ | FinanceKit unique |
| Portfolio Analysis | ✅ Value, sector, concentration | ❌ | FinanceKit unique |
| Market Overview | ✅ Indices + VIX + sentiment | ❌ | FinanceKit unique |
| Institutional Holders | ❌ | ✅ | Finance unique |
| Analyst Recommendations | ❌ | ✅ | Finance unique |
| News | ❌ | ✅ | Finance unique |
| Self-Hosted | ✅ uvx | ✅ python -c (venv) | Both free |
| API Key Required | ❌ No key needed | ❌ No key needed | Both truly free |

## Recommended Combo

Install **both** for full coverage — they complement each other with zero overlap:
- **FinanceKit** → market overview, technical analysis, crypto, portfolio
- **akshatbindal/finance** → fundamentals, options chain, institutional holders, dividends, news
