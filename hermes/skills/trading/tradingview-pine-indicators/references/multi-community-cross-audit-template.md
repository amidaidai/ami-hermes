# Multi-Community Cross-Audit Framework for Pine Dashboards

## Purpose
Template and methodology for comprehensive multi-community audits of mature Pine Script indicators, especially multi-factor dashboards combining SVP/ICT/VWAP/EMA/CVD/DMI.

## When to Use
User says "全面审计", "联网社区对照", "看看社区怎么说", or asks "适应多社区多品种吗".

## Search Matrix (run ALL in parallel)

| Platform | Search Pattern | Purpose |
|----------|---------------|---------|
| TradingView | `site:tradingview.com <indicator-type> best practice 2025` | Peer indicator design patterns |
| Reddit | `r/pinescript OR r/TradingView "<topic>" best practice pitfall` | Real-world gotchas |
| GitHub | `"pine-script" "<feature>" adaptive OR multi-asset` | Open-source implementation |
| Medium/DevTo | `"Pine Script" "multi-asset compatibility" OR "adaptive thresholds"` | Architecture articles |
| ICT Community | `r/InnerCircleTraders OR innercircletrader.net killzone session forex crypto metals` | Session/CVD standards |

## 8-Dimension Audit Rubric

| # | Dimension | Key Checks | Community Source |
|---|-----------|------------|------------------|
| 1 | Core Structure | SVP anchor logic, VWAP bands, EMA cloud alignment | TradingView editor's picks |
| 2 | Session/ICT | KillZone naming, DST handling, session-end label lifecycle | ICT docs, r/InnerCircleTraders |
| 3 | CVD/Order Flow | Divergence gate (3-condition), key-level filtering, swing magnitude | NikaQuant Quantum Map |
| 4 | Multi-Market | Per-asset parameter matrix, CVD channel config, VWAP anchor | Betashorts guide |
| 5 | DMI/Decision | ADX thresholds per market, Wilder14 vs aggressive, grade stability | LuxAlgo adaptive sensitivity |
| 6 | Action Panel | Line count (≤6), prefix dedup, color grading, focus text | AGPro 6-field standard |
| 7 | Performance | Output series count (<40), request.security bundling, object lifecycle | StackOverflow, TV docs |
| 8 | Settings | Dead controls, group ordering, defaults, kill-switches | r/TradingView complaints |

## Output Format

Use the 3-tier community-validated format:

```
✅ 正确 (already correct per community consensus)
⚠️ 需加强 (community has higher standard)
🟢 可优化 (opportunity, not broken)
```

With P0/P1/P2 priority tags and table references.

## Multi-Asset Matrix Template

| Asset Class | SVP | VWAP | EMA | ICT Sessions | CVD | DMI | Overall |
|-------------|-----|------|-----|-------------|-----|-----|---------|
| Crypto (BTC/ETH) | | | | | | | |
| Altcoins | | | | | | | |
| Metals (XAUUSD) | | | | | | | |
| Forex (EURUSD) | | | | | | | |
| Stocks (AAPL) | | | | | | | |
| Indices (SPX) | | | | | | | |

## Key Community References

### NikaQuant Quantum Liquidity Map (TradingView)
- 3-condition CVD divergence: new swing extreme + CVD non-confirm + swing > 1.5×ATR
- VP + VWAP + CVD confluence as structural event
- "Three independent systems agreeing" principle

### Betashorts Multi-Asset Compatibility Guide (Medium, Sep 2025)
- Step 1: Avoid hardcoded thresholds → use `syminfo.mintick`
- Step 2: Detect symbol type → `syminfo.type` / `syminfo.currency`
- Step 3: Normalize volatility → ATR-based stops
- Step 4: Dynamic formatting → `format.mintick`

### ICT KillZone Standards (Reddit r/InnerCircleTraders)
- Crypto: 3 sessions (Asia/London/NY), all have volume
- Forex: 2 significant (London/NY), Asia low volume
- Metals (XAUUSD): 2 significant (London/NY), gold barely trades in Asia
- KillZone ≠ Silver Bullet (10-11am specific window)

