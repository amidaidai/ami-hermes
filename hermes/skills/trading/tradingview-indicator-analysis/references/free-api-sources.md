# 免费API数据源状态 (2026-06-18 锁定)

## 已接入·运转中

| API | Key | 免费额度 | 提供 | 采集器 |
|-----|-----|----------|------|--------|
| **CoinMarketCap** | ✅ secrets/ | 333次/天 | 加密行情·市占·恐慌贪婪 | multi_source_collector |
| **CoinGecko** | ❌ 无需 | 10-30次/分 | 社区情绪·热门·板块·汇率 | coingecko_collector |
| **Alpha Vantage** | ✅ secrets/ | 500次/天 | 股票报价·外汇 | multi_source_collector |
| **Twelve Data** | ✅ secrets/ | 800次/天 | RSI·MACD·多品种 | multi_source_collector |
| **Massive** | ✅ secrets/ | 免费层 | 股票/加密日线·ETF·期货 | multi_source_collector |
| **alt.me** | ❌ 无需 | 无限 | 恐慌贪婪指数 | coingecko_collector |
| **Brave Search** | ✅ secrets/ | 2000次/月 | Web搜索·情绪 | sentiment_search |
| **Exa** | ✅ secrets/ | 1000次/月 | Web搜索(备用) | 待接入 |
| **Binance** | ✅ MCP | 无限 | 加密价格·衍生品六件套 | MCP |
| **金十** | ✅ MCP | 无限 | 快讯·日历·XAU报价 | MCP |
| **TradingView** | ✅ MCP | 无限 | 图表·DMI·指标·截图 | MCP |
| **FinanceKit** | ✅ MCP | 无限 | 股票·ETF·期权·加密 | MCP |

## 不可用/待修复

| API | 状态 | 原因 |
|-----|------|------|
| FMP | ❌ 403 | Key过期或计划限制 |
| Tavily | ❌ 0结果 | API不返回数据 |
| AnySearch | ❌ 不通 | 端点不可达 |
| Firecrawl | ❌ 欠费 | 额度耗尽 |
| DDGS | ⚠️ 不稳定 | 限速后返回空·仅备用 |

## 搜索优先级

```
Brave (2000/月) → Exa (1000/月) → DDGS (不稳定)
→ 金十快讯 + CG社区情绪 兜底
```

## Key文件位置

所有Key存储在 `hermes/secrets/`：
- `brave_api_key.txt` · `exa_api_key.txt`
- `coinmarketcap_api_key.txt` · `alphavantage_api_key.txt`
- `twelvedata_api_key.txt` · `massive_api_key.txt`
- `tushare_token.txt` · `fmp_api_key.txt`
