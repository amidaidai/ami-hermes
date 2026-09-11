# Cross-Market Timeframe Community Guide (2026-06-26)

Session-specific reference for the v10.4 turn: user asked "其他市场的呢？我这个时间周期是不是有问题？" — querying whether their 5m/15m/1h/4h/1D timeframe stack is correct per market, and requesting multi-channel community research. Distinct from `indicator-svp-v10-timeframe-role-funding-2026-06-26.md` (which covers role detection + funding) and `indicator-svp-v10-optimization-2026-06-26.md` (which covers bug fixes + Magnet Score). **This file covers only: (1) per-market timeframe recommendations sourced from professional community consensus, and (2) the `f_auto_htf` gradient bug fix that differentiated 4h from 1h HTF context.**

## 1. Community-sourced Per-Market Timeframe Stack

The user's 5m/15m/1h/4h/1D combination was validated against 10+ community sources across markets. The consensus:

| Market | Execution (LTF) | Structure (MTF) | Background (HTF) | Source |
|---|---|---|---|---|
| **Crypto BTC/ETH perp** | **5m / 15m** | 1h / 4h | 1D | CoinFlip 2026, LiteFinance, Reddit r/Daytrading, Learning Crypto |
| **Metals XAU** | **5m** | 15m / 1h | 4h / 1D | The Secret Mindset (990K subs), NYC Servers, LiteFinance, ThinkMarkets 2026 |
| **Forex EURUSD/GBPUSD** | **5m / 15m** | 1h / 4h | 1D | BKTraders 2026, FXPro, EUR/USD SMC Guide (Scribd), "The Best Forex Trading Timeframe 2026" YT |
| **Stocks / Index ES/NQ** | **5m** | 15m / 1h | 4h / 1D | Steady Turtle Trading, Master The Market (YT), Scott Taylor NQ 2026 |
| **Commodity futures** | **5m / 15m** | 1h / 4h | 1D | Optimus Futures Community, general SMC consensus |

User confirmed: crypto uses 15m, metals use 5m — both match community recommendations exactly. Forex/stocks adoption of 5m as the entry timeframe is the community default for day-trading these markets.

### The ICT 3-tier hierarchy (canonical pattern)
Every community source converged on this 3-tier pattern:
- **HTF (Weekly → Daily)** = Map / Bias Timeframe — "what to trade"
- **MTF (4H → 1H)** = Structure / Setup Timeframe — "context for the setup"
- **LTF (15m / 5m / 1m)** = Execution Timeframe — "when to enter"

Sources: SmartMoneyICT "ICT Timeframes for Position, Swing & Scalping", SMC And ICT (Facebook "Proper Timeframe Alignment"), Arcanum Fx (Instagram scalper vs day vs swing hierarchy), PropTradingVibes 2026, Investopedia/TradeCiety/Bookmap.

## 2. `f_auto_htf` Gradient Bug Fix (Class-Level Lesson)

### Bug
The HTF filter ladder returned the same HTF for two adjacent chart timeframes:

```pine
// BEFORE — 4h and 1h both return 1D
f_auto_htf() =>
    int sec = timeframe.in_seconds(timeframe.period)
    sec <= 60 ? "15" : sec <= 300 ? "60" : sec <= 900 ? "240" : sec <= 3600 ? "D" : sec <= 14400 ? "D" : "W"
```

When the user switched from 1h to 4h, the HTF filter still showed the *same* 1D bias — there was no perceptible change in HTF context despite the chart timeframe doubling. This contributed to the user's complaint that "切到1h又是另外一个了,要是切到4小时又是另外一个方案.总感觉好像有点奇怪."

### Fix
Each chart tier should step UP exactly one HTF tier, never duplicating an adjacent tier:

```pine
// AFTER — 4h→W, 1D→M (each tier sees a distinct higher context)
f_auto_htf() =>
    int sec = timeframe.in_seconds(timeframe.period)
    sec <= 60 ? "15" : sec <= 300 ? "60" : sec <= 900 ? "240" : sec <= 3600 ? "D" : sec <= 14400 ? "W" : "M"
```

| Chart TF | Role | BEFORE → HTF | AFTER → HTF | Improvement |
|---|---|---|---|---|
| 1m | 执行 | 15m | 15m | unchanged |
| 5m | 执行 | 1h | 1h | unchanged ✓ |
| 15m | 执行 | 4h | 4h | unchanged ✓ |
| 1h | 结构 | 1D | 1D | unchanged ✓ |
| **4h** | 结构 | **1D** (same as 1h!) | **1W** | distinct weekly context |
| **1D+** | 背景 | **1W** | **1M** | monthly long-term bias |

### Class-Level Principle
**An auto-HTF ladder should never return the same HTF for two adjacent chart tiers.** Each step UP in chart timeframe should step UP in HTF filter as well — otherwise the trader perceives no change in higher-context bias when switching timeframes, which feels broken.

When designing `f_auto_htf()`-style functions, audit the full ladder: enumerate each interval the user might select (1s, 5s, 15s, 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 1D, 1W, 1M) and verify each gets a DISTINCT HTF result (or a deliberate same-as-previous fallback for ultra-fast scalping where there is no higher tier). 1D→1M is the right cap for long-term bias — 1W→1W duplication is a common mistake when copying fx-style code to multi-market indicators.

