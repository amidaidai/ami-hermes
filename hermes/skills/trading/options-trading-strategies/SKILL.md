---
name: options-trading-strategies
description: "期权交易策略 — 期权链数据分析、Greeks(Delta/Gamma/Vega/Theta)、隐含波动率、多腿策略(垂直/对角/铁鹰/蝶式)、Gamma暴露(GEX)、IV百分位。对接 financekit MCP + Yahoo Finance"
version: 1.0.0
author: 安禾
tags: [options, options-trading, greeks, IV, implied-volatility, GEX, hedging, strategies]
---

# 期权交易策略 — Options Trading

股票和ETF期权的链数据、Greeks分析、策略构建。基于 financekit MCP + yfinance。

## 核心数据源

| 数据 | 来源 | 命令 |
|------|------|------|
| 期权链 | financekit MCP | `options_chain(symbol="SPY", expiration="2026-07-17")` |
| 实时行情 | financekit MCP | `stock_quote(symbol="AAPL")` |
| 技术分析 | financekit MCP | `technical_analysis(symbol="SPY")` |
| 历史波动率 | yfinance | `yfinance.download()` |
| 看跌/看涨比 | web search | `web_search("SPX put/call ratio")` |

## 期权分析流程

### ① 获取链数据
```python
# 通过 financekit MCP
# 获取最近到期期权链
result = mcp_financekit_options_chain(symbol="SPY")
# 返回: strike, call_bid/ask/vol/OI/IV, put_bid/ask/vol/OI/IV
```

### ② Greeks 解读

| Greek | 含义 | 典型值 | 用法 |
|-------|------|--------|------|
| **Delta** | 标的价格变动1，期权变动Δ | Call 0-1, Put -1-0 | 方向暴露，做多=买Call/卖Put |
| **Gamma** | Delta变动率 | ATM最高(0.05-0.15) | Gamma越高→Delta变化越快 |
| **Vega** | IV变动1%，期权变动V | ATM最长(0.10-0.40) | IV预期变化时用Vega对冲 |
| **Theta** | 时间衰减/天 | ATM最短(-0.05 to -0.20) | 卖方策略吃Theta |

### ③ IV 分析
- **IV百分位**：当前IV在历史上排名（>70=贵，<30=便宜）
- **IV偏斜**：OTM Put vs OTM Call 的IV差异（恐慌溢价）
- **IV期限结构**：近月 vs 远月 IV 曲线（Contango/Backwardation）

### ④ Gamma 暴露 (GEX)
- **正GEX**：做市商在现货上涨时买更多（加速上涨）
- **负GEX**：做市商在现货下跌时卖更多（加速下跌）
- **零GEX**：中性

```python
# GEX 计算近似
GEX ≈ sum(OI × Gamma × 100)  # 所有未平仓合约
# 正GEX → 市场稳定（做市商反向对冲）
# 负GEX → 市场波动（做市商同向追单）
```

## 常见策略

| 策略 | 构成 | 看什么 | R:R特征 |
|------|------|--------|---------|
| **垂直价差** | 买卖同一到期不同行权 | 方向+有限风险 | R 固定，≤1:2 典型 |
| **日历价差** | 买远月卖近月同价 | 时间+IV分歧 | Theta 正，Vega 风险 |
| **铁鹰** | 双垂直价差 | 区间震荡 | 高胜率(60-80%)，低赔率 |
| **蝶式** | 三腿对称 | 窄区间目标 | 极高胜率，极低赔率 |
| **对角价差** | 不同月+不同价 | 方向+时间 | 灵活但复杂 |
| **跨式/勒式** | Put+Call 同月 | 大波动(财报) | 双方向，Vega敏感 |
| **备兑开仓** | 持股+卖Call | 降低持有成本 | 有限upside，下行保护 |

## 集成到分析

### 期权环境段（可注入分析卡）
```
期权环境：
SPY IV 18.5% · IV百分位 45% · 偏斜 Put+2.3%
GEX +1.2B · 最大痛点 545 · Put/Call 1.15
下周期权到期 6/28 · 最大集中位 550
```

### 财报前后策略
1. **财报前**：买跨式（预期波动暴增）
2. **财报后**：卖铁鹰（IV坍塌，收割溢价）
3. **IV偏斜变陡**：Put侧贵→恐慌，Bull Put Spread

## 陷阱
- IV 百分位≠IV 方向 — 高百分位可继续高
- 期权链数据不同源有 5-15min 延迟（free tier）
- 周末Theta照扣（3天衰减在周五收盘已反映）
- 财报前后IV可能涨 50-100%，买跨式要算 IV crash 后的盈亏
- 小盘股期权价差大，滑点可能吃光利润
