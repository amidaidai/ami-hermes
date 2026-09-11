# 多资产覆盖矩阵 v9.0

最后更新：2026-06-29

## 逐资产能力

### 加密（BTC/ETH/SOL...） 98%
| 维度 | 来源 | 状态 |
|------|------|------|
| 技术面 | TV MCP: SVP+Volume+OI, 4h/1h/15m | ✅ |
| 价格 | Binance + CG Pro + TV 三重验证 | ✅ |
| 衍生品 | Binance: OI/费率/Taker/LS/多空比 | ✅ |
| 全局排名 | CG Pro: Top10/板块轮动 | ✅ |
| 链上数据 | Dune: BTC流/CEX净流 | ✅ |
| ETF Flow | SoSoValue 免费抓取 | ✅ |
| 期权OI | Deribit 公开API: C/P比+MaxPain | ✅ |
| 情绪 | x_search + 恐惧贪婪 + Polymarket | ✅ |
| 日历 | 金十 | ✅ |
| 订单流 | CVD/吸收/FVG/OB/Delta | ✅ |
| 执行 | Binance | ✅ |

### 贵金属（XAU/XAG） 85%
| 维度 | 来源 | 状态 |
|------|------|------|
| 技术面 | TV MCP: SVP | ✅ |
| 价格 | 金十 + Yahoo GC=F/MGC=F | ✅ |
| 宏观背景 | DXY/EURUSD/US10Y/TIP/TLT/GLD/GDX | ✅ |
| COT持仓 | CFTC 投机/商业净多空 | ✅ 新增 |
| 金市新闻 | Cnyes + 金十 | ✅ |
| 日历 | 金十（利率决议/CPI/NFP） | ✅ |
| 情绪 | x_search (XAU/gold) | ⚠️ 可用非标准 |
| 资金流 | GLD ETF 持仓 | ❌ |
| 执行 | 无 | ❌ |

### 股票（AAPL/TSLA/NVDA...） 85%
| 维度 | 来源 | 状态 |
|------|------|------|
| 技术面 | TV MCP: SVP | ✅ |
| 价格 | FMP + Yahoo + Alpha Vantage + Twelve Data | ✅ |
| 基本面 | FMP: P/E/MC/财报 | ✅ |
| 期权链 | FinanceKit: OI/IV/Greeks | ✅ |
| COT股指 | CFTC 投机/杠杆基金净多空 | ✅ 新增 |
| 宏观 | SPX/VIX/NDX | ✅ |
| 财报日历 | FinanceKit earnings_calendar | ✅ |
| 板块 | FMP sectors-performance | ⚠️ 未标准化 |
| 执行 | 无 | ❌ |

### 外汇（EURUSD/GBPJPY...） 75%
| 维度 | 来源 | 状态 |
|------|------|------|
| 技术面 | TV MCP: SVP | ✅ |
| 价格 | Yahoo/FMP/Jin10 | ✅ |
| COT持仓 | CFTC 杠杆基金/资管净多空 | ✅ 新增 |
| 日历 | 金十 | ✅ |
| 宏观 | DXY/US10Y/利差 | ⚠️ 部分 |
| 情绪 | x_search | ⚠️ 可用非标准 |
| 执行 | 无 | ❌ |

### 期货（ES/NQ/CL/GC...） 70%
| 维度 | 来源 | 状态 |
|------|------|------|
| 技术面 | TV MCP: SVP | ✅ |
| 价格 | Yahoo/FMP | ✅ |
| COT持仓 | CFTC 投机/商业净多空 | ✅ 新增 |
| 宏观 | SPX/VIX | ✅ |
| 日历 | 金十 | ✅ |
| 执行 | 无 | ❌ |

### 期权 60%
| 维度 | 来源 | 状态 |
|------|------|------|
| 图表 | TV MCP | ✅ |
| 加密期权 | Deribit: OI/C-P/MaxPain | ✅ 新增 |
| 股票期权 | FinanceKit: chain/IV/Greeks | ✅ |
| 波动率 | VIX + FinanceKit IV | ✅ |
| 加密到期 | Deribit 到期日OI集中度 | ✅ 新增 |
| 执行 | 无 | ❌ |

## 总体覆盖

```
加密:     █████████░ 98%
贵金属:   ████████░░ 85%
股票:     ████████░░ 85%
外汇:     ███████░░░ 75%
期货:     ███████░░░ 70%
期权:     ██████░░░░ 60%
──────── ─────────────────
加权综合: ████████░░ 84%
```

## 剩余缺口（均需付费）
- 全所衍生品对比：CoinGlass $29/mo
- 实时鲸鱼追踪：Glassnode/CryptoQuant/Santiment $几百/mo
- DeFi TVL：DeFiLlama 免费但非紧急，随时可接
- GLD ETF 持仓：Yahoo 已有 GLD 价格，持仓变化可加但价值有限
