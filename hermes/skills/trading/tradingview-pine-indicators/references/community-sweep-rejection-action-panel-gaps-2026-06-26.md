# Community Audit: Sweep Rejection, Action Panel Gaps, Pre-Trade Checklist (2026-06-26)

Session context: user asked for full multi-community audit (X, Reddit, TradingView, GitHub) comparing the indicator against high-quality community indicators. User explicitly said EQH/EQL and Premium/Discount are NOT wanted, but asked for other improvement suggestions. User also asked to evaluate the action panel as a decision tool for entry/trading.

---

## 1. Sweep Rejection Confirmation — #1 Community Gap

### Community Consensus (5+ independent sources)
Every high-quality community sweep indicator distinguishes between a **true sweep** (rejection) and a **breakout**:

| Source | Standard |
|---|---|
| Quantum Algo (Liquidity Sweep Filter) | Wick through + close back inside = sweep; close outside = breakout |
| JOAT (Sweep and Cluster) | 5-condition strict sweep: real pivot + clean wick + close back inside + cluster confirmation |
| FluxCharts | "Price goes beyond level and shoots back = sweep. Stays = breakout." |
| Zeiierman | Sweep = targeted move through key level to trigger stops, then snaps back |
| Alchemy Markets | "False break of structure followed by sharp reversal" |

### Our Current Code (GAP)
```pine
// CURRENT — counts ALL price crossings as sweeps (including breakouts)
isSwept := lvl.isHigh ? (high > lvl.price) : (low < lvl.price)
```

This means a genuine breakout (price closes above the high and continues) is marked as "swept" — producing false sweep signals, inflating `ictSweptCount`, and corrupting the Magnet Score.

### Implementation Status: ALL P0 ITEMS COMPLETED (2026-06-26)

### ✅ Sweep rejection confirmation — IMPLEMENTED
```pine
isSwept := lvl.isHigh ? (high > lvl.price and close < lvl.price) : (low < lvl.price and close > lvl.price)
```

### ✅ R:R + target price in action panel — IMPLEMENTED
- 执行行: `多 65420 · 止63800 · 标↑67200(2.1R) · 失效破VWAP`
- 风险行: `R:R 2.1R · 磁78↑`
- 结论行: `· 标↑67200`

### ✅ Magnet direction arrow — IMPLEMENTED
`magnetDir = magnetNearestPrice > close ? "↑" : "↓"`

### ✅ DXY direction (metals/forex) — IMPLEMENTED
`request.security("TVC:DXY")` — free account compatible

### ✅ VIX (stocks/metals) — IMPLEMENTED
`request.security("TVC:VIX")` — free account compatible

### ✅ Session overlap — IMPLEMENTED
`londonNyOverlap = isLondon and isNY` → `⚡伦纽重叠`

### ⏳ OTE 62-79% zone — NOT YET IMPLEMENTED (P1, pending user approval)

---

## Recommended Fix (ORIGINAL — kept for reference)
```pine
// TRUE SWEEP — wick through + close back inside (rejection)
bool sweepHighRejection = high > lvl.price and close < lvl.price
bool sweepLowRejection = low < lvl.price and close > lvl.price
isSwept := lvl.isHigh ? sweepHighRejection : sweepLowRejection
```

Optionally add a "breakout" state (price closes beyond level = not a sweep, just a break):
```pine
bool breakoutHigh = close > lvl.price  // not a sweep, continuation
bool breakoutLow = close < lvl.price   // not a sweep, continuation
```

### Impact
This is the single highest-impact signal quality improvement. It affects:
- `ictSweptCount` / `ictActiveCount` (used in action panel 结构 line)
- Magnet Score (uses swept/unswept classification)
- Sweep event detection (`sweptHighNow`, `sweptLowReclaimed`)
- Action panel 确认 line (`actionIctText`)

---

## 2. Action Panel Missing R:R + Target Price

### Community Pre-Trade Checklist Standard
From 6 community sources (KMF, SMC Trade Checklist, TradingFinder ICT, TFlab, Reddit ICT Plan, ICT PD Array Matrix):

| Step | Community Standard | Our Panel | Status |
|---|---|---|---|
| 1. Bias/Direction | HTF trend confirmation | `15m↑1h↑4h→1D↑` | ✅ |
| 2. Liquidity sweep | Recent high/low taken | `扫2存5` | ✅ |
| 3. Entry zone | PD Array / OB / FVG / OTE | `POC 65420等承接` | ✅ |
| 4. Stop loss | Structural level, tight | `止损1.5A` | ⚠️ ATR multiple only, no price |
| 5. **R:R ratio** | **≥ 1:1.5 minimum** | **✗ MISSING** | 🔴 |
| 6. **Target price** | **Next liquidity pool / TP1/TP2** | **✗ MISSING** | 🔴 |
| 7. Risk % | ≤ 1% per trade | Data Window only | ✅ (CD system) |
| 8. Session | London/NY preferred | `⚡伦敦开盘` | ✅ |
| 9. CVD confirmation | Order flow confirms | `CVD日买盘` | ✅ |
| 10. SMT confirmation | Correlated instrument | `SMT⚠` | ✅ |

### Recommended Panel Changes

**执行行 — add target + R:R:**
```
// CURRENT
执行：多 POC 65420等承接 · 多失效:破VWAP 63800

// RECOMMENDED
执行：多 65420 · 止损63800 · 目标67200(2.1R) · 失效:破VWAP
```

**风险行 — add R:R and Magnet direction:**
```
// CURRENT
风险：止损1.5A · 位3/确5/延0 · 磁78

// RECOMMENDED
风险：止损1.5A(63800) · R:R 2.1 · 位3/确5/延0 · 磁78↑
```

