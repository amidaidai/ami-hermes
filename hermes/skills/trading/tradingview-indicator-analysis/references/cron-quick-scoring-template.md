# Cron Quick Multi-Factor Scoring Template (v1.0 · 2026-06-28)

## Purpose

Standardized lightweight scoring for 5-min agent cron cycles that decide whether to push an alert or stay silent. This is NOT a replacement for the full weighted scoring used in `render_card_locked()` — it is a fast gate that maps SVP action table + Binance data to a 0-80 score with threshold ≥56/70% for push.

## Eight Factors (10 pts each = /80)

| # | Factor | What to assess | Scoring guide |
|---|--------|---------------|--------------|
| 1 | **TV SVP等级** | Read `pine_tables` action table "结论\|" row | A=8-10, B=5-7, C=2-4, X=0. If table mentions `⚠冲突` subtract 2 |
| 2 | **VWAP/EMA结构** | Price vs VWAP-Band1, EMA9/21/34/55 order | All bearish and price below all EMAs=7-9; mixed=4-6; bullish=8-10. Deep discount below -Band1 reduces to 3-5 |
| 3 | **关键位距离** | Distance from current price to nearest SVP key level | Within 0.3 ATR = 8-10; within 1 ATR = 5-7; far = 0-4 |
| 4 | **Taker/订单流** | Last 2 periods' taker direction and ratio | Consecutive buy >1.2 or sell <0.8 = 6-8; flipping = 3-5; mixed/no data = 0-3 |
| 5 | **OI/多空/费率** | OI trend + L/S ratio + funding rate combo | OI stable + moderate L/S (1.0-1.5) + low funding = 7-9. Extreme L/S >2.0 = 2-4 (crowded).|
| 6 | **量能充足性** | Volume of last bar vs rolling average | >70% avg = 6-8; 40-70% = 3-5; <40% = 1-2 (noisy/unreliable) |
| 7 | **多周期一致** | 4h / 1h / 15m all same direction? | All 3 align = 8-10; 2 of 3 = 5-7; 1 of 3 or flip = 1-4 |
| 8 | **反指标记** | Presence of warning flags | No conflict markers = 8-10; ⚠conflict = 3-5; X/过热 = 0-2 |

### Raw score → decision

| Raw (/80) | % | Decision |
|-----------|---|----------|
| ≥ 56 | ≥ 70% | **Push** — direction clear, multi-factor support |
| 40-55 | 50-69% | **Hold** — note in local log, don't push |
| < 40 | < 50% | **Silent** — insufficient evidence |

### Mandatory penalties (apply BEFORE threshold check)

- SVP table shows `⚠冲突` or `X`: **-15 pts**
- SVP table shows `C等待` or `等空/等多` without proximity to key level: **-10 pts**
- Taker recent window shows `neutral` (<1.1 and >0.9) with low volume: **-5 pts**
- 4h volume last 5 bars declining >40% avg: **-5 pts**

## Quick cron data sources (no external API, MCP only)

```
TV:   study_values → VWAP/EMA/VAH/VAL/POC
      pine_tables  → action table (结论·方向·进场·核对·磁吸)
      pine_labels  → key level labels
      pine_lines   → horizontal level list
      data_get_ohlcv(summary=true) → OHLC + volume stats

Binance: get_price → spot price verification
         get_open_interest_history(limit=3) → OI trend
         get_long_short_ratio → top trader L/S
         get_global_long_short → all trader L/S
         get_taker_volume(limit=3) → taker buy/sell ratio
         get_funding_rate_history(limit=3) → funding rate
```

## Scripted alternative (for no_agent cron without MCP access)

When MCP is unavailable, use `dmi_decision.py` Python DMI engine:
```python
from dmi_decision import score_market
result = score_market(
    adx=22, plus_di=18, minus_di=25,
    ema9=60182, ema21=60550, price=59945,
    vwap=63475, atr=1200, ln_oi_change=-0.001,
    ln_price_change=-0.0043, ln_taker_ratio=-0.2,
    ln_funding_change=-0.3
)
# Returns {score, direction, grade, verdict}
```

Score ≥ 70 → push. Grade X or "conflict" → silent.

## Output format for cron push

When score ≥56 and direction is clear (not X, not ⚠conflict):
```
↑↓○ {direction} BTC `{price}` · {grade}
VWAP`{vwap}` · EMA{fast}/{slow}
① 关键位：{R1/S1} · {R2/S2} · {R3/S3}
② 数据：CVD {direction} · Taker {ratio} · OI {trend}
③ 操作：{short action plan}
MEDIA:{screenshot_path}
```

## Quick Reference: SVP Action Grid → Score Mapping

| SVP Conclusion Row Text | Base Score | Notes |
|------------------------|-----------|-------|
| `A多 正常仓` / `A空 正常仓` | 9 | Clear direction, tradable |
| `B多 轻仓` / `B空 轻仓` | 7 | Partial conviction, reduce size |
| `等多 回踩` / `等空 反抽` | 5 | Waiting, no clear conflict |
| `等多 回踩 ⚠冲突` / `等空 反抽 ⚠冲突` | 3 | Conflict detected, unreliable |
| `X禁做 结构冲突` / `X禁做 过热` | 1 | Do not trade, pure conflict |

**Multi-timeframe conflict detection:**
- All 3 TFs same direction → +0 (good to go)
- 2 of 3 aligned, 1 opposite → -10 pts (ambiguous, reduce confidence)
- 4h and 15m opposite directions → -20 pts (HTF/LTF conflict, treat as high-risk)
- Any TF shows `⚠冲突` on conclusion → automatic -15 pts per conflicted TF
- X grade on any TF → automatic SILENT (even if total score ≥ 56)

## Worked Example: This Session (BTC 60,392, Score 19/80 → Silent)

**SVP Data:**
- 4h: "B空 轻仓" → score 7; penalty ⚠conflict on 1h/15m → -15
- 1h: "等空 反抽 ⚠冲突" → score 3
- 15m: "等多 回踩 ⚠冲突" → score 3
- MTF: 4h bearish vs 15m bullish = -20

**Binance Data:**
- Taker: mixed buy 2.164 / sell 0.595 / neutral 1.003 → 3
- OI: 102.8K→102.7K mild decline → 4
- L/S Ratio: 2.1 extreme long-heavy → 2 (crowded contrarian)
- Funding: 0.0014% → 7 (neutral)
- Volume: shrinking across TFs → 2

**Calculation:**
1. SVP等级: 4h=7, 1h=3, 15m=3 → avg 4 (with ⚠conflict -15 = 0)
2. VWAP/EMA: far below 4h VWAP but above 15m VWAP → 4
3. 关键位距离: between DO (60,000) and Sat High (60,925) → 5
4. Taker: mixed, no consistent direction → 3
5. OI/LS/Funding: OI↓4, L/S 2.1→2, Funding→7 → avg 4
6. 量能: shrinking → 2
7. 多周期一致: full conflict 4h⇄15m → 1
8. 反指标记: ⚠conflict on 1h+15m, L/S extreme → 0

**Raw: 0+4+5+3+4+2+1+0 = 19/80 (24%) → SILENT ✓**
This session's scoring correctly suppressed a low-confidence push.

## Testing

After changing the cron template or scoring weights, verify with:
```python
# A known B/conflict case (like this session: BTC ~60K, score 35/80)
assert score < 40, "Should be silent for B等级·⚠冲突 case"
```
