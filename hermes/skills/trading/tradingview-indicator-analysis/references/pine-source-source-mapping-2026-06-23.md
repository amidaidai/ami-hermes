# Pine Script 源码对齐映射 (2026-06-23)

棠溪 2026-06-23 上传了两个 Pine Script 源文件，作为系统调参的唯一权威源。

## 文件清单

| 文件 | 行数 | 用途 |
|------|:----:|------|
| `CVD.txt` | 28 | 简单累计成交量差(CVD)蜡烛图可视化 |
| `SVP+ICT+VWAP+EMA+CVD.txt` | 2024 | 主指标：DMI决策表+SVP分布图+ICT会话+VWAP+EMA云+CVD背离 |

## CVD.txt 源码解读

纯视觉指标，用 `ta.requestVolumeDelta` 计算量差，蜡烛可视化（teal=买盘, red=卖盘）。
- 无自定义参数，无信号逻辑 — 只是看图用的可视化层
- 通过TV MCP `study_values` 读取即可，无需本地复现

## SVP+ICT+VWAP+EMA+CVD.txt 参数对齐

### VWAP
| Pine参数 | 值 | 本地引擎对应 |
|----------|:--:|-------------|
| `VWAP_SD_MULT_1` | 1.0 | `band1_high/band1_low` (VWAP ±1σ) |
| `VWAP_SD_MULT_2` | 2.0 | `band2_high/band2_low` (VWAP ±2σ) |
| `S_VWAP_ANCHOR` | 自动(日/周/月) | 15m以下=日, 1-4h=周, 4h+=月 |
| `SHOW_VWAP_BANDS` | true | 读取 `S VWAP Band 1 High/Low` |

### EMA
| Pine参数 | 值 | 本地引擎对应 |
|----------|:--:|-------------|
| `EMA_1_LEN` | 9 (快速) | `ema9` |
| `EMA_2_LEN` | 21 (快速) | `ema21` |
| `EMA_3_LEN` | 34 (慢速) | `ema34` |
| `EMA_4_LEN` | 55 (慢速) | `ema55` |
| `SHOW_EMA_12_CLOUD` | true | EMA9/21云(金叉/死叉判断) |
| `SHOW_EMA_34_CLOUD` | true | EMA34/55云(趋势强弱) |

### CVD
| Pine参数 | 值 | 本地引擎对应 |
|----------|:--:|-------------|
| `CVD_SLOPE_LEN` | 5 | `cvd_slope` (正=买盘, 负=卖盘) |
| `CVD_DIVERGENCE_LEN` | 20 | 价格vsCVD背离判断窗口 |
| `CVD_ABSORB_LEN` | 12 | 吸收/派发观察K数 |
| `CVD_ABSORB_PRICE_ATR` | 0.8 | 吸收时价格压缩阈值(ATR倍数) |
| `CVD_ABSORB_DELTA_MULT` | 3.0 | 吸收时CVD变化倍数 |
| `CVD_CONFIRM_WEIGHT` | 1.0 | CVD评分权重 |

### DMI 决策表
| Pine参数 | 值 | 本地引擎对应 |
|----------|:--:|-------------|
| `DMI_ADX_SMOOTH` | 10 | `adx_smooth` (Wilder平滑) |
| `DMI_ADX_TREND` | 20.0 | 趋势阈值(ADX≥20=趋势, <20=盘整) |
| `DMI_ADX_HOT` | 40.0 | 过热阈值(ADX≥40=过热禁追) |
| `ACCEPT_BARS` | 2 | A级需连续确认K数 |
| `GRADE_STABLE_BARS` | 2 | 升级所需稳定K数 |

### 关键位
| Pine参数 | 值 | 本地引擎对应 |
|----------|:--:|-------------|
| `A_KEY_LEVEL_ATR` | 0.60 | A级须在关键位ATR×0.60内 |
| `CVD_KEY_LEVEL_ATR` | 0.45 | CVD背离须在关键位ATR×0.45内 |
| `A_ONLY_NEAR_KEY_LEVEL` | true | 非关键位位置最多B级 |
| `FILTER_CVD_DIVERGENCE_BY_KEY_LEVEL` | true | CVD背离过滤 |

### DMI 评分规则 (2024行 Pine源码复现逻辑)

```
趋势分 0-10 计算:
  +2 price_above_s(VWAP上方)
  +2 price_above_vah 或 price_in_va
  +2 ema_bull(9>21 AND 34>55)
  +2 dmi_bull_confirm(ADX上升+DI+>DI-)
  +1 vol_high + close_near_high
  +1 MTF VWAP(price_above_w AND price_above_m)
  +1 killzone_active
  +triple_confirm_bonus(OB/FVG/Sweep)
  +cvd_bull_confirm
  -cvd_bear_div

等级判定:
  X = hot(ADX≥40) OR extended(>1.5 ATR from VWAP) OR
      conflict(priceAboveS AND emaBear) OR htf_conflict
  A = trend≥8 AND gap≥2 AND cvd_confirm AND position OK
      AND htf_allow AND near_key_level AND NOT hot
  B = trend≥6 AND gap≥2 AND cvd_ok AND htf_allow AND NOT A
  C = reversal≥6 AND gap≥2 AND htf_allow
```

## 优先级

TV MCP 直读的 DMI 决策表（通过 `data_tables` CLI 获取）是**真理源**，本地Python引擎(`dmi_decision.py`)只在 TV MCP 不可用时作为后备。

## 验证方法

上传新 Pine Script 后，执行：
1. `read_file` 提取参数值
2. 对比 `dmi_decision.py` 和 `vwap_ema_cvd_engine.py` 的参数
3. 运行 `python scripts/dmi_decision.py --verify` (需存在验证模式)
4. 运行 `python scripts/monitor/btc_card_gen.py` 验证TV MCP读取是否正确
