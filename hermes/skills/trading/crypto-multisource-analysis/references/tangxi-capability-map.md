# 棠溪实时分析能力接入图 v1.2

> 来源：2026-06-27 本机 Hermes 能力审计 + 2026-06-28/29 驾驶舱补强。用于 `crypto-multisource-analysis` / `tradingview-indicator-analysis` 在分析 BTC/ETH/XAU/外汇/股票时知道"哪些源可用、哪些优先、哪些只是候选"。

## 1. 已确认可用的核心能力

### Hermes 运行态

- Hermes Agent，可用。
- Gateway 正在运行。
- Telegram 已配置，home channel 可用但历史上有过发送超时，关键推送需做可靠性兜底。
- 当前 active profile: `default`。
- 技能总量约 294 个，其中 trading 约 26 个。

### 当前主模型/辅助模型

- 当前默认：`deepseek-v4-pro`。
- 可用模型组：OpenRouter、DeepSeek、xAI OAuth、OpenCode Go。
- **fallback_providers 已配置**（2026-06-28确认）：4层降级链可用。
- x_search 已配置 `grok-4.20-non-reasoning`，90s timeout，2 retries，xAI OAuth 已登录。适合快扫 X/新闻情绪。

## 2. 搜索 / 网页能力

### 已启用插件

- `web-brave-free`、`web-exa`、`web-firecrawl`、`web-tavily`、`web-ddgs`

### 降级链状态

- 搜索链：`Brave → Exa → Tavily → DDGS` ✅
- X/新闻：`x_search（grok-4.20，优先）→ web_search → browser` ✅

## 3. TradingView / 图表能力

MCP `tradingview` 已启用并测试通过，约 78 个工具。

## 4. 加密 API / 金融 API

### CoinGecko Pro API Key（2026-06-28 发现 · 2026-06-29 确认为驾驶舱必调步骤）

- **Key**: `CG-tkuaqHxNbpTQ92HgpvEc4QXY`
- **Header**: `x-cg-pro-api-key`
- **限速**: 500 req/min
- **状态**: ✅ 已灌注4个脚本，驾驶舱Step 4强制执行
- **分析时必须调用**: cg_categories(板块轮动) + cg_coin_detail(流动性评分) + cg_exchange_volumes(交易所量验证)
- **非Orion场景完全可用**；Orion CG交叉验证偶有400（端点兼容性），不影响主流程

### Binance MCP · FinanceKit MCP · Jin10 MCP

已启用，分析时标准步骤调用。

## 5. 社交 / 情绪 / 新闻能力

### X Search（2026-06-28 已确认可用 · 2026-06-29 标记为驾驶舱Step 6必调）

- Toolset `x_search` 已启用，模型 `grok-4.20-non-reasoning`，90s timeout，2 retries。
- **驾驶舱Step 6强制执行**，不可用时降级 web_search 并标注「web源·非X实时」。
- 写入分析卡交叉验证行：方向 + 强度 + 大V观点。

### 恐惧贪婪

`api.alternative.me/fng/`，已验证可用。

## 6. 多市场驾驶舱路由

`pipeline_router.py` 自动按资产类别确定管线步骤：

| 市场 | 步骤数 | 执行步骤 |
|------|:--:|------|
| 🪙 加密 | 14 | tv→binance→cg_pro→macro→jin10→poly→dune→deribit→x_sent→fg→cvd→depth→card |
| 🥇 贵金属 | 8 | tv→macro→jin10→cot→x_sent→cvd→gold_macro→card |
| 💱 外汇 | 7 | tv→macro→jin10→cot→x_sent→forex_rate→card |
| 📈 股票 | 8 | tv→macro→jin10→cot→x_sent→fmp→options_chain→card |
| 📊 期货 | 6 | tv→macro→jin10→cot→x_sent→card |
| 📋 期权 | 3 | tv→options_chain→card |

**铁律**：分析前先跑 `route_pipeline(symbol, "full")`，按返回列表逐一执行，缺一步不算完成。

## 7. 分析任务默认接入矩阵（v4.4+ → v9.4）

| 数据源 | 状态 | 备注 |
|---|---|---|
| TV 主指标(行动格v2) | ✅ MCP | Step 2 |
| TV 副指标(Volume) | ✅ MCP | 仅加密 |
| Binance(价/OI/Funding/Taker) | ✅ MCP | Step 3 · 加密专属 |
| **CoinGecko Pro** | ✅ 强制执行 | Step 4 · cg_categories/coin_detail/exchange_volumes |
| 宏观(SPX/VIX/DXY) | ✅ FinanceKit MCP | Step 4 |
| 金十日历 | ✅ MCP | Step 5 |
| Polymarket | ✅ Gamma API | Step 5b |
| ETF Flow | ❌ Cloudflare封禁 | 已删除 · Dune+稳定币替代 |
| Dune 链上 | ✅ 40req/min | Step 5d |
| COT 持仓 | ✅ CFTC免费 | Step 5e · 非加密 |
| Deribit 期权 | ✅ 公开API | Step 5f · 加密 |
| **x_search X情绪** | ✅ 强制执行 | Step 6 · grok-4.20 |
| 恐惧贪婪 | ✅ API | Step 7 |
| CVD订单流 | ✅ MCP | Step 2内 |
| Depth挂单墙 | ✅ MCP | 加密专属 |
| 稳定币供应 | ✅ DeFiLlama | cron每2h |
| QLib 30因子 | ✅ 纯Python | cron每30min |
| 清算压力 | ✅ Binance API | cron每30min |
| 告警去重 | ✅ MD5 | 已注入4脚本 |
| IP-ban回退链 | ✅ 3级 | 代理→直连→缓存 |
