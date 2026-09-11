# v8.1+ Multi-Market Parameter Matrix

Complete effective-parameter values per market type for the SVP+ICT+VWAP+EMA+CVD indicator. All values are applied when `MARKET_ADAPTIVE_ENGINE = true`.

## Full Parameter Table

| Parameter | 加密 Crypto | 贵金属 Metals | 外汇 Forex | 股票 Stock | 期货 Futures | 指数 Index | 通用 |
|-----------|------------|-------------|-----------|-----------|-------------|-----------|------|
| **effCvdWeight** | +0.5 | ±0 | -0.5 | -0.5 | -0.5 | ±0 | ±0 |
| **effAKeyLevelAtr** | ≥0.75 | 0.60 | 0.50 | 0.55 | 0.55 | 0.55 | 0.60 |
| **effCvdKeyLevelAtr** | ≥0.55 | 0.45 | 0.35 | 0.30 | 0.30 | 0.45 | 0.45 |
| **effVwapExtendedAtr** | 2.0 | 1.5 | 1.2 | 1.4 | 1.4 | 1.4 | 1.5 |
| **effAtrStopMult** | 1.8 | 1.5 | 1.2 | 1.4 | 1.4 | 1.4 | 1.5 |
| **effDmiAdxTrend** | 25 | 22 | 18 | 20 | 20 | 20 | 20 |
| **effDmiAdxHot** | 45 | 42 | 35 | 40 | 40 | 40 | 40 |
| **effTrendAThreshold** | 8 | 8 | 9 | 8 | 8 | 8 | 8 |
| **effTrendBThreshold** | 6 | 6 | 7 | 6 | 6 | 6 | 6 |
| **effReversalThreshold** | 7 | 6 | 7 | 6 | 6 | 6 | 6 |

## SVP Rows

| Market | FINAL_ROWS | Rationale |
|--------|-----------|-----------|
| Crypto | max(NUM_ROWS, 70) | Wide price range needs more buckets |
| Forex | max(NUM_ROWS, 40) | Tight pip ranges, fewer buckets sufficient |
| Others | NUM_ROWS (default 50) | Balanced |

## KillZone Times (v8.1+)

| Market | London KZ | NY KZ |
|--------|-----------|-------|
| Crypto, Metals | 0700-0930 | 0820-1130 |
| Forex | 0700-0900 | 0820-1000 |
| Stock, Index, Futures | 0800-0930 | 0930-1030 |

## Action Panel Structure (Final)

```
TICKER · 看FOCUS1+FOCUS2 ⚡KILLZONE    ← headerLine
结论：A多 回踩                           ← grade + action
结构：SVP VAH上 · VWAP 上 · EMA 多      ← SVP/VWAP/EMA one-liner
确认：ICT 扫周四亚高收回 · CVD 日买盘    ← ICT event + CVD anchor
资金：亚+15K 伦-3.2K 纽~0 亚主↑        ← session CVD + direction hint
定调：偏多 · D多 · DMI顺多 · VWAP上控   ← narrative/verdict (v8.1+)
[checklist row if active plan]           ← HTF✓ EMA✓ CVD✓ 位✓
执行：多 VAL 67200等承接 · 多失效:…      ← plan + invalidation
```

### Row Details

- **资金行** (v8.1+): Session CVD three-channel via `f_fmt_cvd()`. Direction hint shows dominant session (largest |slope|) with arrow: ↑ buy, ↓ sell, → flat. Falls back to `资金：关闭` when off, `资金：—` when no data.
- **定调行** (v8.1+): Narrative synthesis. Fields: (1) bias direction from grade, (2) HTF context from `htfBiasText`, (3) DMI momentum from `dmiVerifyText`, (4) key structure from sweep state > VWAP position > VA position > EMA trend. When no setup: `定调：观望 · W多 · 等待结构确认`.
- **Label separator**: This user uses `：` (Chinese colon), NOT `｜` (pipe).

## Scoring Bonus Points

| Condition | Crypto | Metals | Forex | Stock | Futures | Index |
|-----------|--------|--------|-------|-------|---------|-------|
| Vol high + close near side | +1 | — | — | +1 | — | — |
| Swept + close above/below | — | +1 | +1 | — | — | — |
