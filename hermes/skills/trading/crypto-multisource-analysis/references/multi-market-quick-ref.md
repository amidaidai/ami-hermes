# 多市场驾驶舱执行速查 v1.0

> 2026-06-29 · 6类资产快速参考卡。分析前跑 `pipeline_router.route_pipeline(symbol, "full")`。

## 快速对照

| 市场 | 品种 | router step数 | 第一步 |
|------|------|:--:|---|
| 🪙 加密 | BTCUSDT ETHUSDT SOLUSDT | **14** | tv→binance→cg_pro→macro→jin10→poly→dune→deribit→x_sent→fg→cvd→depth→card |
| 🥇 贵金属 | XAUUSD XAGUSD | **8** | tv→macro→jin10→cot→x_sent→cvd→gold_macro→card |
| 💱 外汇 | EURUSD GBPJPY | **7** | tv→macro→jin10→cot→x_sent→forex_rate→card |
| 📈 股票 | AAPL TSLA NVDA | **8** | tv→macro→jin10→cot→x_sent→fmp→options_chain→card |
| 📊 期货 | ES NQ CL | **6** | tv→macro→jin10→cot→x_sent→card |
| 📋 期权 | CALL PUT SPX | **3** | tv→options_chain→card |

## 执行铁律

1. **先跑router** → 拿到步骤列表
2. **逐步骤执行** → 不跳步，不跳过数据采集
3. **所有步骤跑完再出卡** → card是最后一步，不是第3步
4. **验证清单全打勾再输出**
