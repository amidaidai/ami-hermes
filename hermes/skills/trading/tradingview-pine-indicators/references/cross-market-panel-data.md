# Cross-Market Panel Data Sources & Adaptive Content

How to adapt a single Pine Script indicator's action panel for crypto, metals, forex, stocks, and indices — using only free-account-compatible data sources.

## Free-Account Cross-Market Data via TVC

TradingView's `TVC:` prefix provides index data accessible on free accounts. These are the most useful for cross-market context:

```pine
// DXY (Dollar Index) — for metals and forex
float dxyClose = request.security("TVC:DXY", timeframe.period, close)
float dxyPrev = request.security("TVC:DXY", timeframe.period, close[1])
float dxyChange = not na(dxyClose) and not na(dxyPrev) ? dxyClose - dxyPrev : 0.0
string dxyDirection = dxyChange > 0.05 ? "DXY↑利空" : dxyChange < -0.05 ? "DXY↓利多" : "DXY→中性"

// VIX (Volatility Index) — for stocks, indices, and metals (risk sentiment)
float vixClose = request.security("TVC:VIX", timeframe.period, close)
string vixText = not na(vixClose) ? "VIX " + str.tostring(vixClose, "#.0") + (vixClose > 25 ? "高波" : vixClose < 15 ? "低波" : "中波") : ""
```

### Cost
Each `request.security()` call adds to the 40-call limit. DXY requires 2 calls (current + previous for change calculation). VIX requires 1 call. Total budget impact: +3 calls.

### What does NOT work on free accounts
- `request.funding_rate()` — only for perpetual futures symbols; spot pairs return `na`
- Economic calendar / news data — no Pine Script API
- Market breadth (advance/decline) — requires specific exchange tickers
- Real yields (TIPS) — no data source in Pine

## Market-Adaptive Panel Content

Each market type has different professional priorities. The action panel should show different data per market:

### Crypto (BTC/ETH)
| Priority | Data | Source | Panel Row |
|---|---|---|---|
| #1 | CVD (order flow) | Built-in calculation | 结构 + 确认 |
| #2 | Sweep count + Magnet | ICTLevel array | 结构 |
| #3 | KillZone | Session time check | 确认 |
| #4 | SMT (BTC/ETH) | request.security same exchange | 核对 |
| #5 | EMA + VWAP | Built-in | 结构 |

### Metals (XAU/USD)
| Priority | Data | Source | Panel Row |
|---|---|---|---|
| #1 | DXY direction | request.security TVC:DXY | 结构 |
| #2 | ICT sweep events | ICTLevel array | 结构 + 确认 |
| #3 | Volume Profile (VA) | SVP engine | 结构 |
| #4 | KillZone / session overlap | Session time check | 确认 |
| #5 | VIX (risk sentiment) | request.security TVC:VIX | 结构 (optional) |

### Forex (EUR/USD, GBP/USD)
| Priority | Data | Source | Panel Row |
|---|---|---|---|
| #1 | Session overlap (London/NY) | isLondon and isNY | Header + 确认 |
| #2 | VWAP position | Built-in | 结构 |
| #3 | DXY direction | request.security TVC:DXY | 结构 |
| #4 | CVD sessions | Built-in | 确认 |
| #5 | SMT (EUR/GBP) | request.security | 核对 |

### Stocks/Indices (ES, NQ, SPX)
| Priority | Data | Source | Panel Row |
|---|---|---|---|
| #1 | VIX level | request.security TVC:VIX | 结构 |
| #2 | Volume Profile (VA) | SVP engine | 结构 |
| #3 | VWAP position | Built-in | 结构 + 确认 |
| #4 | Volume (high/low) | Built-in | 结构 |
| #5 | EMA trend | Built-in | 结构 |

## Session Overlap Detection

Simple but valuable for forex and metals traders:

```pine
bool londonNyOverlap = isLondon and isNY
bool asiaLondonOverlap = isAsia and isLondon
string sessionOverlapText = londonNyOverlap ? "伦纽重叠" : asiaLondonOverlap ? "亚伦重叠" : ""
```

Display in header line: `看VWAP+会话 ⚡伦纽重叠`
Display in confirmation row: append to KillZone text.

## R:R and Magnet Direction Implementation

```pine
// Magnet direction: ↑ = target above, ↓ = target below
string magnetDir = not na(magnetNearestPrice) ? (magnetNearestPrice > close ? "↑" : "↓") : ""
string magnetTargetText = not na(magnetNearestPrice) ? magnetDir + str.tostring(magnetNearestPrice, format.mintick) : ""

// R:R = reward / risk
float rrRatio = na
if not na(replayPlanPrice) and not na(replayInvalidPrice) and not na(magnetNearestPrice)
    float riskDist = math.abs(replayPlanPrice - replayInvalidPrice)
    float rewardDist = math.abs(magnetNearestPrice - replayPlanPrice)
    rrRatio := riskDist > 0 ? rewardDist / riskDist : na
string rrText = not na(rrRatio) ? str.tostring(rrRatio, "#.1") + "R" : ""
```

### Panel display patterns
- **结论行**: `· 标↑67200` (target direction + price)
- **执行行**: `多 65420 · 止63800 · 标↑67200(2.1R) · 失效破VWAP` (entry + stop + target + R:R)
- **风险行**: `R:R 2.1R · 磁78↑` (R:R + Magnet score with direction)

## User Preferences (this indicator class)

- **NO BOS/CHoCH** — user explicitly rejected (ICT purist approach)
- **NO Order Blocks / FVG** — user explicitly rejected
- **NO Premium/Discount zones** — user explicitly rejected
- **NO EQH/EQL** — user explicitly rejected
- **Action panel is PRIMARY decision tool** — must be comprehensive and reliable
- **Free account compatible** — no premium-only features
- **TradingView white theme** — `#0F0F0F` and near-black colors ARE visible
- **All labels `size.small`** — not `size.tiny`
- **Label format**: `周三 高: 2345.6` (day name + 高/低 + colon + price, no duplication)
- **Chinese language** for all labels and panel text
