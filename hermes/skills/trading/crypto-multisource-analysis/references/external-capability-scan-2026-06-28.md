# 外部加密能力市场扫描 v1.0

> 2026-06-28 | 来源：cryptoskills.dev + browse.sh + 联网搜索
> 用途：crypto-multisource-analysis 在评估"还有什么能力可补"时的参考

---

## 1. CryptoSkills.dev（97 技能）

平台定位：AI Agent 可读的区块链协议/工具技能文件，覆盖 Solana/EVM/跨链。

### 对我们有用的

| 技能 | 类型 | 价值 | 费用 |
|------|------|------|------|
| **MetEngine** | 聪明钱分析 | 钱包评分/内幕检测/资金流/仓位分析，63端点 | 按次付费 USDC |
| **Pyth Network** | 预言机 | 400ms 实时价格 + 置信区间 + EMA | **免费** |
| **Hyperliquid** | 永续 DEX | 自有 L1，50x 杠杆，API 无 Key | **免费查询** |
| **GMX V2** | 永续 DEX | Arbitrum/Avalanche，100x，异步执行 | **免费查询** |
| **Vertex** | 跨链 DEX | 统一保证金，多链订单簿 | **免费查询** |
| **Ranger Finance** | 路由聚合 | Solana 永续聚合，最优执行 | 需 Key |
| **Polymarket** (已有) | 预测市场 | 已通过 polymarket_bridge.py 接入 | **免费** |

### 与我们无关的
DeFi 借贷（Aave/Compound/Curve）、NFT（Metaplex）、安全审计（Certora/Slither）、前端工具（Privy）等。

---

## 2. browse.sh（425 浏览器自动化技能）

平台定位：消费级网站浏览器自动化（旅游/零售/政府/房产）。

**结论：对加密驾驶舱无直接帮助。** 全部是订机票酒店购物类技能。

---

## 3. 全网免费/付费 API 对比

### 已具备（无需新增）

| 来源 | 数据 | 接入方式 |
|------|------|----------|
| Binance MCP | 价/OI/费率/多空比/Taker（单所） | MCP |
| CoinGecko Pro | 排名/板块/流动性/交易所量 | 4脚本已灌注 |
| FinanceKit MCP | 加密价/Top10/trending/SPX/VIX | MCP |
| Jin10 MCP | 财经日历/快讯 | MCP |
| x_search | X 实时情绪（grok-4.20） | plugin |
| Polymarket | 事件概率 | polymarket_bridge.py |
| 恐惧贪婪 | alternative.me | web_extract |

### 免费可接入（推荐）

| 来源 | 数据 | 接入方式 | 优先 |
|------|------|----------|------|
| **SoSoValue** | BTC ETF 日净流入/流出 | web_extract 抓公开页 | ⭐⭐⭐ |
| **Dune Analytics** | 交易所流入流出/稳定币/鲸鱼 | 免费 API 40req/min，需注册 | ⭐⭐ |
| **Pyth Hermes** | 400ms 实时价格 + 置信区间 | 免费 REST/SSE | ⭐（已有 Binance+TV，冗余） |

### 付费（不接入）

| 来源 | 最便宜 | 为什么不用 |
|------|--------|-----------|
| CoinGlass | $29/月 | 全所 OI/爆仓/ETF 数据很好但全付费 |
| MetEngine | 按次 USDC | 聪明钱追踪但需付钱 |
| Nansen | $几百/月 | 链上深度分析 |
| CryptoQuant | 联系销售 | 机构级链上 |
| Glassnode | $29-$999/月 | API 需单独购买 |

---

## 4. SoSoValue ETF Flow 接入要点

```
URL: https://m.sosovalue.com/assets/etf/us-btc-spot
方法: web_extract
提取: 日净流入/流出(USD)、累计净流、各 ETF 明细
写入: 分析卡「ETF Flow」行
阈值: 净流入 > +$100M = 机构看多 / 净流出 > -$100M = 警惕
```

---

## 5. Dune Analytics 接入要点

```
免费方案: 40 req/min, SQL 查询
需要: 注册免费账号 → 创建 API key
现成查询:
  - 交易所 BTC 余额变化（流入=抛压）
  - 稳定币 USDT/USDC 供应量变化
  - 鲸鱼钱包大额转账
写入: 分析卡「链上」行
```
