# Pine Script Indicator Audit Methodology

**Source session**: 2026-07-10 audit of `SVP_production_optimized.pine`  
**Applicability**: Any Pine Script v6 indicator audit for production deployment

---

## 5-Point Audit Checklist

### 1. CVD Swing Filter Integration (`cvdDivSwingOk` → `qualified`)
- **Check**: `cvdDivSwingOk` (swing magnitude > 1.5×ATR) must be AND'd into `cvdBearDivQualified` / `cvdBullDivQualified`
- **Location pattern**: Search `cvdDivSwingOk` definition → verify used in `*Qualified` booleans
- **Star logic**: Absorption (buy pressure at lows) → bull stars; Distribution (sell pressure at highs) → bear stars. Verify not swapped.

### 2. DMI Hot State: A-Grade vs X-Grade Consistency
- **Check**: `dmiHot = (dmiAdx >= effDmiAdxHot)` blocks A-grade (`not dmiHot`), marks X-grade (`xHot = dmiHot`), adds to reversal score (`+1`)
- **Logic**: A-grade = trend-follow (exclude overheat); X-grade = risk flag; Reversal = counter-trend opportunity → **no contradiction**

### 3. Magnet Variable Triplet Consistency (name/price/score)
- **Three buckets**: `magnetNearest*`, `magnetAbove*`, `magnetBelow*` — each has `Name`, `Price`, `Dist`, `Score`, `Htf`
- **Target selection**: `planSideLong ? magnetAbove* : planSideShort ? magnetBelow* : magnetNearest*`
- **Verify**: Display texts (`magnetAboveText`/`magnetBelowText`) use only their own bucket's variables — no cross-bucket leakage

### 4. `request.security` Dead-Link Audit
- **Enumerate all calls** (max 40 in Pine v6)
- **Classify each**:
  - ✅ Live: `syminfo.tickerid` + standard TF (`"D"`, `htfTf`, `timeframe.period`)
  - ⚠️ Conditional: User-input symbols (`smtTicker`, `spotTickerForPerp`), `_OI` suffix
  - ❌ Dead: Hardcoded delisted symbols, deprecated APIs, duplicate same-data calls
- **TV verify**: Data Window → watch each return variable for `na` on cold start / symbol switch

### 5. Single-Assignment Variable Disposition
| Category | Action | Examples |
|----------|--------|----------|
| **Used downstream** (scoring, panel, Data Window, replay) | **Keep** | `cvd*Qualified`, `setupLongA`, `xHot`, `magnetTarget*`, `extensionRiskScore` |
| **Intermediate only, no downstream ref** | **Delete** | (none found in this audit) |
| **Business sentinel** (threshold flags, gating booleans) | **Keep** | `nearAKeyLevel`, `acceptanceBullOk`, `dmiVerifyText` |

---

## Report Template (Markdown)

```markdown
# <Indicator>_audit_report_<YYYYMMDD>.md

## Core Conclusions (table)
## Detailed Findings per Checkpoint
## Minimal Patch Locations (file, line, old→new, risk, TV verify)
## Verification Checklist (8-step TV runbook)
```

---

## TV Verification Runbook (8 Steps)

1. **CVD star semantics** — BTCUSDT 5m: panel `吸收/派发` + `★` vs price location
2. **`cvdDivSwingOk` gating** — Data Window: `cvdDivSwingMag` / `currATR` → watch qualified flip
3. **`dmiHot` A/X split** — Strong trend (ADX>45 crypto): A-grade absent, X-grade "过热", reversal +1
4. **Magnet direction** — Long plan → target above price (↑); Short plan → target below (↓)
5. **`request.security` liveness** — Data Window: all 12 return vars non-`na` (except conditional-off)
6. **Data Window completeness** — All `plot`/`label`/`box.set_text` fields visible
7. **FVG/OB label placement** — Zoom into box: text bottom-right (`halign=right`, `valign=bottom`)
8. **Compiler limits** — Pine Editor footer: `request.security ≤ 40`, `plot ≤ 64`, `max_*_count` OK

---

## Patterns Observed in This Audit

- **CVD absorption/distribution**: Price-range compression (`≤ ATR×mult`) + CVD delta divergence (`> avgDelta×mult`) + close position in range (0.45/0.55 quantile) — reliable pattern
- **Adaptive thresholds by market**: `effDmiAdxHot` (crypto 45 / forex 35 / metal 42), `effCvdKeyLevelAtr` — audit must verify per-market values
- **HTF confirmation via `request.security(..., lookahead_on)`** — only for confirm packs, never for entry triggers
- **Magnet scoring**: `distScore×0.4 + freshnessScore×0.3 + prioScore×0.3 + (HTFconf?20:0)` — weights auditable
- **Replay/review fields**: `replaySideCode`, `replayGradeCode`, `replayPlanPrice` — required for Data Window post-trade analysis