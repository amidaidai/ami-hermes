# 多市场管线适用性（2026-06-28 用户确认）

## 核心原则
本 skill 的 8 步管线专为加密设计。用户问"所有市场都是吗"→确认不是。

## 各市场适用性

| 市场 | 全8步 | 副驾驶(Volume Aggregated) | 说明 |
|:----|:-----:|:-------------------------|:-----|
| 加密(BTC/ETH/SOL) | ✅ ✅ | ✅ 有效，isCryptoA=true | 全管线执行 |
| 贵金属(XAUUSD) | ❌ | ❌ 罢工显示"非加密品种" | 只读主指标行动格 v2 |
| 外汇(EURUSD等) | ❌ | ❌ 罢工 | 只读主指标+VWAP+ICT会话 |
| 股票/指数(AAPL/SPX) | ❌ | ❌ 罢工 | 只读主指标+成交量+财报 |

## 加密分析必做项（同主 SKILL.md）
- TV MCP：4h→1h→15m 三周期 + 主副指标 pine_tables + lines + labels + study_values + 截图full
- Binance MCP：价格/OI/多空比/费率/主动买卖
- CoinGecko：24h/7d变动+市值+排名
- 金十MCP：本周财经日历+闪讯
- 恐惧贪婪：alternative.me/fng/
- X/Web情绪：web_search 回退并标注「web源·非X实时」
- Binance深度：可选

## 非加密市场限制
- 副指标内部 `isCryptoA = syminfo.type=='crypto'`，挂黄金/外汇/股指时行动格显示"非加密品种/请看主指标判定"
- OI/多空比/费率 = ❌ 不可用于非加密
- 恐惧贪婪 = ❌ 只限加密情绪
- CoinGecko = ❌ 只限加密
