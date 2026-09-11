# Indicator SVP v10 — Timeframe Role Adaptation + Perpetual Funding Rate (2026-06-26)

Session-specific reference for the v10.3 turn that added (1) timeframe role detection and per-role action panel adaptation, and (2) perpetual futures funding rate approximation — PLUS the **v10.3.1 follow-up** that added the `tfRoleRec` market-recommended-timeframe footer to the headerLine and fixed the stale `f_auto_htf()` gradient. The pre-existing references for today's earlier work (`anti-repaint-sweep-dxy-efficiency`, `community-sweep-rejection-action-panel-gaps`, `indicator-svp-v10-optimization`) cover the barstate.isconfirmed sweep guard, DXY tuple-bundle, sweep rejection confirmation, R:R + target price, and magnet direction. **This reference covers only the mechanisms listed below.**

## 1. Timeframe Role Detection Pattern

### Problem
The user reported confusion: "切到1h又是另外一个了,要是切到4小时又是另外一个方案.总感觉好像有点奇怪." The action panel content already varied by market (crypto/metal/forex/stock) but NOT by timeframe role — so the same execution-grade entry price text showed on 1D as on 15m, which felt wrong. Community consensus (ICT, SmartMoneyICT, SMC And ICT, Arcanum Fx, PropTradingVibes 2026, Investopedia/TradeCiety/Bookmap) is unambiguous:
- **HTF (Weekly→Daily)** = Map / Bias Timeframe — "what to trade"
- **MTF (4H→1H)** = Structure / Setup Timeframe — "context for the setup"
- **LTF (15m/5m/1m)** = Execution Timeframe — "when to enter"

### Detection

```pine
int curTfSec = timeframe.in_seconds(timeframe.period)
string tfRole = curTfSec <= 900 ? "执行" : curTfSec <= 14400 ? "结构" : "背景"
```

- `<=900s` (≤15m incl 1s, 5s, 15s, 1m, 3m, 5m, 15m) → "执行" (entry-grade)
- `<=14400s` (≤4h incl 30m, 1h, 2h, 3h, 4h) → "结构" (structure-grade)
- `>14400s` (1D, 1W, 1M, 3M, 12M) → "背景" (bias-grade)

`900` was chosen because user's execution TFs are 5m/15m (crypto 15m, metal 5m); `14400` because user's structural TFs are 1h/4h. If user later switches to 30m execution (some scalpers), regenerate `900 → 1800`.

### Header Adaptation
Prefix the header with `[角色]` so the trader sees the role at a glance:

```pine
string fundingHint = isPerp and fundingText != "" ? " · " + fundingText : ""
string overlapHint = sessionOverlapText != "" ? " ⚡" + sessionOverlapText : ""
string headerLine = "[" + tfRole + "] " + focusHint + actionKillZoneLine + overlapHint + fundingHint
```

Example outputs:
- 15m BTCUSDT.P: `[执行] 看CVD+扫点 ⚡伦敦开盘 · 资金+0.1%空`
- 1h BTCUSDT:     `[结构] 看CVD+扫点 ⚡伦敦开盘`
- 1D BTCUSDT:     `[背景] 看CVD+扫点`

### actionLine5 Per-Role Switch
The 5th line (执行/structure/background) provides *actionable* feedback at each layer:

```pine
string actionLine5 = tfRole == "执行" ? "执行：" + lineAction
   : tfRole == "结构" ? "结构：" + (activeLongPlan ? "等5m/15m多入場" : activeShortPlan ? "等5m/15m空入場" : "等5m/15m执行信号") + " · " + htfTfLabel + "方向"
   : "背景：" + (htfBull ? "多头bias" : htfBear ? "空头bias" : "中性") + " · 等1h/4h结构"
```

- **执行周期**: full `lineAction` text — entry price + stop + target + R:R + invalidation (`多 65420 · 止63800 · 标↑67200(2.1R) · 失效破VWAP`)
- **结构周期**: "等5m/15m执行信号 · 1h方向" — tell trader to drill down for the entry
- **背景周期**: "多头bias · 等1h/4h结构" — give directional bias only; do NOT pretend a daily bar is an entry trigger

This eliminates the original confusion: the panel now explicitly tells the trader what role the current chart is playing and what to do next based on that role.

### Why this matters for ICT/SMC indicators
Trader-prefixed timeframe hierarchy is a community-best-practice ("3-timeframe rule" — trend/signal/entry). The panel already had the bias/structure/execution data layers internally; the FIX was making the panel aware of which layer the user is currently viewing. This is class-level: any multi-timeframe dashboard benefits from the role tag.

