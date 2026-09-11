# Cron Job Push Scoring Rubric (BTC Edition)

## Purpose
Standardized 10-factor scoring for 5m cron push decisions. Score ≥ 7 AND direction clear (not X/conflict) → push to topic 386 with screenshot. Otherwise → [SILENT].

## The 10 Factors (each 0-10, threshold ≥70/100 or 7/10)

| # | Factor | Weight | Source | How to Score |
|---|--------|--------|--------|-------------|
| 1 | HTF Direction (4h/1h) | 1.0x | SVP Action Grid (结论 row) | "A多/空"=9-10, "B多/空"=7-8, "等空/多"=5-6, "等多/空 ⚠冲突"=3-4, "X禁做"=0-2 |
| 2 | LTF Momentum (15m/5m) | 1.0x | SVP Action Grid + study_values | Price above 15m VWAP + EMA9>21 + buy flow = 7-10; mixed = 4-6; all bearish with sell flow = 0-3 |
| 3 | MTF Alignment | 1.5x | Compare 4h→1h→15m direction | All same direction=9-10, 2/3 aligned=6-8, only LTF aligned=3-5, full conflict=0-2 |
| 4 | Action Grid Grade | 1.0x | SVP conclusion + conflict flag | A=9-10, B=6-8, C/等=3-5, X=0-2; +⚠conflict → -2 penalty |
| 5 | Sub-indicator Verdict | 1.0x | Volume Aggregated table | "可执行/追"=8-10, "等多"=5-7, "降级/不追/逆高周"=2-4, "放弃/禁做"=0-2 |
| 6 | Taker/Order Flow | 1.0x | Binance get_taker_volume | Consistent buy (ratio>1.2 across 3 bars)=7-10, mixed=4-6, sell dominant=0-3 |
| 7 | OI Trend | 0.8x | Binance get_open_interest_history | OI rising with price=8-10, OI flat=5-7, OI falling=3-4, OI falling + price down=1-2 |
| 8 | Funding Rate | 0.5x | Binance get_funding_rate_history | Neutral (0.001-0.01%)=7-10, slightly extreme=4-6, very extreme=0-3 |
| 9 | Long/Short Crowding | 0.7x | Binance get_long_short_ratio | 1.0-1.5=7-10, 1.5-2.0=4-6, >2.0 or <0.5=0-3 (contrarian risk) |
| 10 | Volume Quality | 1.0x | OHLCV summary + sub-indicator "量能" | Increasing volume=8-10, steady=5-7, decreasing/shrinking=2-4, exhaustion=0-2 |

**Final Score = sum(factor_i × weight_i) / sum(weights)** → clamp 0-10.

## Push Decision Flow

```
Score ≥ 7 AND direction NOT X/conflict → PUSH:
  - Generate push card with ↑↓○× arrow + key levels + VWAP
  - Attach MEDIA screenshot
  - Target: telegram:-1003733144325:386

Score < 7 → [SILENT]:
  - No push, no screenshot needed
  - Score < 5 → definitely silent
  - Score 5-6 → potentially borderline, but still silent — only ≥7 pushes

Direction IS X/conflict → [SILENT]:
  - Even if score ≥ 7, if Action Grid shows "X" or ⚠conflict, do NOT push
  - X-level signals are local-recording-only, never pushed to chat
```

## Concrete Scoring Examples

### Example A: Low-confidence (this session)
- 4h: "B空 轻仓" → 6
- 15m: "等多 回踩 ⚠冲突" + price above 15m VWAP → 5
- MTF: bearish 4h vs bullish 15m = conflict → 3
- Action Grid: "C/等" with ⚠ → 3 (-2=1)
- Sub-indicator: "逆高周·不追·降级" → 2
- Taker: mixed buy/sell spikes → 4
- OI: mild decline 102.8K→102.7K → 3
- Funding: 0.0014% → 8
- L/S Ratio: 2.1 → 1
- Volume: shrinking → 3

**Result: ~4.5/10 → [SILENT] ✓**

### Example B: High-confidence (hypothetical)
- 4h: "A多 正常仓" → 9
- 15m: "A多 正常仓" + price above VWAP, EMA9>21 → 9
- MTF: full bullish alignment → 9
- Action Grid: "A" no conflict → 9
- Sub-indicator: "可执行" → 8
- Taker: consistent buy 1.5 across bars → 8
- OI: rising with price → 9
- Funding: neutral 0.005% → 7
- L/S Ratio: 1.2 → 8
- Volume: increasing → 8

**Result: ~8.5/10 → PUSH ✓**

### Example C: Real session — main vs sub-indicator color conflict (2026-06-28 BTC cron)

Key challenge: SVP main says "等空 反抽" on both 4h and 15m, but sub-indicator says `🔴偏多·1/4` on 4h and `🟡偏空·2/4` on 15m. The 🔴 prefix makes the sub-indicator's apparent "偏多" actually a bearish-downgrade signal — **not a directional conflict**.

| # | Factor | Raw Data | Score | Notes |
|---|--------|----------|-------|-------|
| 1 | HTF Direction | 4h SVP "等空 反抽" | 5 | C/等 bearish-waiting |
| 2 | LTF Momentum | 15m: price~VWAP(60,134), EMA flat, weak bear | 3 | Low momentum, mixed flow |
| 3 | MTF Alignment | SVP consistently "等空" on 4h+15m (sub 🔴 not directional) | 5 | 2/2 aligned if ignoring sub 🔴 prefix |
| 4 | Action Grid | "等空 反抽" on both TFs, no ⚠ flag | 5 | Clean C/等 |
| 5 | Sub-indicator | 4h: "降级/放弃" (2), 15m: "逆高周不追" (3) | 3 | 🔴🟡 both downgrade |
| 6 | Taker | Mixed: buy 1.52 / sell 0.39 (last bar) | 4 | No consistent direction |
| 7 | OI | 103.4K→103.5K, +0.1% | 5 | Flat/slight rise |
| 8 | Funding | 0.0014% | 8 | Neutral |
| 9 | L/S Crowding | 2.12x long | 1 | Heavily skewed ⚠ |
| 10 | Volume | Shrinking, 84% perp | 3 | Low conviction |

**Score: 4.1/10 → [SILENT] ✓**

**Lesson**: When the sub-indicator shows `🔴偏多` but the main SVP shows consistent "等空", do NOT treat this as an MTF conflict (would wrongly lower Factor 3). The 🔴 prefix in the sub-indicator is a warning, not a bullish vote. Always check `references/volume-aggregated-color-semantics.md` before scoring Factor 3 when the sub-indicator uses 🔴/🟡 prefixes.

## Quick Reference: Action Grid → Score Mapping

| SVP Conclusion Text | Base Score | Notes |
|--------------------|-----------|-------|
| "A多 正常仓" / "A空 正常仓" | 9 | Clear, tradable |
| "B多 轻仓" / "B空 轻仓" | 7 | Partial conviction |
| "等多 回踩" / "等空 反抽" | 5 | Waiting, no conflict |
| "等多 回踩 ⚠冲突" / "等空 反抽 ⚠冲突" | 3 | Conflict detected |
| "X禁做 结构冲突" / "X禁做 过热" | 1 | Do not trade |
