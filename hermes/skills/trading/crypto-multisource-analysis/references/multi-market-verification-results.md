# 多资产管线验证 v1.0

> 2026-06-30 审计修复验证

## 目的

确认 pipeline_router 为5大类资产返回正确的步骤列表，且各市场专属步骤正确插入。

## 验证方法

```python
from pipeline_router import pipeline_summary
print(pipeline_summary(symbol, "full"))
```

## 验证结果

| 市场 | 标的 | 步数 | 专属步骤 | 正确路由 |
|:---|:---:|:---:|:---|---|
| 🪙 加密 | BTCUSDT | 10 | binance/cg_pro/cvd/depth | ✅ |
| 🥇 黄金 | XAUUSD | 8 | gold_macro | ✅ |
| 💱 外汇 | EURUSD | 7 | forex_rate | ✅ |
| 📈 股票 | AAPL | 8 | fmp/options_chain | ✅ |
| 📊 期货 | ES | 6 | — | ✅ |

## 注意

- 股票管线有2条数据路径：A股用 Stock-API MCP，美股用 yfinance 回退
- 外汇/期权管线的专属步骤（forex_rate/options_chain）仅有路由定义，无实战执行代码
- 黄金管线的 gold_macro仅定义了路由，实战依赖 gold-api + 金十 + Yahoo 代理
