# Session CVD + KillZone + SMT Additions (v8.2.9+)

Pattern from 2026-06-24 community audit session. Full implementation with pitfalls discovered during compilation. Updated 2026-06-24 in second session: corrected unprofessional KillZone naming and CVD notation.

## What was added

### Session CVD Three-Channel (Asia/London/NY)
- Accumulates CVD delta separately for each session, reset daily
- Computes slope for each channel over `CVD_SLOPE_LEN` bars
- Displays dominant session in action panel CVD line: `CVD：主D关键位吸收，伦敦主导`
- Session channel notation uses **+/-/~** (universal financial standard): `亚+` (net buying), `亚-` (net selling), `亚~` (neutral). **Never** ↑↓→ arrows.
- Session row label: **`CVD分时`** (NOT `CVD会话`)
- Encoded into single Data Window float: `A*1e6 + L*1e3 + N` (rounded to k-units)
- Input group: `"05 CVD - 会话三通道"`, boolean `SHOW_SESSION_CVD`

### KillZone Time Windows
- London KillZone: 07:00-09:30 local (`KILLZONE_LONDON_TIME`)
- NY KillZone: 08:20-11:30 local (`KILLZONE_NY_TIME`)
- Detects: `inKillZoneLondon`, `inKillZoneNY`, `isKillZone`
- Labels: **`伦敦开盘` / `纽约开盘`** — unified across all markets. This matches ICT "London Open Killzone" / "NY Open Killzone" community standard.
- **NEVER** use: `白银`, `伦窗`, `纽窗`, `伦敦白银`, `纽约白银`, `伦敦高波`, `纽约高波`, or emoji flags (`🇬🇧 / 🇺🇸`). "白银" is a mistranslation — Silver Bullet is specifically the 10-11am window, not the broader KillZone.
- **NEVER** use `bgcolor()` for KillZone. Text markers only (`⚡伦敦开盘`).
- Input group: `"02 ICT - KillZone开盘窗口"` (NOT "白银时刻"), boolean `SHOW_KILLZONE`

### SMT Cross-Instrument Divergence
- Auto-detects pair: BTC→ETH, XAU→DXY, ES→RTY
- Compares 5-bar relative change between main and reference instrument
- `smtBullDiv`: main rising while reference falling, main below 3-bar close
- `smtBearDiv`: main falling while reference rising, main above 3-bar close
- Encoded in Data Window: 2 (bull), -2 (bear), 0 (none)
- Alert: `"Pro SMT Divergence"` → `"SMT divergence detected"`
- Input group: `"05 CVD - SMT跨品种背离"`, boolean `SHOW_SMT` + pair selector + manual ticker

### Entry Checklist Row
- Added to action panel when `activeLongPlan or activeShortPlan`
- Row label: **`条件`** (NOT `核对`)
- Format: `条件｜HTF✓ EMA✓ CVD✓ 位✓ SMT⚠`
- `ckRr` entry was **removed** when trade controls were deleted

## Compilation Pitfalls Discovered

### #1: Declaration order — isAsia/isLondon/isNY
These session booleans are declared at the bottom of the ICT block (~L1042). Session CVD logic referencing them was inserted after `cvdStateText` (~L870), which is ~170 lines BEFORE the declaration. Pine is single-pass — this produces `Undeclared identifier` errors.

**Fix:** Move the entire Session CVD + KillZone + SMT block to immediately after `bool isNY = ...` declaration. Verify with `grep -n`.

### #2: Declaration order — bgcolor(isKillZone)
Even after fixing #1, `bgcolor(isKillZone ...)` was placed in the EMA section (~L967), which is still BEFORE `isKillZone` declaration (~L1000). `bgcolor()` is a global-scope call that references its argument every bar — same declaration-order rule applies.

**Fix:** Move `bgcolor()` to after the `cvdSessionSummary` line (which follows `isKillZone`). Then removed entirely per user preference.

### #3: Output limit (64 series)
Session CVD (3 plots) + SMT (3 plots) + Object Count (1) + CVD Source (1) = 8 additional Data Window plots pushed total beyond 64.

**Fix:** Encode multiple values into single floats:
- 3 Session CVD values → 1 encoded float
- 3 SMT values → 1 divergence code only
- 3 Risk params (Risk%/Daily%/Weekly%) → 1 encoded float
- 3 Effective params (ATR/VWAP Ext/CVD weight) → 1 encoded float
- 3 Scores (Location/Confirm/Extension) → 1 encoded float
- Replay Stop Distance + Stop ATR → 1 encoded float
- Object Count + CVD Source → removed entirely
- `Trade Control Blocked` → removed with trade controls

Reduction: 45 → 29 plots (16 saved). Total output series: ~33.

### #4: Unused function f_session_cvd_capture
Defined during initial implementation but the actual session CVD uses inline variables (`cvdAsiaBar = isAsia ? cvdBarDelta : 0.0`). Removed to keep code clean.

### #5: Unprofessional KillZone naming (fixed 2026-06-24)
Initial implementation used `🇬🇧白银`/`🇺🇸白银` based on "Silver Bullet" translation. User explicitly called this unprofessional. Correct: `伦敦开盘`/`纽约开盘` — unified across all markets, matching community "London Open Killzone" / "NY Open Killzone". All input group names and tooltips also updated from "白银时刻" to "开盘窗口".

### #6: Ambiguous CVD session arrows (fixed 2026-06-24)
Initial implementation used ↑↓→ arrows for CVD session direction. User found these unclear. Changed to +/-/~ (universal financial standard). `+` = net buying, `-` = net selling, `~` = neutral.

## Action Panel Display Rules (Post-Audit v8.2.9+)

### CVD line
```pine
// Anchor: 主D / 主W / 主M (via f_tf_label)
// Session comma only when SHOW_SESSION_CVD is true
// NO redundant direction after absorption/distribution
cvdAbsorbBuy      → "CVD：主D关键位吸收，伦敦主导"
cvdBullConfirm    → "CVD：主D买盘跟随，亚洲主导"
cvdBearDiv         → "CVD：主D顶背离转弱，近关键位"
cvdStateText       → "CVD：主D买盘回升"  (no session when SHOW_SESSION_CVD=false)
```

### ICT line
```pine
sweptLowReclaimed  → "ICT：扫亚低后收回"    (uses lastEventName for richer context)
sweptHighRejected  → "ICT：周四伦高后拒绝"   (includes day name from lastEventName)
sweptLowNow        → "ICT：正在扫纽低"       (uses ictEventName for same-bar)
```

### CVD session row
```pine
// Row label: CVD分时 (NOT CVD会话)
// Notation: +/-/~ (NOT ↑↓→)
cvdAsiaSlope > 0   → "亚+"
cvdLondonSlope < 0  → "伦-"
cvdNYSlope == 0     → "纽~"
// Full row: "CVD分时｜亚+ 伦+ 纽~"
```

### KillZone marker
```
⚡伦敦开盘    (not ⚡🇬🇧白银)
⚡纽约开盘    (not ⚡🇺🇸白银)
```

## External Script Decoding

```python
# Session CVD
asia_k = int(cvd_session // 1e6)
london_k = int((cvd_session % 1e6) // 1e3)
ny_k = int(cvd_session % 1e3)

# Risk params
risk_pct = int(risk_encoded // 10000) / 100
daily_pct = int((risk_encoded % 10000) // 100) / 100
weekly_pct = risk_encoded % 100

# Scores
location = int(sc_encoded // 100)
confirm = int((sc_encoded % 100) // 10)
extension = sc_encoded % 10
```