### When to revisit
If the user switches to 30m as their execution TF (some scalpers), the breakpoint `900` (15m ceiling) in `tfRole` and `f_auto_htf` should both shift to `1800` (30m ceiling). The two functions must stay in sync — `tfRole` defines the role label, `f_auto_htf` defines the HTF bias source.

## 3. focusHint `isPerp` Split

Small but useful refinement: the header focusHint should differentiate perpetual vs spot crypto, since the perp funding rate is the most cited perp-only order-flow signal and was added as a separate display field.

```pine
// BEFORE — single crypto focusHint
string focusHint = marketCrypto ? "看CVD+扫点" : marketMetal ? "看DXY+ICT" : ...

// AFTER — perpetual differentiation
string focusHint = marketCrypto ? (isPerp ? "看CVD+资金" : "看CVD+扫点") : marketMetal ? "看DXY+ICT" : ...
```

Traders on perpetual charts see `看CVD+资金` in the header, signaling the funding rate row is now active. Traders on crypto spot see the original `看CVD+扫点`. This pattern of "add a market-subtype qualifier to the focusHint when a new market-subtype-specific data source exists" generalizes — e.g., if a future session adds COT (Commitment of Traders) data for futures-only instruments, focusHint should split `marketFutures ? "看COT+ICT" : "看ICT+结构"`.

## 4. Multi-Channel Community Audit Methodology (Reusable)

This session used a structured multi-source search pattern that produced robust consensus on a workflow question (timeframe recommendations). It's reusable for future "is our approach right?" questions:

1. **Identify the question class.** Timeframe recommendations = a `professional recommendation` class question, not a documentation lookup. Search for content where professional traders explicitly state their stack.
2. **Search 5+ independent channels in parallel** via `web_search` (single batched turn):
   - YouTube (educators with >100K subs): The Secret Mindset (990K), BKTraders (123K), Scott Taylor, Master The Market (31K)
   - Broker education hubs: ThinkMarkets, LiteFinance, NYC Servers, FXPro, OANDA
   - Community forums: Reddit r/Daytrading, Optimus Futures Community
   - TradingView idea pages: chart posts by reputable authors
   - Prop firm educators: PropTradingVibes 2026, FXIFY
3. **Extract the consensus tier structure.** If 4+ independent sources agree on the same LTF/MTF/HTF stack for a market, that's community consensus. Document the stack with attribution.
4. **Compare to current implementation.** Flag any divergence as either (a) a bug to fix, or (b) an explicit user preference to preserve with a note explaining why.
5. **Apply only the class-level patterns** to the indicator. Don't hardcode user-specific market/TF pairs into the script — let the user choose via inputs and use the community stack as defaults.

This methodology is distinct from the `firecrawl-community-audit-workflow.md` reference (which covers single-page scraping extraction). This pattern targets *consensus across channels* on a workflow question.

## 5. Community Sources Consulted

Per-market timeframe recommendations:
- **Crypto**: CoinFlip.trade "Best Crypto Trading Timeframes 2026", LiteFinance "10 Best Crypto For Day Trading 2026", Reddit r/Daytrading "What chart time frames do you trade daytrade/scalp crypto BEST on", Learning Crypto YT "What's the Best Timeframe for Crypto Trading"
- **Metals**: The Secret Mindset YT "STOP Trading Gold With Broken Setups! Use This Simple XAUUSD Strategy Instead" (990K subs), NYC Servers "Gold XAUUSD Trading Strategy Guide", LiteFinance "Gold Trading Strategies 2026", ThinkMarkets "Gold trading strategy 2026", David_Perk TradingView "Powerful Gold Strategy for 2026"
- **Forex**: BKTraders YT "4-Hour Forex Strategy 2026 Update" (Kathy Lien, 20+ yrs experience), FXPro "EUR/GBP Trading Complete 2026 Guide", EUR/USD SMC Trading Strategy Guide (Scribd), "The Best Forex Trading Timeframes to Trade in 2026" YT, InstaForex EUR/USD analysis
- **Stocks/Index**: Steady Turtle Trading "6 Proven Day Trading Strategies That Actually Work (ES & NQ Futures)" (Medium), Master The Market YT "Best Time Frames for Day Trading Explained", Scott Taylor YT "Simple NQ Futures Strategy for 2026", Optimus Futures Community "What time frames do you trade and why?"
- **General MTF workflow**: SmartMoneyICT, SMC And ICT (Facebook "Proper Timeframe Alignment"), Arcanum Fx (Instagram scalper/day/swing hierarchy), PropTradingVibes 2026 "Multiple Timeframe Analysis", Investopedia, TradeCiety, Bookmap

## 6. Verification

```bash
# Confirm f_auto_htf is the FIXED version (each tier distinct)
grep 'sec <= 14400 ? "W" : "M"' file.txt  # should find 1 match
grep 'sec <= 14400 ? "D" : "W"' file.txt  # should find 0 matches (old buggy version)

# Confirm focusHint isPerp split
grep -c 'isPerp ? "看CVD+资金"' file.txt  # should be 1
```

Final file: 2,642 lines, 161,393 bytes. plot=31, request.security=9, alertcondition=13. No multiline expression issues. All previous fixes (sweep rejection, R:R, Magnet direction, DXY merge, barstate.isconfirmed) preserved.