### LuxAlgo/AGPro Dashboard Design Consensus
- ≤6 lines, single-cell table
- No ticker name (chart already shows it)
- Color-by-state, not color-by-indicator
- `：` (Chinese colon) label separator
- Module prefixes in row template, NOT in value text

### StackOverflow request.security Limits
- 40 calls hard limit
- Tuple bundling: 1 call → 7 values (`[open, high, low, close, hl2, hlc3, ohlc4]`)
- Memory limit errors from excessive calls

## Session-Specific Findings (2026-06-25)

### From the SVP+ICT+VWAP+EMA+CVD audit:

**P0 Issues Found:**
1. Session-end labels hidden by `barstate.islast` merge (fixed)
2. Instant sweep after session end (fixed with 3-bar protection)
3. `f_cutoff_ms` using `time` instead of `timenow` (fixed)

**P1 Multi-Market Gaps Found:**
1. 3-channel CVD running on forex/metals (Asia noise) → should auto-disable
2. VWAP anchor not market-adaptive → forex/metals should force daily anchor
3. VP bucket width not auto-adjusted → metals too coarse, forex too fine

**Action-panel execution-gate findings (2026-06-26):**
When auditing a Pine dashboard whose top-right table is intended as the user's real entry-decision aid, treat the panel as an execution gate, not a loose summary. Required checks:
1. **R:R must gate execution, not merely display.** If `rrRatio < 2`, A/B executable states must downgrade to wait/invalid and the panel should say `R:R不足` rather than showing an entry.
2. **Targets must be direction-filtered.** A long plan may only compute reward against an above-price magnet/liquidity target; a short plan may only compute reward against a below-price target. Nearest magnet across both sides can create false R:R.
3. **Grade controls price specificity.** A-grade may show entry/stop/target; B-grade should show trigger conditions; C-grade should show observation only. Do not render B/C as if they were ready limit orders.
4. **HTF checklist is side-specific.** For a long plan check `htfAllowLong`; for a short plan check `htfAllowShort`. Do not use a generic `htfAllowLong and htfAllowShort` pass/fail.
6. For Tangxi SVP/ICT right-top cockpit panels, keep labels symmetrical and decision-oriented: `层级 / 结论 / 结构 / 确认 / 关键 / 计划 / 风险`. Avoid bracket headers like `[执行]`; use `层级：执行/结构/背景`. Use `计划：` instead of `执行：` so it aligns with the other row labels. The panel must include upper/lower key liquidity or Magnet targets, concrete B/C wait conditions at named levels, invalidation, R:R, and risk/extension context; do not leave B/C as vague “不给价”.
7. For weekly liquidity pools on intraday charts, default Tangxi production settings are: display distance `8 ATR`, line width `1`, label size `small`, and session background transparency `80`. Draw previous-week levels from the current week’s first bar (`curWeekStartBar` captured on `ta.change(time("W"))`), not from the bar where ATR visibility first becomes true. Otherwise H1 BTC/XAU charts can make the level visually start on Tuesday if Monday was outside the ATR display window or if the line was deleted/recreated later. Do not dedupe weekly pools against previous-day pools; they are different timeframe liquidity even when prices are equal. Sweep confirmation should match daily/session logic: wick through + close back inside, not mere touch/breakout.

**P1 Multi-Market Gaps Found:**
1. 3-channel CVD running on forex/metals (Asia noise) → should auto-disable
2. VWAP anchor not market-adaptive → forex/metals should force daily anchor
3. VP bucket width not auto-adjusted → metals too coarse, forex too fine

**DST Verification:**
- `Asia/Shanghai`: UTC+8, no DST → always correct ✓
- `Europe/London`: IANA auto-handles BST/GMT → correct ✓
- `America/New_York`: IANA auto-handles EDT/EST → correct ✓
- Session overlap tooltips verified correct for summer/winter shift