**Magnet direction arrow**: `↑` = nearest target above price, `↓` = nearest target below.

### Implementation notes
- `replayStopDistance` variable already exists (price distance to stop) — display it alongside ATR multiple
- Target price = `magnetNearestPrice` (already computed) or next liquidity pool
- R:R = `(magnetNearestPrice - entryPrice) / (entryPrice - stopPrice)` — requires entry price variable
- These are display-only changes; all underlying variables already exist

---

## 3. OTE 62-79% Retracement Zone

### Community Source
TradingFinder ICT, ICT mentorship, LuxAlgo — the Optimal Trade Entry is ICT's most cited entry model.

### Definition
- Draw Fibonacci from recent swing high → swing low
- **62% - 79% retracement = OTE zone** (70.5% = sweet spot)
- Price entering this zone = high-probability entry in trend direction

### Our Indicator
Not implemented. We have VAH/VAL/POC/VWAP as entry zones but not the Fibonacci-based OTE.

### Potential implementation
- Detect recent swing high/low using `ta.pivothigh()` / `ta.pivotlow()`
- Draw 62%-79% zone as a shaded band
- Action panel: show "OTE 62-79%" when price is in the zone
- This is a standalone feature, not a fix — requires user approval before implementing

---

## 4. Community Feature Comparison Matrix

| Feature | LuxAlgo 25.6K | Trading IQ 4.3K | JOAT Sweep | Liquidity Magnet | **Our indicator** |
|---|---|---|---|---|---|
| KillZone | ✅ | ✅ | ❌ | ❌ | ✅ |
| Liquidity sweep | ✅ | ✅ | ✅ (strict 5-cond) | ✅ | ✅ (needs rejection filter) |
| **Sweep rejection confirm** | ✅ | ✅ | ✅ (5 conditions) | ✅ | **❌** |
| CVD session | ❌ | ❌ | ❌ | ❌ | ✅ (unique) |
| SMT divergence | ❌ | ❌ | ❌ | ❌ | ✅ 7 pairs (unique) |
| VWAP weekly/monthly | ❌ | ❌ | ❌ | ❌ | ✅ (unique) |
| Volume Profile | ❌ | ❌ | ❌ | ❌ | ✅ (unique) |
| EMA cloud | ❌ | ❌ | ❌ | ❌ | ✅ (unique) |
| Magnet Score 0-100 | ❌ | ❌ | ❌ | ✅ (3-factor) | ✅ (3-factor, unique) |
| Action panel 6-row | ❌ | ❌ | ❌ | ❌ | ✅ (unique) |
| Data Window CD output | ❌ | ❌ | ❌ | ❌ | ✅ (unique) |
| Multi-market adaptive | ❌ | ❌ | ❌ | ❌ | ✅ (unique) |
| OTE 62-79% zone | ❌ | ✅ | ❌ | ❌ | ❌ |
| R:R in panel | ❌ | ✅ | ❌ | ❌ | ❌ |
| Target price in panel | ❌ | ✅ | ❌ | ❌ | ❌ |
| EQH/EQL | ✅ | ✅ | ❌ | ❌ | ❌ (user rejected) |
| Premium/Discount | ✅ | ✅ | ❌ | ❌ | ❌ (user rejected) |
| BOS/CHoCH | ✅ | ✅ | ❌ | ❌ | ❌ (user rejected) |
| OB/FVG | ✅ | ✅ | ❌ | ❌ | ❌ (user rejected) |

### Verdict
Our indicator has 7 unique features not found in any community indicator. The main gaps are: (1) sweep rejection confirmation [P0], (2) R:R + target in action panel [P0], (3) OTE zone [P1].

---

## 5. Community Sources Consulted

| Platform | Source | Key takeaway |
|---|---|---|
| Reddit r/InnerCircleTraders | "ICT indicator requests/ideas" thread | Community wants clean sweep detection with rejection confirmation |
| TradingView | Liquidity Sweep Filter (AlgoAlpha) | Sweep = wick through + close back inside |
| TradingView | Sweep and Cluster (JOAT) | 5-condition strict sweep + cluster confirmation |
| TradingView | ICT Concepts (LuxAlgo) | Non-repainting, killzones, inducements — 25.6K likes |
| TradingView | Checklist Dashboard (Eamda) | ICT/SMC structured checklist as on-chart table |
| Scribd | SMC Trade Entry Checklist (Aug 2025) | 10-step checklist: bias→liquidity→CHOCH→OB→entry→SL/TP→risk→session→news→emotions |
| KMF Journal | Pre-Trade Checklist 10 Rules | R:R ≥ 1:1.5, position sizing, news filter, emotional check |
| TradingFinder | ICT Entry Checklist | 4-step: liquidity grab→MSS→premium/discount→PD array |
| TFlab | ICT Entry Checklist | Liquidity→MSS→entry→SL/TP |
| InnerCircleTrader.net | ICT SMT Divergence | Standard SMT pairs: BTC/ETH, ES/NQ, EUR/GBP, XAU/XAG, BTC/DXY |
| InnerCircleTrader.net | ICT PD Array Matrix | Premium/discount + 8 institutional trigger tools |
| YouTube | PineTrades Liquidity Sweep Filter | Buy-side/sell-side liquidity zones + volume profile confirmation |
| YouTube | Justin Bennett Sweep Reversal | Sweep + acceptance + 2.5R-4R targets using structure |
| GitHub | joshyattridge/smart-money-concepts | Python SMC library: OB, FVG, BOS, CHoCH, liquidity, swing highs/lows |
