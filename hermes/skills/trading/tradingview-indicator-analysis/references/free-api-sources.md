# 免费/低价 API 数据源状态

> **本文件是「状态表」，会过期。** 唯一权威测量手段是脚本，不是这张表：
> ```bash
> cd "D:/Hermes agent" && python scripts/maintenance/api_source_health_probe.py
> ```
> 复跑前的最后更新：**2026-09-13**（22 个数据源逐条真实调用）。
>
> ⚠️ 历史教训：本文件 2026-06-18 版曾记录「FMP ❌403 / Tavily ❌0结果 / Firecrawl ❌欠费 /
> AnySearch ❌不通」，到 2026-09-13 复测时**前三项全部已恢复可用**。状态表不标注测量时间
> 和复现命令，就会变成误导下一位读者的假事实。

## 一、2026-09-13 实测：可用（18）

| API | Key 来源 | 提供 | 采集器 |
|-----|----------|------|--------|
| **Binance 公开行情** | 无需 | 加密价格·K线·衍生品 | MCP `binance` + 脚本 |
| **Binance 私有账户** | `binance.json` | 余额·持仓·下单 | MCP `binance` |
| **CoinMarketCap** | `coinmarketcap_api_key.txt` | 加密行情·市占·恐慌贪婪 | multi_source_collector |
| **CoinGecko** | `coingecko_api_key.txt`（可无） | 社区情绪·热门·板块·汇率 | coingecko_collector |
| **Alpha Vantage** | `alphavantage_api_key.txt` | 股票报价·外汇 | multi_source_collector |
| **Twelve Data** | `twelvedata_api_key.txt` | 报价·RSI·MACD | multi_source_collector |
| **FMP** | `fmp_api_key.txt` | 全球宏观·财报·财报日历 | multi_source_collector |
| **Massive（股票/加密日线）** | `massive_api_key.txt` | 日线 OHLCV | multi_source_collector |
| **Tushare（部分接口）** | `tushare_token.txt` | A股日线/分钟·指数·中国宏观基础 | multi_source_collector |
| **Dune** | `dune_api_key.txt` | 链上流量·稳定币 | dune_collector |
| **Polymarket** | `polymarket_address.txt` | 预测市场 | 脚本/技能 |
| **Tavily** | `tavily_api_key.txt` | AI 搜索 | Hermes web 插件 |
| **Brave Search** | `brave_api_key.txt` | 网页搜索（2000/月） | sentiment_search |
| **Exa** | `exa_api_key.txt` | 语义搜索 | Hermes web 插件 |
| **Firecrawl** | `firecrawl_api_key.txt` | 网页抓取 | Hermes browser 插件 |
| **Metaso** | `metaso_api_key.txt` | 中文搜索 | 脚本 |
| **金十 MCP** | `jin10_token.txt` + `jin10_mcp.cmd` | 快讯·日历·XAU 报价 | MCP `jin10` |
| **x_search** | OAuth（非 API key） | X 情绪 | 工具层 |

**Tushare 是分接口授权的**：本项目实测可用 7/23 —— `daily` / `stk_mins` / `index_daily` /
`cn_gdp` / `cn_cpi` / `shibor` / `shibor_lpr`。北向资金、融资融券、龙虎榜、可转债、基金净值、
港股/美股财报、外汇日线、期货日线等 **16 个接口需 2000+ 积分**。

## 二、受套餐/额度限制（2）

| API | 证据 | 影响 |
|-----|------|------|
| **Coinglass** | `HTTP 200` 但 body `code=401 "Upgrade plan"` | 需付费套餐；**系统当前未引用该源**，无实际影响 |
| **Massive 期货快照** | `You are not entitled to this data` | 需付费套餐。**期货资产类目前只有 massive + macro 两个采集器**，故该接口受限 = 期货报价缺源（卡面走「待采集/—」） |

> ⚠️ 判据：**HTTP 200 不等于可用**。必须看 body 里的 `code`/`msg`。

## 三、未配置（1）

| API | 状态 |
|-----|------|
| **OANDA** | `oanda_token.txt` 是说明性占位符（`PLACEHOLDER_REPLACE_WITH_REAL_TOKEN`），**从未配置过真 token**。XAU 五周期 OHLCV 因此走 TwelveData。 |

> 守卫已落地：`scripts/credential_store.py` 会识别占位符/注释/中文说明并把它们判为「未配置」，
> 避免被当成真凭据去发请求再静默失败。填真 token 即自动启用。

## 四、已清理（2）—— 2026-09-13 删除

| API | 删除时的证据 | 处置 |
|-----|------|------|
| **Felo** | 端点只返回 `{"Hello":"World"}` 占位响应（路径已失效） | 🗑 密钥文件已删 |
| **AnySearch** | DNS 不通 / 代理下 SSL EOF | 🗑 密钥文件已删 |

两者**系统从未引用**，删除不影响任何链路。原值不保留；如需恢复请到服务商后台重新签发。
记录：`hermes/maintenance-logs/removed-keys-20260913.txt`。

## 五、搜索优先级

```
Brave (2000/月) → Exa (1000/月) → Tavily
→ 金十快讯 + CoinGecko 社区情绪兜底
```

## 六、Key 文件位置

全部在 `D:/Hermes agent/hermes/secrets/`。密钥清单与用途见 `api-keys-index.md`。
**不要**把任何凭据值写进技能或文档。
