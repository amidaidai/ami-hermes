# 指标svp.txt v1 Production Audit — 2026-06-26

## File Identity
- **File**: 指标svp.txt (user's production indicator)
- **Location**: Uploaded via web UI, NOT the desktop file
- **Lines**: 2392
- **Outputs**: 31 plots + 2 fills + 1 bgcolor = 34 (under 64 limit)

## Audit Findings (3-Tier Format)

### 🔴 P0 — Session H/L Labels Not Appearing After Session Ends
- **Lines**: 1209–1256 (manageSession), 1395–1459 (merge block)
- **Root Cause**: When `SHOW_OPEN_ONLY_ACTIVE=true`, labels hidden at session start (text="", style=none). Session end only sets `isActive=false` — never restores labels. Merge block creates new labels only at `barstate.islast`.
- **Fix**: Restore labels at session end; skip session-end levels in merge; add 3-bar sweep protection window.
- **Reference**: `references/session-hl-delayed-display-fix.md`

### 🟡 P1 — CVD Divergence Missing Swing Magnitude Gate
- **Lines**: 804–805
- **Issue**: Simple high/low comparison triggers false divergences on minor price wiggles.
- **Community Standard**: NikaQuant Quantum Map — 3-condition gate: price swing extreme + CVD non-confirm + swing ≥ 1.5×ATR(14).
- **Fix**: Add `ta.pivothigh/low(5,5)` + `recentSwingHighAmp >= 1.5 * ta.atr(14)`.

### 🟡 P1 — Non-Crypto Markets Still Accumulate Asia CVD
- **Lines**: 974–983
- **Issue**: Forex/metals Asia session has negligible volume; CVD data is noise.
- **Community Consensus**: ICT/Reddit r/InnerCircleTraders — crypto=3 channels, forex=London+NY only, metals=London+NY only.
- **Fix**: Add `cvdAsiaActive` flag gated by `MARKET_ADAPTIVE_ENGINE`.

### 🟡 P2 — VP Bucket Mintick No Market Adaptive Scaling
- **Line**: 524
- **Issue**: `VP_MIN_TICK_MULT * mintick` gives 0.2 for BTC (fine), 0.2 for XAUUSD (coarse on $3000), 0.0002 for EURUSD (absurdly narrow).
- **Community**: Betashorts multi-asset guide — mintick-based precision must be market-aware.
- **Fix**: `finalVpMinTickMult = crypto?20 : metal?≥50 : forex?≥40 : stock?≥30` gated by `MARKET_ADAPTIVE_ENGINE`.

### 🟢 P3 — f_cutoff_ms Uses `time` Instead of `timenow` on Realtime Bar
- **Lines**: 1133–1139
- **Issue**: On last unfinished candle, `time` = candle open time, not current time. Off-by-one cutoff drift possible.
- **Fix**: Use `timenow` when `barstate.islast`, fall back to `time` for historical bars.

## Not an Issue
- **VWAP anchor logic** (line 762): `autoSvwByMarket` = original per-market logic. CORRECT. Community suggestion to force daily for forex/metals was applied then reverted — dashboard's SMART_HIDE_VWAP + manual override already cover the problem.
- **SVP anchor** (line 662): `autoProfileByMarket` = UNCHANGED, original logic intact.
- **Output count** (34): Safe under 64 limit. No compression needed for this version.
