# API 密钥清单

> 存放目录：`D:/Hermes agent/hermes/secrets/`（**不纳入备份、不写入技能正文**）。
> 状态列的实际值请以脚本为准，不必信任本表：
> ```bash
> cd "D:/Hermes agent" && python scripts/maintenance/api_source_health_probe.py
> ```
> 本表最后核对：**2026-09-13**。

## 行情/宏观（分析链路使用）

| 密钥文件 | API | 用途 | 实测状态 |
|---|---|---|---|
| `binance.json` | Binance（U本位+现货） | 行情·余额·持仓 | ✅ 公开+私有鉴权均通过 |
| `coinmarketcap_api_key.txt` | CoinMarketCap | 加密行情·市占·恐慌贪婪 | ✅ |
| `coingecko_api_key.txt` | CoinGecko | 社区情绪·热门·板块 | ✅ |
| `fmp_api_key.txt` | Financial Modeling Prep | 全球宏观·财报·财报日历 | ✅ |
| `alphavantage_api_key.txt` | Alpha Vantage | 股票报价·外汇 | ✅ |
| `twelvedata_api_key.txt` | Twelve Data | 报价·RSI/MACD·XAU 五周期备源 | ✅ |
| `massive_api_key.txt` | Massive | 股票/加密日线 | ✅ 日线可用；**期货快照需付费套餐** |
| `tushare_token.txt` | Tushare | A股·中国宏观 | ⚠️ 分接口：7/23 可用，其余需 2000+ 积分 |
| `dune_api_key.txt` | Dune Analytics | 链上流量·稳定币 | ✅ |
| `jin10_token.txt` + `jin10_mcp.cmd` | 金十数据（MCP） | 快讯·日历·XAU 报价 | ✅ |
| `coinglass_api_key.txt` | Coinglass | 加密衍生品聚合 | ⚠️ `HTTP 200 + code 401 Upgrade plan`；系统未引用 |
| `oanda_token.txt` + `oanda_account_id.txt` | OANDA | XAU 五周期 OHLCV 首选源 | ❌ **占位符，从未配置真 token** |
| `polymarket_address.txt` / `polymarket_api_key.txt` | Polymarket | 预测市场 | ✅ 公开读可用 |

## 搜索/抓取

| 密钥文件 | API | 用途 | 实测状态 |
|---|---|---|---|
| `brave_api_key.txt` | Brave Search | 网页搜索（2000/月） | ✅ |
| `tavily_api_key.txt` | Tavily | AI 搜索 | ✅（2026-09 复测恢复） |
| `exa_api_key.txt` | Exa | 语义搜索 | ✅ |
| `firecrawl_api_key.txt` | Firecrawl | 网页抓取 | ✅（2026-09 复测恢复） |
| `metaso_api_key.txt` | Metaso | 中文搜索 | ✅（2026-09 复测恢复） |
| ~~`anysearch_api_key.txt`~~ | AnySearch | 聚合搜索 | 🗑 **2026-09-13 已删除**（DNS 不通 / SSL EOF，系统从未引用） |
| ~~`felo_api_key.txt`~~ | Felo | AI 研究搜索 | 🗑 **2026-09-13 已删除**（端点只剩 `{"Hello":"World"}` 占位，路径失效） |

> 删除记录：`hermes/maintenance-logs/removed-keys-20260913.txt`。原值不保留，
> 如需恢复须到服务商后台重新签发。
| `search_apis.json` | 聚合备份 | 上述搜索 key 的 JSON 备份 | 结构化文件，非单值凭据 |

## 未配置（对应开源项目依赖，非本系统缺口）

| 名称 | 说明 |
|---|---|
| `TWINGLY_API_KEY` | FinanceMCP 可选新闻源，未配置 → 该项目新闻能力不可用 |
| `QVERIS_API_KEY` | FinanceMCP 动态能力路由，未配置 |

## 搜索优先级

```
Brave (2000/月) → Exa (1000/月) → Tavily → 金十快讯 + CoinGecko 情绪兜底
```

## 环境变量注入（可选）

凭据既可放 `secrets/` 文件，也可用环境变量注入（环境变量优先）：
`FMP_API_KEY` · `DUNE_API_KEY` · `OANDA_TOKEN` · `OANDA_ACCOUNT_ID` · `BRAVE_API_KEY` · `TAVILY_API_KEY` · `EXA_API_KEY` · `FIRECRAWL_API_KEY`

> 占位符保护：`scripts/credential_store.py` 会把「整份只有注释」「含 PLACEHOLDER/TODO/YOUR_ 标记」
> 「有效行是中文说明」的文件判为**未配置**并返回空串，避免拿说明文字去发请求后静默失败。
> 中文注释 + 真 key 的文件、以及 `.json` 结构化凭据不受影响（有回归测试锁死）。
