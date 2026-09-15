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
| **清算堆积带（24h）** | **`scripts/coinglass_web.py`** | **免 key 网页端握手；仅 `Binance_BTCUSDT` 匿名可读（其它品种 `code=40000`）；强度是相对刻度不是 USD；缓存 `data/coinglass_liq.json`，卡面短句 `liquidation_band_text()`** |
| **逐笔强平流（真实成交）** | **`scripts/liquidation_flow.py`** | **OKX 公共接口免 key：`uly=<COIN>-USDT` 必填、单页硬上限 100 笔、往旧翻页用 `after=<最旧ts>`；缓存 `data/liquidation_flow.json`，卡面短句 `flow_text()`；刷新走 `scripts/liquidation_refresh.py`（双源、cron `清算双源刷新`）** |

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
- **清算口径三条铁律**：① CoinGlass 热图强度是**相对刻度**，不得当美元爆仓额引用；② OKX 名义按 `sz × ctVal × bkPx` **估算**（ctVal 随品种变：BTC 0.01 / ETH 0.1 / SOL 1，取自 `/api/v5/public/instruments`），写卡面必须带「估算」；③ 交易所单页只回 100 笔、只保留最近约 24h → **覆盖不足时标签必须写真实窗口**，不把 4 小时的数据标成「近24h」。
- **bootstrap 陷阱**：`fetched_at` 不在 `source_health.TIMESTAMP_KEYS`（只认 `updated_epoch/updated_at/ts/time/updated`）里 —— 自建缓存只写 `fetched_at` 会被数据新鲜度看门狗判成「无显式时间戳」而误报，落盘时要同时写 `updated_epoch`。
- **别再用已下线的强平接口**：币安 `fapi/v1/allForceOrders` 返错误页、Bybit `/v5/market/liquidation` 返 404、Bybit WS `liquidation.<SYM>` 主题回 `handler not found`（2026-09-15 实测）→ 免费可用的**规模口径只剩 OKX 逐笔**（`uly=<COIN>-USDT`，单页上限 100 笔需翻页），本轮采集器 `scripts/liquidation_flow.py`。
- **币安 WS 强平流三个坑**：① 路径已改为 `wss://fstream.binance.com/market/ws/!forceOrder@arr`（旧路径 `/ws/…` 仍能握手但**永不推送**，静默空转② 官方自 2021-04-27 起只推 **≤1 条/秒快照**，不是全量逐笔 → **不得并入规模统计**（系统性低估比不给数字更糟），只能作「币安侧最近发生过强平」的存在性提示；③ `fstream` 直连超时需走代理，普通 HTTP 代理可隧道 WS（实测 `bookTicker` 12s 17,947 条）。采集器 `scripts/ws_liquidation_listener.py` + 保活 `liquidation_ws_watchdog.py`。
- **免费多所逐笔的边界（2026-09-15 全部实测，别重复找）**：Bitfinex WS `liq` 与 `liquidations` 频道均回 `10300 channel: unknown`（已下线）；HTX `market.<sym>.liquidation_orders` 走代理被 `1003` 断开、直连握手超时；币安只推 ≤1 条/秒快照；**Hyperliquid 无公开全市场清算流**（官方 `WsTrade` 定义里没有 liquidation 字段，清算只出现在**用户级** `userFills`/`userEvents`；全市场需自建 gRPC 节点或付费第三方）。→ **结论：免费公开的第二所逐笔清算源不存在，规模口径只能挂 OKX 一所**；多所规模需求出现时只能走付费（CoinGlass/TapeSurf 档位）。
