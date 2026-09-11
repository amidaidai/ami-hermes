# Multi-Channel Web Research Audit Methodology (2026-06-24)

How to audit a mature Pine Script multi-factor dashboard against external sources, community standards, and known platform limitations.

## Audit Dimensions (10-point framework)

Run searches across ALL dimensions in parallel — don't serialize. Each dimension targets specific keywords:

### 1. Pine Script Technical Compliance
- `Pine Script v5 output limit 64 plot fill bgcolor workaround`
- `Pine Script request.security repainting lookahead barmerge gaps`
- `Pine Script request.security_lower_tf accuracy limitation history bar count`
- Count all output series: `plot()` + `fill()` + `bgcolor()` + `linefill.new()` + `table.new()` → must stay under 64

### 2. CVD/Delta Data Accuracy (FUNDAMENTAL LIMITATION)
- `TradingView CVD cumulative volume delta fake inaccurate tick proxy`
- `Pine Script f_cvd_delta close open volume approximation limitation`
- Community consensus: TradingView CVD is a **tick-volume proxy** (`close > open` heuristic), NOT true bid/ask order flow. Divergences are probabilities, not guarantees.

### 3. Volume Profile (SVP) Accuracy
- `TradingView volume profile POC VAH VAL accuracy issue low time frame`
- `Do NOT rely on TradingView Volume Profiles Reddit`
- Key finding: uniform volume distribution across candle range can shift POC to untraded levels

### 4. ICT/SMC Methodology Alignment
- `LuxAlgo ICT Concepts TradingView 2026 most popular settings`
- `ICT KillZone standard times London 07:00-09:30 New York 08:20-11:30`
- `Top 10 ICT indicators TradingView 2026`
- Benchmark against community gold-standard indicators (LuxAlgo 25,600 likes)

### 5. DMI/ADX Parameter Standards
- `ADX indicator Wilder standard DI length 14 vs 10 Pine Script`
- `DMI ADX smooth best practice TradingView`
- Compare script's DI_LEN/ADX_SMOOTH/DMI_ADX_TREND against Wilder classic 14/14/20-25

### 6. Performance & Resource Limits
- `Pine Script max_lines_count max_labels_count max_polylines_count`
- `request.security() max 40 unique calls limit`
- `Pine Script too many scopes limit 550 v5 vs v6`

### 7. Community Best Practices Alignment
- Benchmark against popular community indicators
- Check for known anti-patterns (bgcolor on KillZones, trade controls, etc.)
- Verify naming conventions match community standards

### 8. Market-Specific Parameter Sensitivity
- Review `eff*` parameter tables per market
- Check if crypto/forex/metal thresholds align with known volatility profiles

### 9. Code Architecture Audit
- Single-pass sequential compilation order
- Dead code detection (`grep -c` per variable)
- Feature removal completeness (4-layer check: inputs, calc, branches, Data Window)

### 10. Forward Calibration & Signal Quality
- Check calibration horizon appropriateness per timeframe
- Verify hit-rate thresholds and downgrade logic
- Assess CVD quality guard effectiveness

## Output Format

Produce a structured report with:
- Per-dimension 🔴/🟡/🟢 rating
- Evidence citations (URLs, community consensus)
- Specific line references from source code
- Prioritized fix recommendations

## Key Community Sources (2026)

| Source | Topic | Finding |
|---|---|---|
| r/TradingView "Do NOT rely on TV Volume Profiles" | SVP accuracy | Uniform volume distribution shifts POC |
| TradingView docs "CVD is tick-volume proxy" | CVD accuracy | Not true order flow, divergences fail often |
| Stack Overflow "limit output 64" | Output limits | Composite float encoding pattern |
| LuxAlgo ICT Concepts (25.6K likes) | ICT benchmark | KillZone times, session colors, sweep detection |
| Pineify/mindmathmoney YouTube | Community standards | ADX 14/14 standard, DI interpretation |
| TV Pine docs "Other data/timeframes" | security() limits | LTF ~100K bars, 40 unique calls max |

## Pitfalls Discovered During Audit (add to SKILL.md)

All four pitfalls below were discovered during the v9.3 audit and **implemented in v9.4 (2026-06-24)**. See SKILL.md pitfalls section for current code patterns.

### DMI/ADX non-standard DI_LEN=10 → ✅ IMPLEMENTED v9.4
Wilder classic = 14. Using 10 creates more sensitive but noisier signals.
Market-adaptive ADX thresholds (crypto 25/45 vs standard 20/40) partially compensate.
**Fix:** Added `DMI_MODE` toggle `标准(Wilder14)` / `激进(短周期)`. Derived `finalDmiDiLen` and `finalDmiAdxSmooth` select 14 or 10 based on mode.

### Forward calibration TF-agnostic horizon → ✅ IMPLEMENTED v9.4
`CAL_HORIZON_BARS=12` was fixed regardless of chart timeframe.
**Fix:** Replaced with TF-adaptive: `<1m→48, <5m→24, <15m→12, <1H→8, <4H→6, <1D→4, ≥D→3`.

### VP_MIN_TICK_MULT market-adaptive need → ✅ IMPLEMENTED v9.4
Default 20x mintick works for BTC but too narrow for forex, too coarse for metals.
**Fix:** Added `finalVpMinTickMult` with market floors: crypto=20, stock≥30, forex≥40, metal≥50.

### SMT auto-pair cross-exchange blind spot → ✅ IMPLEMENTED v9.4
Old hard `==` ticker checks silently failed on BYBIT/OKX/KUCOIN.
**Fix:** Replaced with `f_is_btc_pair()` / `f_is_xau_pair()` helper functions matching all major exchanges.
