# v3.5 Alert Card Format — 分层可读短信风格 + 作战建议

Adopted 2026-06-22. Replaces old `↑做多 | Model: reason (conf:%)` format with hierarchical
`+/−/~` markers, grouped by direction, self-contained for push passthrough.
v3.5 adds actionable next-step guidance at the bottom.

## Format Template

```
══ BTC · {price} · VWAP {vwap} · {HH:MM CST} ══
综合: {grade} {偏多/偏空/中性} (多{N} vs 空{M}){★高胜率}
  {one-line warning sentence ≤40 chars}

  + {model} → {reason} · {conf}%
  - {model} → {reason} · {conf}%
  ~ {model} → {reason}

关键位: VWAP {v} · VAH {h} · VAL {l} · B2上 {h} · B2下 {l}
指标: CVD {+/-n} · Taker {r} · OI {k}K

下一步: {actionable guidance — which level, what to do, contingency}
```

## Filter Rules (ORDER MATTERS)

The filter pipeline in `write_pending()` must check in this exact order:

0. **Grade Gate (v3.6+)** — After building the `active` list, extract the confluence alert. If `priority not in ("A+", "A")`, return 0 immediately. B/C/D grades → no pending file written → push cron silent. This is the FIRST check after filtering — before any formatting or grouping. A+ = total_w ≥ 8 (3+ strong signals aligned), A = total_w ≥ 6 (2+ strong signals aligned, no contradiction). This enforces the 80%+ confidence threshold.
1. **Cooldown** — same model within 15min → skip (unless A+)
2. **Confluence always pass** — `is_confluence=True` → add to active and continue (MUST check BEFORE conf filter to avoid self-filtering)
3. **Priority D** → skip
4. **Conf < 0.35** → skip (this kills KillZone's 0.30 conf noise)
5. **Neutral one-shot** — `○等待/○监测` → only push once, then cooldown permanently

## One-Line Summary Rules (_gen_summary)

Max ~40 chars. Natural flowing sentence, NOT dash-separated chains.
Priority-ordered condition ladder:

| Condition | Pattern | Example |
|-----------|---------|---------|
| 偏多 + B2突破 + Taker背离 | Contradiction alert | `多头控盘但Taker卖压(0.6)，关注B2(64,474)能否守稳` |
| 偏多 + B2突破 + SilverBullet | Window + level | `站上B2(64,474)，银弹窗临，关注14-15UTC突破确认` |
| 偏多 + B2突破 only | Clean breakout | `站上B2(64,474)，多头控盘，回踩XX上方做多` |
| 偏多 + CVD only | Flow-driven | `CVD强买支撑，守VWAP(64,201)上方偏多` |
| 偏空 + B2跌破 | Breakdown | `失守B2(63,928)，空头加速，关注VWAP(64,201)支撑` |
| 偏空 + CVD+Taker双卖 | Double sell pressure | `CVD+Taker双卖压，若破VWAP(64,201)则空头确认` |
| 中性 + SilverBullet | Wait for window | `多空均衡，银弹窗(14-15UTC)待选方向，观望为宜` |
| 中性 + KillZone | Range + active zone | `价格XX贴VWAP(64,201)拉锯，KillZone活，等突破` |

Warning keywords: 关注 / 谨慎 / 警惕 / 注意 / 观望

## Next-Step Guidance (_gen_next_step)

Added v3.5. Tells the trader exactly what to watch and what to do.
Two-part structure: "Action → Contingency".

### Level Selection

- **nearest_support**: closest level BELOW price (B2上 > VWAP > B2下 > VAL)
- **nearest_resist**: closest level ABOVE price (VAH > B2上 > B2下)
- Both B2上 and B2下 must appear in BOTH lists (can be above or below depending on price)

### Direction Logic

| Dominant | Pattern | Example |
|----------|---------|---------|
| 偏多 | 守{w}做多看{t}。破{w}止损；站上{t}加仓 | `守B2上(64,474)上方做多，目标新高(>65,046)。若破B2上(64,474)止损观望；若站上新高(>65,046)加仓` |
| 偏多+Taker背离 | 关注{w}守稳。守稳做多{t}；失守减仓 | `多头控盘但Taker背离(0.6)，关注B2上(64,474)能否守稳。守稳做多看新高(>65,046)；失守则减仓` |
| 偏空 | 守{w}做空看{t}。站回{w}止损；破{t}加速 | `守VWAP(64,201)下方做空，目标VAL(63,894)。若站回VWAP(64,201)止损；若跌破VAL(63,894)空头加速` |
| 中性+SilverBullet | 观望。上破X做多，下破Y做空 | `银弹窗(14-15UTC)内观望。上破B2上做多，下破VWAP(64,201)做空` |
| 中性+拉锯 | 上破X做多，下破Y做空，区间观望 | `价格65,046拉锯。上破VAH做多，下破B2上做空，区间内观望` |

## Data Formatting

| Field | Format | Example |
|-------|--------|---------|
| Price | `{price:,.0f}` | 65,157 |
| VWAP | `{vwap:,.0f}` | 64,201 |
| CVD | `{cvd:+,.0f}` | +16,287 or -3,368 |
| Taker | `{taker:.2f}` | 2.02 or 0.69 |
| OI | `{oi/1000:,.0f}K` | 102K |

## Signal Reason Formatting

Keep reasons short — no redundant field names, minimal punctuation:
- `价65,046>B2上64,474` not `价格65370>+B264474·>VWAP64201`
- `+16,287·斜率+3,219` not `CVD+16287·斜率+3219`
- `0.56卖方主导` not `Taker0.56·卖方碾压`

## Push Pipeline

Detector (`btc_alert_watch_v3.py`) → writes `btc_pending.txt` (self-contained card) →
Pusher (`btc_push_cron.py` v6) → reads, chunks to 3900 chars, sends via `telegram_direct` →
Truncates pending.

Pusher does NO format processing — the detector output is final Telegram-ready format.

## Common Bugs & Fixes

| Bug | Symptom | Fix |
|-----|---------|-----|
| Confluence self-filtering | Grade shows `?` | Check `is_confluence` BEFORE conf filter |
| OI showing 0M | Real OI is 101K | Use `oi/1000` not `oi/1e6` with `:.0f` |
| "上破B2上" when above B2 | Price > B2, says break upward | B2 must be in `levels_below` when price > B2, not just `levels_above` |
| Data re-load race | OI or other fields vanish | Pass `data` dict as parameter to `write_pending()`, don't re-call `load_data()` |