## 1.1 v10.3.1 — `tfRoleRec` Market-Recommended Timeframe Footer

### Motivation
User asked "其他市场的呢？我这个时间周期是不是有问题？你多渠道联网社区看一下时间周期的情况". The community audit (SmartMoneyICT / ArcanumFx / PropTradingVibes 2026 / SMC And ICT / Coinbase Learn / TradingView official / The Secret Mindset / BKTraders) produced a per-market optimal timeframe triplet:

| 市场 | 执行(LTF) | 结构(MTF) | 背景(HTF) |
|---|---|---|---|
| 加密 BTC/ETH 永续 | **15m** | 1h / 4h | 1D |
| 贵金属 XAU | **5m** | 15m / 1h | 4h / 1D |
| 外汇 EURUSD等 | **5m / 15m** | 1h / 4h | 1D |
| 股票/指数 ES/NQ | **5m** | 15m / 1h | 4h / 1D |

### Implementation
Add a per-market recommended-timeframe string and append it to the headerLine **only when the current chart is NOT the execution layer** (execution layer doesn't need to be told what it already is):

```pine
string tfRoleRec = marketCrypto ? "15m执行·1h/4h结构·1D背景"
   : marketMetal ? "5m执行·15m/1h结构·4h背景"
   : marketForex ? "5m/15m执行·1h/4h结构·1D背景"
   : (marketStock or marketIndex) ? "5m执行·15m/1h结构·4h/1D背景"
   : "5m/15m执行·1h/4h结构·1D背景"

string headerLine = "[" + tfRole + "] " + focusHint + actionKillZoneLine + overlapHint + fundingHint + (tfRole != "执行" ? " · " + tfRoleRec : "")
```

### Output
```
[执行] 看CVD+资金 ⚡伦敦开盘 · 资金+0.1%空            ← 15m, no footer (it IS the execution)
[结构] 看CVD+资金 · 15m执行·1h/4h结构·1D背景         ← 1h, footer shows full triplet
[背景] 看CVD+资金 · 15m执行·1h/4h结构·1D背景         ← 1D, footer shows full triplet
```

### Why footer only on non-execution
Execution-layer traders are actively entering — they don't need a "triplet reminder" clogging the header. Structure/background layer traders are *orienting* — they need to know "drill down to 5m/15m for the actual entry". The footer is a hint that points toward the next action, not a static label.

### f_auto_htf gradient fix (same session)
While here, also fixed a stale `f_auto_htf()` gradient — original returned `"D"` for both 1h AND 4h (1h and 4h saw the same context), and `"W"` for 1D. New gradient:
- 1m → 15m
- 5m → 1h
- 15m → 4h
- 1h → 1D
- 4h → **1W** (was 1D — duplicating 1h)
- 1D+ → **1M** (was 1W — now provides month-level bias)

This makes each timeframe see a UNIQUE higher-timeframe context, eliminating the silent duplication where 1h and 4h showed identical HTF bias.

## 2. Perpetual Futures Funding Rate Approximation

### Problem
User said "加密是使用永续合约品种" — they trade `.P` perpetuals primarily (BTCUSDT.P, ETHUSDT.P on Bybit/OKX/Binance Futures). Funding rate is one of the most cited perp-only order-flow signals (Coinbase Learn, Investopedia, MetaMask workflow article, TradingView "Funding Rate Explained" video). Community indicators like TradingView's official Funding Rate pane display it next to price.

But Pine Script v5/v6 has NO `request.funding_rate()` function — verified against the Pine Script v5 and v6 reference manual index (both lists end at request.dividends/earnings/economic/financial/footprint/quandl/security/security_lower_tf/seed/splits — funding rate is not included).

### Approximation Method
Use the **price premium of perpetual vs underlying spot** as a proxy for funding rate:

```pine
// Perpetual futures detection: PERP or .P suffix, crypto asset class only
bool isPerp = autoCrypto and (str.endswith(syminfo.ticker, "PERP") or str.endswith(syminfo.ticker, ".P"))

string SPOT_REF_TICKER = input.string("", "永续现货对标(留空自动)", group=FUNDING_GROUP,
   tooltip="留空则自动从当前ticker去掉.P后缀。PERP后缀合约需手动填写如BINANCE:BTCUSDT")

// Auto-derive spot ticker for .P suffix (Bybit/OKX/Binance .P style)
string autoSpotTicker = str.endswith(syminfo.ticker, ".P") ?
   syminfo.prefix + ":" + str.substring(syminfo.ticker, 0, str.length(syminfo.ticker) - 2) : ""

string spotTickerForPerp = SPOT_REF_TICKER != "" ? SPOT_REF_TICKER : autoSpotTicker

float perpSpotPrice = isPerp and spotTickerForPerp != "" ?
   request.security(spotTickerForPerp, timeframe.period, close, ignore_invalid_symbol=true) : na

float perpPremium = isPerp and not na(perpSpotPrice) and perpSpotPrice > 0 and close > 0 ?
   (close - perpSpotPrice) / perpSpotPrice * 100 : 0.0

string fundingText = isPerp and not na(perpSpotPrice) ?
   (perpPremium > 0.1 ? "资金+" + str.tostring(perpPremium, "#.0") + "%空"
    : perpPremium < -0.1 ? "资金" + str.tostring(perpPremium, "#.0") + "%多"
    : "资金中性") : ""
```

### Direction Semantics (per Coinbase Learn / Investopedia)
- **Positive premium (永续 > 现货)** = longs paying shorts = funding rate positive = **多方拥挤 → 利空** (label `资金+0.1%空`)
- **Negative premium (永续 < 现货)** = shorts paying longs = funding rate negative = **空方拥挤 → 利多** (label `资金-0.1%多`)
- **|premium| < 0.1%** = `资金中性`

The 0.1% threshold approximates Binance's typical 8-hour funding rate (0.01%/hour × 8 = 0.08%, plus volatility). Tighter thresholds increase sensitivity but produce more noise.

### Display
- headerLine: `… · 资金+0.1%空` (only when `isPerp && fundingText != ""`)
- actionLine3 (确认行) for crypto ONLY: append ` · 资金+0.1%空` at end

### Resource Cost
1 additional `request.security` call (the spot reference) — only triggered on perp tickers via the `isPerp and spotTickerForPerp != ""` guard. Pine's `request.security` always evaluates regardless of runtime guard, but `ignore_invalid_symbol=true` ensures non-perp charts return `na` cleanly without compile errors.

### Manual Override for PERP suffix
`.P` suffix auto-derivation works for Bybit/OKX/Binance-style USD-margined perpetuals. For **coin-margined PERP tickers** (e.g. `BTCPERP` on some exchanges), the spot ticker cannot be auto-derived (PERP→BTCUSDT mapping is not 1:1). Provide the `SPOT_REF_TICKER` input so the user can manually specify e.g. `BINANCE:BTCUSDT` for the spot reference. Default empty → uses auto `.P` derivation. If on a `PERP`-suffix chart without SPOT_REF_TICKER, `fundingText` is empty (silent skip — safer than guessing).

### Pattern applicability
This pattern works for any Pine indicator that overlays on a perpetual crypto chart and wants to surface funding rate context without external data feeds. It uses a single `request.security` spot call. Free TradingView accounts support `BINANCE:`, `BYBIT:`, `OKX:`, `COINBASE:`, `KRAKEN:` spot tickers — no paid data feed needed.

## 3. Perpetual Detection Helper

```pine
bool isPerp = autoCrypto and (str.endswith(syminfo.ticker, "PERP") or str.endswith(syminfo.ticker, ".P"))
```

Source: TradingCode `IsPerpetualFuture()` article. The `syminfo.type == "crypto"` guard is mandatory — some EUREX futures also end with `PERP`. Without the crypto guard, those would be misclassified.

## 4. Alertcondition Chinese-ization (tension with prior pitfall)

This session Chinese-ized all 13 `alertcondition` titles/messages:

```pine
alertcondition(alertLongA, "A多信号", "A多 入場" + ...))
alertcondition(alertKillZone, "KillZone开盘", killZoneLabel + "开盘")
alertcondition(alertMagnetHigh, "Magnet高分", "磁" + str.tostring(magnetScore) + magnetDir + ...))
```

**Tension with prior pitfall** documented in SKILL.md: "alertcondition() can produce misleading syntax errors with complex named arguments or non-ASCII messages; fall back to positional arguments and short ASCII titles/messages."

**Observed:** positional form with full-non-ASCII titles appeared to compile in this session's audit verification. The user has NOT confirmed these compile in their TradingView environment — the prior pitfall was based on actual compile errors in past Pine versions. **Recommendation:** leave the pitfall in place; the Chinese-ized alerts are a beta change. If user reports "alertcondition compile error", revert to ASCII titles + Chinese message bodies (the safer middle ground). Do NOT delete the prior pitfall based on a single unverified session.

## 5. New Alert Names

- `A多信号` / `A空信号` — A-grade entry, with entry price (`@<planPrice>`) in message
- `B多轻仓` / `B空轻仓` — B-grade entry
- `C多等回` / `C空等回` — C-grade reversal, wait for reclaim
- `扫低收回+CVD` — sweep low reclaim with CVD confirm
- `扫高拒绝+CVD` — sweep high rejection with CVD confirm
- `禁追` — no-chase state
- `SMT背离` — SMT divergence
- **NEW** `KillZone开盘` — KillZone opens (fires on `isKillZone and not isKillZone[1]`)
- **NEW** `CVD背离` — CVD divergence qualified (`cvdBullDivQualified or cvdBearDivQualified`)
- **NEW** `Magnet高分` — Magnet score crosses 70 (`magnetScore >= 70 and magnetScore[1] < 70`)

The 3 new alerts cover the three highest-signal market events that previously had no alert: KillZone openings (time-based entry window), CVD divergences (reversal-quality signal), and Magnet ≥70 (high-probability liquidity target). User explicitly said "到关键位必须主动推送到群里" — these alerts enable Webhook-driven 群推送.

## 6. Verification Commands Used

```bash
# After all patches, count resources
grep -cE '\bplot\(' file.txt       # 31 (target < 40)
grep -cE 'request\.security\(' file.txt  # 9 (limit 40)
grep -cE '\balertcondition\(' file.txt   # 13

# Check no multi-line expressions
grep -nE '( | or| and)$' file.txt | grep -v '//'   # should be empty
```

## 7. Community Sources

- **TradingCode** — `IsPerpetualFuture()` article (syminfo.type crypto + PERP/.P suffix)
- **TradingView Pine v5/v6 Reference Manual** — confirmed `request.funding_rate()` does NOT exist; only dividends/earnings/financial/economic/footprint/quandl/security available
- **Coinbase Learn: Funding Rates in Perpetual Futures** — direction semantics (positive funding = longs pay = crowding = potential reversal risk)
- **SmartMoneyICT: ICT Timeframes for Position, Swing & Scalping** — 3-tier hierarchy (Weekly/Daily=Map, 4H/1H=Structure, 15m/5m=Entry)
- **SMC And ICT (Facebook)** — Proper Timeframe Alignment: Daily-4H-15M/5M or Daily-1H-5M/1M
- **Arcanum Fx (Instagram)** — Scalper (15m bias, 5m confirm, 1m entry) vs Day Trader (Daily, 1h, 5m) vs Swing (W/M, 4h, 1h)
- **PropTradingVibes 2026: Multiple Timeframe Analysis** — 3-timeframe rule for NQ futures (Daily+1h+5m+1m)
- **Investopedia/TradeCiety/Bookmap** — HTF bias → LTF entry workflow canonical pattern
- **TradingView "Funding Rate Explained" video** — positive funding = long crowded, negative = short crowded
- **The Secret Mindset (YouTube, 990K subs)** — "Dollar Flip" system: DXY-first for XAU trading; same community-best-practice layering as funding-rate premium — cross-asset confirmation before entry
- **BKTraders / Kathy Lien (4-Hour Forex Strategy 2026 Update)** — 20/200 SMA crossover on 4h forex; reaffirms 4h as the structure-grade MTF for forex/euro crosses and gold

## 8. Why This Belongs in the Skill (Class-Level)

These mechanisms are **class-level techniques** applicable to ANY multi-market Pine indicator, not just this user's SVP v10:

1. **Timeframe role adaptation** benefits any indicator that has data layers for multiple timeframes. Without the role-aware header/execution row, traders switch timeframes and the panel content feels "wrong" because it doesn't tell them what to do *at that timeframe role*.

2. **Perpetual funding rate approximation** benefits any perpetual-overlaid indicator. Since Pine has no native funding rate function, this pattern will be the de-facto approach until TradingView adds one.

3. **Per-market timeframe triplet footer** (`tfRoleRec`) is a one-line addition that turns a confusing "why does the panel look different on 1h vs 4h?" into a self-documenting hint. Generic enough to apply to any multi-market dashboard.

4. **f_auto_htf gradient fix** (1h→1D, 4h→1W, 1D→1M) — each timeframe must see a UNIQUE higher-context layer. The pre-fix 1h/4h duplication was a silent bug that took a user complaint about "看着奇怪" to surface.

Future sessions reusing these on different indicators should reference this file for the recipe and adapt the role labels / threshold percentages per market context.