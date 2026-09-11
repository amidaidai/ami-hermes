# Cross-TF HALDRO Pattern Recognition

When HALDRO (Volume Aggregated Spot & Futures) Composite and CVD values diverge sharply across timeframes, the market is in a **cross-TF conflict** state. This is a strong no-trade signal.

## Pattern: CVD Polarity Flip

| Timeframe | CVD | Composite | Signal | Operation |
|---|---|---|---|---|
| 4h | +220M (buy accumulation) | -11 | 🔴 偏空 · 1/4共振 · 吸收 0/5 | 逆上级,不追,等回调对齐 |
| 1h | +114M (buy accumulation) | -11 | 🔴 偏空 · 1/4共振 · 吸收 0/5 | 逆上级,不追,等回调对齐 |
| 15m | -5,609 (sell dominance) | -11 | 🔴 偏空 · 1/4共振 · 去杠杆 2/5 | 别追空,等反弹 |
| 5m | -97M (sell dominance) | — | 🔴 偏空 · 4/4共振 | A空=可做 |

**Key observations from 2026-07-11 BTC session:**

1. **CVD polarity flip between 4h (+220M) and 15m (-5,609)**: The higher timeframe shows buy accumulation while the execution timeframe shows sell dominance. This is a structural conflict — neither direction has conviction.

2. **HALDRO signal row is 🔴 (red) on ALL timeframes**: The red prefix is a **warning level**, not a direction indicator. 🔴偏空 means "bearish signal with red-level warning" — the direction is unreliable. See `volume-aggregated-color-semantics.md`.

3. **Operation row diverges by TF role**:
   - 4h/1h: "逆上级,不追,等回调对齐" — structural TF says wait for alignment
   - 15m: "别追空,等反弹" — execution TF says don't chase the sell
   - 5m: "A空=可做" — trigger TF says short is actionable
   
   **Rule**: When structural TF (4h) and execution TF (15m) both say "wait/don't chase" but trigger TF (5m) says "go", the structural+execution consensus overrides the trigger. The 5m is too micro to trust alone.

4. **Composite score is identical (-11) across 4h/1h/15m**: When Composite is the same number across multiple TFs but the underlying CVD and OI components differ, the Composite is averaging out the conflict. Don't treat a stable Composite as "consensus" — decompose it.

## When to flag this pattern

- CVD polarity flips between adjacent TFs (4h vs 15m, or 1h vs 5m)
- HALDRO signal row is 🔴 (red warning) on 3+ TFs simultaneously
- Operation row on structural TF (4h) says "wait/align" while trigger TF (5m) says "go"
- Depth bid/ask ratio is extreme (>5x or <0.2x) — confirms the conflict is real, not noise

## Resolution

This pattern resolves when:
- CVD polarity aligns across TFs (all positive or all negative)
- HALDRO signal row changes from 🔴 to 🟡 or 🟢 on the execution TF
- Price breaks out of the conflict zone with volume confirmation
- One of the conflicting TFs closes a full candle beyond its key level (VAH/VAL/POC)
