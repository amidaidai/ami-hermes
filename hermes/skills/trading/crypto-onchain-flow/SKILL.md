---
name: crypto-onchain-flow
description: "Crypto On-Chain Flow Analysis — 交易所流入/流出、鲸鱼追踪、稳定币流动、资金费率、链上活动、聪明钱追踪。补充 Binance MCP + CoinGecko + CryptoQuant 风格链上指标"
version: 1.0.0
author: 安禾
tags: [crypto, onchain, whale, exchange-flow, stablecoin, funding-rate, smart-money, flow]
---

# 链上流量分析 — On-Chain Flow

追踪加密市场的链上资金动向——交易所净流、鲸鱼地址、稳定币增发/赎回、资金费率、链上活跃度。

## 核心数据源

| 数据 | 来源 | 说明 |
|------|------|------|
| 资金费率 | Binance MCP | `get_funding_rate_history(symbol="BTCUSDT", limit=5)` |
| 多空比 | Binance MCP | `get_long_short_ratio(symbol="BTCUSDT")` + `get_global_long_short()` |
| OI 变化 | Binance MCP | `get_open_interest_history(symbol="BTCUSDT")` |
| Taker 量 | Binance MCP | `get_taker_volume(symbol="BTCUSDT")` |
| **大额挂单墙** | **`depth_wall.py`** | **`scripts/depth_wall.py BTCUSDT` — 免费Binance depth端点，零依赖。已验证可用。返回支撑墙+压力墙+OI四象限体制。** |
| BTC 价格 | Binance MCP | `get_price(symbol="BTCUSDT")` |
| 恐惧贪婪 | web_extract | `alternative.me/api/crypto/fear-and-greed-index/latest` |
| 交易所净流 | web_extract | `coinglass.com/ExchangeFlow` 或 `cryptoquant.com` |
| 稳定币总市值 | web_search | `web_search("USDT USDC market cap 2026")` |

## 链上分析框架

### ① 交易所流量 (Exchange Flows)

```python
# 交易所 BTC 净流入 → 卖出压力
# 交易所 BTC 净流出 → 提币/囤积 (看涨信号)
# 稳定币入所 → 买入准备 (看涨)
# 稳定币出所 → 离场 (看跌)
```

**解读**：
| 信号 | 含义 | 置信 |
|------|------|------|
| BTC大量入交易所 | 抛售准备 → 看跌 | 中 (50-70%) |
| BTC大量出交易所 | 囤积 → 看涨 | 中 (50-70%) |
| USDT/USDC大量入交易所 | 买入准备 → 看涨 | 高 (70-90%) |
| USDT/USDC大量出交易所 | 离场 → 看跌 | 中 (50-70%) |

### ② 资金费率 (Funding Rate)

**Binance MCP 获取**：
```python
funding = mcp_binance_get_funding_rate_history(symbol="BTCUSDT", limit=5)
# 正值 → 多头付费 (看涨过热)
# 负值 → 空头付费 (看跌过热)
# 极值 → 反转信号
```

| 费率 | 解读 |
|------|------|
| > 0.01% | 多头拥挤 → 短线回调风险 |
| 0.001% ~ 0.01% | 健康 |
| < -0.01% | 空头拥挤 → 短线反弹风险 |
| 持续负值 | 长期看空情绪 |

**CI 信号**：`费率反转` → BTC 专属回测，正期望

### ③ OI 趋势 (Open Interest)

```python
oi = mcp_binance_get_open_interest_history(symbol="BTCUSDT")
# OI ↑ 价格 ↑ → 新资金进 (健康上涨)
# OI ↑ 价格 ↓ → 新空头建仓 (看跌)
# OI ↓ 价格 ↑ → 空头平仓 (轧空)
# OI ↓ 价格 ↓ → 多头平仓 (看跌)
```

### ④ Taker 买卖比

```python
taker = mcp_binance_get_taker_volume(symbol="BTCUSDT")
# 主动买 > 主动卖 → 多方主导
# 主动卖 > 主动买 → 空方主导
# CIS: Taker背离 → 价格和taker方向不一致 → 趋势可能反转
```

### ⑤ 鲸鱼追踪 (Whale Tracking)

```python
# 大户多空比 → 鲸鱼情绪
ls = mcp_binance_get_long_short_ratio(symbol="BTCUSDT")
# > 1.5 = 大户极度看多 (可能反转)
# < 0.5 = 大户极度看空 (可能反弹)
```

### ⑥ 稳定币指标

| 指标 | 含义 |
|------|------|
| USDT Dominance ↑ | 避险模式 → 资金逃离山寨 |
| USDT Dominance ↓ | 风险偏好 → 资金入山寨 |
| USDT总市值 ↑ | 新法币入场 → 看涨 |
| USDT总市值 ↓ | 资金出逃 → 看跌 |

## 一键分析模板

```python
# 链上快速扫描
funding = get_funding_rate_history()
oi = get_open_interest_history()
taker = get_taker_volume()
ls = get_long_short_ratio()
fg = "恐惧贪婪指数 (web)"

# 判断市场情绪
if funding >= 0.01:   print("过热 — 多头拥挤")
if funding <= -0.01:  print("恐惧 — 空头拥挤")
if taker.ratio > 1.2: print("主动买多 — 看涨动量")
if taker.ratio < 0.8: print("主动卖空 — 看跌动量")
```

## 注入分析卡

```
② 市场背景：
链上：费率 0.005% · OI +2% · Taker 1.15
LS 大户 1.2 · 全网 0.95
F&G 22 恐惧 · USDT.D 5.8% ↑
→ 解读：空头拥挤+恐惧 → 潜在反弹
```

## 陷阱
- 交易所流量数据不同源差异大（CryptoQuant vs CoinGlass vs Nansen）
- 资金费率极端值常见于行情末端，但可能维持数天
- BTC 入交易所不一定立刻卖出，可能只是转入做市/借贷
- 稳定币数据有 6-24h 延迟（链上确认时间）
