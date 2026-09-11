# SVP+ICT+VWAP+EMA+CVD 指标评级系统速查

来源：棠溪 TV 自定义指标源码(2025行)，已存档 `svp_indicator.txt`

## 评分四通道 (各0-10分封顶)

```
trendLongScore   趋势多头 — VWAP上(+) + VAH/VA(+) + EMA多(+) + DMI顺多(+) + 量能(+)
trendShortScore  趋势空头 — VWAP下(+) + VAL/VA(+) + EMA空(+) + DMI顺空(+) + 量能(+)
reversalLongScore 反转多 — 扫低收回(3) + VAL收复(2) + VWAP延展下(2) + CVD底背离 + 吸收
reversalShortScore 反转空 — 扫高拒绝(3) + VAH拒绝(2) + VWAP延展上(2) + CVD顶背离 + 派发
```

## 评级生成 (L1876-1910)

| 等级 | 条件 | 含义 |
|------|------|------|
| **A多** | trendLong≥8, ≥trendShort+2, cvdBullConfirm, VWAP上, acceptanceOk, HTF允许, 不在过热 | 高确认做多 |
| **A空** | trendShort≥8, ≥trendLong+2, cvdBearConfirm, VWAP下, acceptanceOk, HTF允许, 不在过热 | 高确认做空 |
| **B多** | trendLong≥6, ≥trendShort+2, cvdLongOk, HTF允许 (无需VWAP上!) | 轻仓等多 |
| **B空** | trendShort≥6, ≥trendLong+2, cvdShortOk, HTF允许 (无需VWAP下!) | 轻仓等空 |
| **C反多** | reversalLong≥6, ≥reversalShort+2, HTF允许 | 反转观望 |
| **C反空** | reversalShort≥6, ≥reversalLong+2, HTF允许 | 反转观望 |
| **C等待** | 以上都不满足 | 观望 |
| **X** | DMI过热 OR VWAP延展 OR 结构冲突 OR HTF冲突 | 禁做 |

## 结构冲突源 (L1550-1554)

```
structureConflictBase = (priceAboveS AND emaBear) OR (priceBelowS AND emaBull)
structureConflictSweep = (扫低收回 AND VWAP下) OR (扫高拒绝 AND VWAP上)
structureConflictDmi = (多头结构 AND DMI偏空) OR (空头结构 AND DMI偏多)
structureConflictCvd = (多头结构 AND CVD顶背离) OR (空头结构 AND CVD底背离)
```

## CVD确认 (L799-808)

- cvdBullConfirm = CVD正在上升 + 价格涨 = 顺多确认
- cvdBearConfirm = CVD正在下降 + 价格跌 = 顺空确认
- cvdBearDiv = 价格20K新高但CVD更低 = 顶背离
- cvdBullDiv = 价格20K新低但CVD更高 = 底背离
- cvdAbsorbBuy = 价格窄幅横盘 + CVD向下出走 = 下方吸收 (反转多)
- cvdDistributeSell = 价格窄幅横盘 + CVD向上出走 = 上方派发 (反转空)

## CVD确认在评级中的权重

CVD_CONFIRM_WEIGHT 约等于2分。趋势评分每个方向最多10分。

## 状态文本映射 (L1596-1672)

SVP指标有12种状态文本用于DMI表"处理"行：
偏强修复 / 偏弱回落 / 下方修复 / 上方拒绝 / 上方接受 / 下方接受 / 上方试探 / 下方试探
VWAP-EMA一致 / 结构不一致 / ... 详见源码 L1596-1760

## 多因子分析替代方案 (当指标判X时)

1. 拆解结构冲突来源（价格 vs EMA vs CVD vs HTF）
2. 判断多空优先级（空4h+CVDS顺空 vs EMA多头+缩量+VAL近）
3. 给出倾向性判断（假跌破 vs 真突破）
4. 设置双路触发（守位做多 / 放量做空）
5. 启动多因子守护 (scripts/btc_vwap_daemon.py)
