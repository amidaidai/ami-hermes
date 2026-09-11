# XAU 数据 Fallback 链 (2026-06-19 实战记录)

当 Firecrawl + gold-api + alternative.me 全部不可用时，以下链稳定可用：

## 价格源

| 优先级 | 源 | 方法 | 可靠性 |
|--------|------|------|--------|
| 1 | 金十 MCP `mcp_jin10_get_quote(code="XAUUSD")` | MCP内置 | 稳定 A级 |
| 2 | TV OANDA chart `mcp_tradingview_quote_get(symbol="OANDA:XAUUSD")` | MCP内置 | 稳定 A级 |
| 3 | Kitco live gold `web_extract("https://www.kitco.com/gold-price-today-usa/")` | 抓取Bid/Ask | 稳定 B级 |
| 4 | Yahoo GC=F `web_extract("https://query1.finance.yahoo.com/v8/finance/chart/GC=F")` | 期货价格（需减$15-25溢价估现货） | 稳定 B级 |

## 技术指标 (TV SVP+ICT+VWAP+EMA+CVD)

通过 `chart_set_symbol("OANDA:XAUUSD")` → `chart_set_timeframe("5")` → `data_get_study_values()` 获取：

- S VWAP / W VWAP / M VWAP
- 上下Band1/Band2 ($36/64 日间)
- EMA 9/21/34/55
- CVD Value + CVD Slope
- POC / VAH / VAL
- DO (Day Open)

**陷阱**：切换回OANDA:XAUUSD符号后 `chart_ready: false`，但 `chart_get_state` 确认symbol已切换。重新 `chart_set_timeframe` 一次后study_values可读。

## 宏观背景

- SPX: `web_extract("https://query1.finance.yahoo.com/v8/finance/chart/%5ESPX")` — 稳定
- US10Y: `web_extract("https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX")` — 稳定 (返回4.428%等)
- DXY: **不可用** — Yahoo Finance DXY endpoint 返回空数据。替代：web_extract Investing.com / DailyFX

## 催化

- 金十日历 `mcp_jin10_list_calendar()` — 本周所有已公布+未公布事件
- 金十快讯搜索 `mcp_jin10_search_flash(keyword="黄金 XAU 金价")` — 有时返回空

## 不可用源 (当前)

| 源 | 原因 | 替代 |
|-----|------|------|
| Firecrawl (web_search) | 欠费 Payment Required | web_extract + DDGS |
| gold-api.com/price/XAU | 无法连接 | 金十 + TV OANDA |
| alternative.me/fng | 无法连接 | 跳过 |
| FinanceKit MCP | 速率限制 | Yahoo Finance |
| DXY Yahoo | 无数据 | Investing.com web_extract |

## XAU 引擎限制

XAU 无 Binance 衍生品数据（Funding/OI/Taker/多空比），所以 `multi_model_engine` 无法有效运行。XAU分析依赖：
- 结构性技术分析（VWAP/EMA/CVD/价值区）
- 宏观关联（SPX/US10Y/DXY）
- 催化驱动（Fed/CPI/NFP/零售）
- 金十快讯
