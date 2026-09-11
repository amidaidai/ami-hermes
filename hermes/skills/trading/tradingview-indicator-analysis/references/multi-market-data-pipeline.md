# 多市场数据管线差异（2026-06-28 用户确认）

## 核心原则
不同市场的可用数据源不同，不能把加密的完整衍生品管线套用到其他市场。

## 市场管线对照表

| 市场 | 全量7步 | 适用源 | 禁用源 | 替代源 |
|:----|:-------:|:-------|:-------|:-------|
| 加密(BTC/ETH/SOL) | ✅ | TV双指标、OI、多空比、费率、主动买卖、Depth、CoinGecko、金十、恐惧贪婪、X情绪 | 无 | — |
| 贵金属(XAUUSD) | ❌ | TV主指标(SVP行动格)、金十行情/日历、DXY/US10Y/SPX宏观 | ❌ OI ❌多空比❌费率❌CoinGecko❌恐惧贪婪 | gold-api现货+Yahoo GC=F期货 |
| 外汇(EURUSD等) | ❌ | TV主指标(SVP+VWAP+ICT会话)、金十日历、央行利率/US10Y | ❌全部加密衍生品❌副驾驶(罢工) | TV主指标判定+财经日历 |
| 股票/指数(AAPL/SPX) | ❌ | TV主指标、财报日历、成交量/VIX | ❌大部分加密衍生品❌副驾驶(罢工) | FinanceKit股票报价+财报季 |

## 副驾驶门控（Volume Aggregated）
- 副指标内部有 `isCryptoA = syminfo.type=='crypto'` 判断
- **加密**：副驾驶全程有效、必采
- **黄金/外汇/股指**：跳过副指标采集，只读主指标行动格 v2（结论/方向/进场/止损/目标/磁吸↑↓）

## 加密全量管线（7步）
1. TV MCP：4h→1h→15m 三周期主副指标+截图
2. Binance MCP：价格/OI/多空比/费率/主动买卖
3. CoinGecko：24h/7d变动+市值+排名
4. 金十MCP：本周财经日历+闪讯
5. 恐惧贪婪指数（alternative.me/fng/）
6. X/Web情绪验证（web_search回退）
7. Binance深度（可选）

## 贵金属管线（精简）
1. TV MCP：主指标行动格+4h/15m关键位+截图
2. 金十：XAU行情+本周日历
3. 黄金宏观：DXY/US10Y/SPX/GC=F（可选）
4. gold-api.com：XAU现货价
5. 注意：❌无OI ❌无多空比 ❌无Funding ❌无Volume Aggregated副驾驶

## 外汇管线（更精简）
1. TV MCP：主指标VWAP/SVP/ICT会话+截图
2. 金十日历：利率决议/PMI/非农
3. 注意：❌副指标不工作（内部 isCryptoA 判false后罢工），只依赖主指标

## 股票/指数管线
1. TV MCP：主指标SVP/VWAP+成交量+截图
2. FinanceKit：股票报价/PE/市值
3. 财报日历（季度）：重大数据前后30min禁做
4. VIX/SPX宏观联动（可选）
5. 注意：❌副指标不工作 ❌无加密衍生品数据
