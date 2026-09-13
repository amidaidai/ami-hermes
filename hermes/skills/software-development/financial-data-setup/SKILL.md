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

## Troubleshooting: Yahoo 腿 "Too Many Requests"（2026-09-13 二次定位 → 已修复）

**症状**：Yahoo 类工具（stock_quote / market_overview / price_history）返回
`Too Many Requests. Rate limited.`，而 crypto_price（CoinGecko 腿）正常。

**真正根因（决定性对照实验）**：Yahoo 封的是**本机直连 IP**，而 financekit MCP
子进程**没有代理**。同一个调用，直连 429、走代理 200：

| 同一次 `get_quote('AAPL')` | 结果 |
|:--|:--|
| `env -u HTTP_PROXY -u HTTPS_PROXY uvx --from financekit-mcp …`（直连） | ❌ `Too Many Requests. Rate limited.` |
| `HTTP_PROXY=http://127.0.0.1:7897 … uvx --from financekit-mcp …` | ✅ `332.27` |

**为什么"杀进程"看起来管用（上一轮的误判，勿再沿用）**：在终端里跑诊断命令时
shell 自带 `HTTP_PROXY`，所以"新进程"实际走的是代理、当然成功；而 MCP 子进程由
网关生成、无代理，重启多少次仍是 429。**"长命进程 stale"是错误结论。**

**为什么网关自己的代理传不进去**：`tools/mcp_tool.py::_build_safe_env()` 对 stdio
子进程**白名单过滤**环境变量（防密钥泄漏），只有 `_SAFE_ENV_KEYS` / `XDG_*` /
secret-source 变量能过。代理变量不在名单内 → 必须在**该 server 的 `env:` 块**
显式写（`env.update(user_env)` 在过滤之后，优先级最高）。

**修复（已落地 + 端到端验证）**：

```bash
hermes config set mcp_servers.financekit.env.HTTP_PROXY  "http://127.0.0.1:7897"
hermes config set mcp_servers.financekit.env.HTTPS_PROXY "http://127.0.0.1:7897"
hermes config set mcp_servers.financekit.env.NO_PROXY    "localhost,127.0.0.1"
```

改完要**重读配置**才生效：网关会话里发 `/reload-mcp`（或 `hermes gateway restart`）。
验证方式：`hermes chat -q "用 financekit 查 AAPL"` → `AAPL=332.27` ✅

**注意**：`patch` 工具**拒绝写 `~/.hermes/config.yaml`**（安全护栏），只能用 `hermes config set`。

**只有境外源需要代理**：binance / jin10 / stock-api / tradingview / hermes-studio 目标
可直连，别给它们加。杀 financekit 进程会断当前会话的 MCP 连接（ClosedResourceError），
新会话自愈；期间美股/宏观用 FMP（/stable/quote）或 stock-api 兜底。

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
