# Pine Script ↔ Python 引擎参数映射 (2026-06-23 验证)

源文件: `SVP+ICT+VWAP+EMA+CVD.txt` (2024行 Pine Script v5)
验证方式: read_file 关键逻辑段 + dmi_decision.py `compute_scores()` 逐项比对

## DMI 决策表参数

| Pine 参数名 | 源码行 | 值 | Python 对应 |
|------------|--------|-----|------------|
| `DMI_ADX_SMOOTH` | 201 | 10 | `adx_smooth=10` |
| `DMI_ADX_TREND` | 203 | 20.0 | `adx >= 20.0` 判断趋势 |
| `DMI_ADX_HOT` | 204 | 40.0 | `hot = latest_adx >= 40.0` |
| `ACCEPT_BARS` | 195 | 2 | `GRADE_STABLE_BARS=2` |
| `FILTER_CVD_DIVERGENCE_BY_KEY_LEVEL` | 196 | true | `near_key_level` 门控 |
| `A_ONLY_NEAR_KEY_LEVEL` | 198 | true | `allow_a_by_location` |
| `A_KEY_LEVEL_ATR` | 199 | 0.60 | `f_near_level(atr*0.60)` |
| `CVD_KEY_LEVEL_ATR` | 197 | 0.45 | `f_near_level(atr*0.45)` |
| `GRADE_STABLE_BARS` | 200 | 2 | — |

## CVD 参数

| Pine 参数名 | 源码行 | 值 | Python 对应 |
|------------|--------|-----|------------|
| `CVD_SLOPE_LEN` | 223 | 5 | `cvdSlope = cvd - cvd[5]` |
| `CVD_DIVERGENCE_LEN` | 224 | 20 | `ta.highest(high,20)[1]` |
| `CVD_ABSORB_LEN` | 225 | 12 | `recent_12 = bars[-12:]` |
| `CVD_ABSORB_PRICE_ATR` | 226 | 0.8 | `price_range <= atr*0.8` |
| `CVD_ABSORB_DELTA_MULT` | 227 | 3.0 | `cvd < -avg_delta*3` |

## VWAP 参数

| Pine 参数名 | 源码行 | 值 | Python 对应 |
|------------|--------|-----|------------|
| `VWAP_SD_MULT_1` | 119 | 1.0 | `band1 = vwap ± atr` |
| `VWAP_SD_MULT_2` | 123 | 2.0 | `band2 = vwap ± atr*2` |
| S_VWAP 锚定 | 114 | 自动 | `tf_sec<14400→D` |

## EMA 参数

| Pine 参数名 | 源码行 | 值 | Python 对应 |
|------------|--------|-----|------------|
| `EMA_1_LEN` | 146 | 9 | `ema9` |
| `EMA_2_LEN` | 151 | 21 | `ema21` |
| `EMA_3_LEN` | 156 | 34 | `ema34` |
| `EMA_4_LEN` | 161 | 55 | `ema55` |
| 9/21 快速云 | 165-168 | — | `ema_fast_bull = ema9>ema21` |
| 34/55 慢速云 | 166-170 | — | `ema_slow_bull = ema34>ema55` |

## 评分逻辑对照

```
Pine 源码 (~line 780-950)         →  Python dmi_decision.compute_scores()
─────────────────────────────────────────────────────────────
趋势分 0-10 (ADX≥20+DI+/DI-)       →  trend_long / trend_short (0-10)
反转分 0-10 (过热/扫荡/背离)       →  reversal_long / reversal_short (0-10)
X: hot+extended+conflict+htf       →  setup_x: hot|extended|conflict|htf_conflict
A: 趋势≥8+gap≥2+CVD+位置+关键位    →  setup_long_a / setup_short_a
B: 趋势≥6+gap≥2+CVD+HTF            →  setup_long_b / setup_short_b
C: 反转≥6+gap≥2+HTF                →  setup_long_c / setup_short_c
HTF过滤: 周/月VWAP+EMA              →  htf_bull / htf_bear
TV决策表覆盖(等级/处理/背景/执行)    →  tv_grade 优先于 Python 评分
```

## 验证结果

- Pine 源码 DMI 决策引擎 (~170行评分逻辑) 与 dmi_decision.py `compute_scores()` (163行) 结构一致
- 双路径架构确认: TV MCP 决策表 > Python DMI引擎(备选)
- 所有 Pine input 参数已在 skill SKILL.md "棠溪自定义Pine参数对齐" 节记录
