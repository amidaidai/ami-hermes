# Volume Aggregated Sub-Indicator Color Prefix Semantics

## The Problem

When reading the Volume Aggregated Spot & Futures sub-indicator's `pine_tables`, the first row is:

```
信号 | 🔴偏多·1/4共振
```

The 🔴/🟡/🟢 **prefix is a WARNING LEVEL, NOT a direction indicator**. This is counter-intuitive and was observed to cause scoring errors in real sessions.

## Color → Meaning Mapping

| Prefix | Meaning | Action Signal |
|--------|---------|---------------|
| 🔴 红色 | Bearish warning / Caution | The direction that follows is unreliable or a contrarian signal. Usually paired with "降级/放弃" in the action row. |
| 🟡 黄色 | Neutral / Moderate | Direction has some resonance but not full conviction. |
| 🟢 绿色 | (rare on crypto — usually on strong moves) | Confirmatory signal. |

## Real Examples from Session (2026-06-28 BTC Cron)

### 4h TF Sub-Indicator
```
信号 | 🔴偏多·1/4共振
结论 | 涨势存疑·CVD不配,别急追
操作 | 主指标即便给多也降级/放弃
```
- `🔴偏多` = **Caution**: The indicator is showing a bullish signal (偏多) but with RED warning — this is NOT a bullish endorsement.
- Only 1/4 resonance (weak).
- Action says "降级/放弃" — confirm the 🔴 is a downgrade signal.
- **Correct interpretation**: The 🔴偏多 means "weak bullish signal under bearish conditions — do not act on it."

### 15m TF Sub-Indicator
```
信号 | 🟡偏空·2/4共振
结论 | 逆高周·短空但高周偏多,降级
操作 | 逆高周,不追,等回调对齐
```
- `🟡偏空` = Moderate bearish signal with 2/4 resonance.
- Higher timeframe (HTF) is marked ▲偏多 — creating a time-frame conflict.
- Action says "降级 / 不追" even though the short-term direction is bearish.
- **Correct interpretation**: Short-term bearish is acknowledged but downgraded due to HTF conflict.

## Why This Matters for Scoring

In the 10-factor cron scoring rubric (Factor 5: Sub-indicator Verdict):

- `🔴偏多·1/4共振` → The direction text says "偏多" but the 🔴 + 1/4 resonance + "降级/放弃" action means it should score **2-3** (downgrade/abandon zone), NOT 7-8 (bullish direction).
- `🟡偏空·2/4共振` → The 🟡 + 2/4 resonance means it should score **3-5** (moderate bearish, with downgrade caveat).

**Rule**: When scoring Factor 5, ignore the literal direction word after a 🔴 prefix — look at the 结论/操作 rows for the real verdict. Only trust the direction word when the prefix is 🟢 (green) or the signal row is clean (no color prefix).

## Cross-TF Confusion Pattern

A common confusing pattern (observed in this session):

| TF | Main SVP Indicator | Sub-Indicator (Volume Aggregated) |
|----|-------------------|-----------------------------------|
| 4h | 等空 反抽 (bearish) | 🔴偏多·1/4 → 降级/放弃 |
| 15m | 等空 反抽 (bearish) | 🟡偏空·2/4 → 逆高周,降级 |

The main SVP consistently says "等空 反抽" (bearish-waiting). The sub-indicator seems to contradict on 4h ("偏多") but its 🔴 prefix means it's actually a caution signal, not a true bullish call. The 4h and 15m sub-indicators are **not** in conflict with each other or with the main SVP — they're both saying "bearish, downgrade."

**Do NOT interpret `🔴偏多` as a bullish vote in the MTF alignment assessment (Factor 3).** Only use the SVP main indicator's action grid for direction; the sub-indicator's color-prefixed direction is a quality modifier, not a directional signal.

## 跨TF Composite 分数不一致（2026-06-30 实战发现）

Volume Aggregated 在 study_values 中输出 `Composite` 行。**同一个品种在不同时间框架上的 Composite 可能方向相反**，这是一个重要的矛盾点：

| 周期 | Composite | 解读 |
|:--:|:--:|:--|
| 4h | -21 | 中周期整体偏空 |
| 15m | +21 | 短周期情绪转正 |
| 5m | +21 | 超短周期同样偏正 |

**处理方法**：
- 这种「高周负 / 低周正」的分裂在下跌行情中常见——短周期超卖反弹尝试 vs 中周期趋势仍空
- 写入分析卡的「矛盾点」段，不编辑任何一边
- 策略上：4h Composite=-21 压制约 15m 的+=+21，做多只能短线，主流倾向仍偏空

信号优先级：4h Composite > 15m Composite。小周期 Composite 可能只是下跌中的反弹脉冲。

When analyzing BTC/XAU across TFs and reading the sub-indicator:
1. Read the **操作 row** ("降级/放弃" / "不追,等回调对齐") — this is the real verdict
2. Check the **共振 count** (1/4 vs 2/4 vs 3+/4) — higher is more reliable
3. Ignore 🔴/🟡 prefix direction words for directional scoring; use them only for quality adjustment
4. The sub-indicator's HTF direction (高周 row) tells you which way the higher timeframe is leaning — if it conflicts with the SVP main indicator's 4h direction, note it as a conflict warning
