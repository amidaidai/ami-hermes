# 数据管道 v6.8.2 (2026-06-18 锁定)

## 一键出卡

```bash
python hermes/scripts/auto_card.py BTCUSDT     # 加密
python hermes/scripts/auto_card.py XAUUSD       # 贵金属
python hermes/scripts/auto_card.py BTCUSDT --push  # +推送
```

输出: `data/auto_card_{symbol}.md`

## 数据源矩阵

| 源 | 品种 | 免费 | Key位置 |
|-----|------|------|---------|
| CMC | 加密 | 333/天 | secrets/coinmarketcap_api_key.txt |
| Alpha Vantage | 股票 | 500/天 | secrets/alphavantage_api_key.txt |
| Twelve Data | 技术指标 | 800/天 | secrets/twelvedata_api_key.txt |
| Massive | 股票/加密日线 | 免费层 | secrets/massive_api_key.txt |
| CoinGecko | 加密社区 | 免费·无Key | 采集器内置 |
| alt.me | 恐慌贪婪 | 免费·无Key | 采集器内置 |
| Brave | Web搜索 | 2000/月 | secrets/brave_api_key.txt |
| Exa | Web搜索 | 1000/月 | secrets/exa_api_key.txt |
| Binance MCP | 加密衍生品 | MCP内置 | — |
| 金十 MCP | 快讯/日历/XAU | MCP内置 | — |
| TradingView MCP | 图表/指标/DMI | MCP内置 | — |
| FinanceKit MCP | 股票/期权 | MCP内置 | — |

## 采集器

| 脚本 | 功能 |
|------|------|
| `hermes/scripts/multi_source_collector.py` | CMC + AV + TD + Massive |
| `hermes/scripts/coingecko_collector.py` | CG社区情绪+热门+板块+恐慌贪婪 |
| `hermes/scripts/sentiment_search.py` | Brave→Exa→DDGS 搜索情绪 |

## 引擎 v2.1

`hermes/scripts/multi_model_engine.py`

关键函数:
- `run_all_models(data)` → 12模型结果列表
- `merge_directions(results)` → 合并方向+置信+动作
- `check_event_ban(data, symbol)` → 五重检查
- `call_grok_validation(symbol, merged, results, price, data)` → Grok交叉验证

置信映射: 0.5→3/5, 0.7→4/5, 0.85→5/5
Grok分歧→强制B等待·action降级·confidence_5上限3
