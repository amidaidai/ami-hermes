---
name: stock-multi-factor-screener
description: "股票多因子扫描器 — 技术面(趋势/动量/波动率) + 基本面(PE/PEG/营收) + 情绪面(期权/PCR/做空比)相结合。对接 financekit MCP + yfinance"
version: 1.0.0
author: 安禾
tags: [stocks, screener, technical-analysis, fundamental, SEPA, momentum, scanning]
---

# 股票多因子扫描器 — Stock Multi-Factor Screener

多维度股票筛选：技术面趋势 + 基本面估值 + 情绪面信号。

## 数据源

| 数据 | 来源 | 函数 |
|------|------|------|
| 技术指标 | financekit MCP | `technical_analysis(symbol)` |
| 基本面 | financekit MCP | `company_info(symbol)`, `stock_quote(symbol)` |
| K线 | yfinance | `price_history(symbol, period="6mo")` |
| 多股报价 | financekit MCP | `multi_quote(symbols)` |
| 板块轮动 | financekit MCP | `sector_rotation(period="3mo")` |

## 三因子评分系统

### 技术面因子（40分）

| 因子 | 条件 | 得分 | 数据源 |
|------|------|------|--------|
| **趋势** | 价格 > EMA50 > EMA200 | 0-15 | `tech_analysis → SMA` |
| **动量** | RSI 40-70 + MACD 正向 | 0-10 | RSI + MACD |
| **波动率** | ATR 正常/收缩 | 0-5 | Bollinger带宽 |
| **成交量** | 日量 > 20日均量 | 0-5 | Volume对比 |
| **形态** | VCP/杯柄/Bull Flag | 0-5 | 模式识别 |

### 基本面因子（35分）

| 因子 | 评分 | 数据源 |
|------|------|--------|
| PE 合理（行业均值±20%） | 0-10 | `company_info → PE` |
| 营收增长 > 10% YoY | 0-10 | `company_info → revenue` |
| 利润率 改善/稳定 | 0-8 | `company_info → profit margins` |
| 市值 > 10亿（流动性） | 0-7 | `stock_quote → market cap` |

### 情绪面因子（25分）

| 因子 | 评分 | 数据源 |
|------|------|--------|
| 期权PCR 较低 | 0-8 | web_search |
| 分析师评级 买入为主 | 0-9 | `earnings-preview / estimate-analysis` |
| 做空比例适中 | 0-8 | web_search |
| 板块轮动 资金流入 | 0-5 | `sector_rotation` |

## 快速筛选模板

### ① SEPA 强势股扫描
```python
# 条件：季报增长 + 趋势 + VCP 形态
for symbol in ["NVDA", "AMD", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "AVGO"]:
    ta = technical_analysis(symbol)
    info = company_info(symbol)
    score = trend_score(ta) + growth_score(info) + pattern_score(ta)
    print(f"{symbol}: {score}/100")
```

### ② 均值回归扫描
```python
# 条件：RSI < 30 + 价格在 Bollinger 下轨 + 基本面不差
for symbol in watchlist:
    ta = technical_analysis(symbol)
    if ta.rsi < 30 and ta.price < ta.bb_lower:
        print(f"{symbol}: RSI {ta.rsi:.0f} → 超卖")
```

### ③ 板块轮动跟随
```python
rotation = sector_rotation(period="3mo")
# 找出最近 1 个月最强板块
top_sectors = sorted(rotation, key=lambda x: x.return_1m, reverse=True)[:5]
print(f"强板块: {[s.sector for s in top_sectors]}")
```

## 快速评分表

```markdown
| 股票 | 技术 | 基本面 | 情绪 | 总分 | 结论 |
|------|------|--------|------|------|------|
| NVDA | 35 | 30 | 20 | 85 | ✅ 强势 |
| AMD  | 28 | 25 | 15 | 68 | ⚠ 关注 |
| TSLA | 20 | 15 | 25 | 60 | ⚠ 分歧 |
| INTC | 10 | 20 | 5  | 35 | ❌ 回避 |
```

## 集成到棠溪卡片格式

```
◷ Wed · 股票扫描 · 日线
③ 全市场：S&P +0.8% · VIX 14.2
强势板块：半导体 +2.1% · AI +1.5%
最佳候选：NVDA 85分 · AVGO 82分
基本面：PE 35× · 增长45% · 利润率55%
技术：EMA50>EMA200 · RSI 62 · 杯柄形态
→ ↑做多 等待VCP突破 止损 EMA50
```

## 集成现有技能
- `sepa-strategy` → SEPA/VCP 深度分析
- `earnings-preview` → 财报预期
- `earnings-recap` → 财报回顾
- `stock-correlation` → 相关股票
- `professional-finance-data` → 暗池/期权流
- `sector-rotation` → 板块资金流向
