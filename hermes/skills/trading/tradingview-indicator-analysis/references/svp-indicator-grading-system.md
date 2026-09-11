# SVP+ICT+VWAP+EMA+CVD 指标评级系统速查

> 来自对棠溪 2025 行 Pine Script 源码的逆向分析（2026-06-22）
> 源文件：`svp_indicator.txt` (2025 lines)

## 四维评分体系（每维 0-10，截断）

| 评分轴 | 满分 | 说明 |
|--------|------|------|
| trendLongScore | 10 | 趋势偏多强度 |
| trendShortScore | 10 | 趋势偏空强度 |
| reversalLongScore | 10 | 反转做多强度 |
| reversalShortScore | 10 | 反转做空强度 |

## trendShortScore 计分细则

```
priceBelowS  ? +2  (价格低于S VWAP)
priceBelowVal? +2  (价格低于VAL)
priceInVA    ? +1  (价格在VA内，含上方)
emaBear      ? +2  (EMA9 < EMA21)
dmiBearConfirm? +2 (DMI顺空确认)
volHigh + closeNearLow ? +1
marketCrypto + volHigh ? +1
cvdBearConfirm ? +CVD_CONFIRM_WEIGHT (~2)
cvdBullDivQualified ? -CVD_CONFIRM_WEIGHT (~-2)
```

## 等级判定（L1876-L1910）

### 常用等级

| 等级 | 条件 | 含义 |
|------|------|------|
| **A空** | trendShortScore≥8 且 ≥trendLongScore+2 且 cvdBearConfirm 且 priceBelowS 且 acceptanceBearOk 且 htfAllowShort 且 allowAByLocation 且 NOT dmiHot | **高置信做空信号** |
| **B空** | trendShortScore≥6 且 ≥trendLongScore+2 且 cvdShortOk 且 htfAllowShort 且 NOT setupShortA | 中等置信，需等进一步确认 |
| **C反空** | reversalShortScore≥6 且 ≥reversalLongScore+2 且 htfAllowShort | 反转信号，非趋势 |
| **C等待** | 以上都不满足 | 观望 |
| **X** | dmiHot OR vwapExtendedUp/Dn OR structureConflict OR htfConflict | 禁止交易 |

### A空 完整条件链

```
trendShortScore ≥ 8
AND trendShortScore - trendLongScore ≥ 2  (gap)
AND cvdBearConfirm (CVD顺空确认)
AND priceBelowS (价格在S VWAP下方)
AND acceptanceBearOk (价格持续在S VWAP下方+VAL下方/VA内)
AND htfAllowShort (NOT htfBull, 即高周期不能偏多)
AND allowAByLocation (价格靠近关键位)
AND NOT dmiHot (DMI未过热)
```

### B空 条件链（更宽松）

```
trendShortScore ≥ 6
AND gap ≥ 2
AND cvdShortOk (= cvdBearConfirm OR cvdBearDiv OR NOT cvdRising)
AND htfAllowShort
AND NOT setupShortA
```

### 稳定化机制

```
等级不是单根K线决定。A/B级需要 GRADE_STABLE_BARS 根K线确认才正式输出。
X级立即生效（有风险就即刻禁做）。
```

## 核心状态判定（L1542-L1564）

```
bullStructureRaw = (扫低收回 AND priceAboveS) OR vahAccepted OR trendOkBull
bearStructureRaw = (扫高拒绝 AND priceBelowS) OR valAccepted OR trendOkBear
bullValidated   = bullStructureRaw AND NOT dmiBullAgainst AND NOT dmiTrendWeak AND cvdLongOk
bearValidated   = bearStructureRaw AND NOT dmiBearAgainst AND NOT dmiTrendWeak AND cvdShortOk
structureConflict = 价格与EMA冲突 OR 扫荡与S方向冲突 OR DMI矛盾 OR CVD背离
```

## CVD 确认逻辑（L799-L808）

```
cvdBearConfirm = cvdFalling AND close ≤ close[CVD_SLOPE_LEN]
cvdBullConfirm = cvdRising AND close ≥ close[CVD_SLOPE_LEN]
cvdBearDiv = 20K内 high新高 AND CVD未新高 → 顶背离
cvdBullDiv = 20K内 low新低 AND CVD未新低 → 底背离
cvdAbsorbBuy = 窄幅震荡 + CVD大幅下降 + 价格在下半区 → 机构吸收
cvdDistributeSell = 窄幅震荡 + CVD大幅上升 + 价格在上半区 → 机构派发
```

状态文本映射：
```
顺空确认 → bear confirmed
顺多确认 → bull confirmed
顶背离 → bear divergence
底背离 → bull divergence
上方派发 → distribution sell
下方吸收 → absorption buy
卖盘回落 → falling (no price confirm)
买盘回升 → rising (no price confirm)
```

## DMI 方向检测（L1400-L1411）

```
dmiBull  = +DI > -DI AND NOT dmiBalance (ADX≥20且gap>3)
dmiBear  = -DI > +DI AND NOT dmiBalance
dmiHot   = ADX ≥ 40 (过热禁追)
dmiBullConfirm = dmiBullPath OR (dmiBull AND ADX未降)
dmiBearConfirm = dmiBearPath OR (dmiBear AND ADX未降)
dmiVerifyText = 过热/顺多/顺空/走弱/待定
```

## DMI 决策表字段含义（简洁模式8行）

| 行 | 字段 | 来源 |
|----|------|------|
| 等级 | A多/A空/B多/B空/C等待/X | setupGradeStable |
| 处理 | 回踩做多/反抽做空/观望/禁追/... | treatmentText |
| 背景 | 多/空/震荡 + TF (如"空4h") | htfBiasText |
| 位置 | VAH上方/VA内｜上方控制/... | structureShortText |
| 量能 | 放量上收/放量下收/量能普通/... | volumeMiniText |
| CVD | 顺空确认/顺多确认/顶背离/... | cvdStateText |
| 执行 | 多:回踩XX / 空:破XX | focusedPlanText |
| 风控 | 多失效:... / 空失效:... | invalidSpecificText |

## 快速理解卡片

当 TV DMI 表显示：
```
等级 | C等待
处理 | 观望
背景 | 空 4h
位置 | VA内｜上方控制
CVD  | 顺空确认
执行 | 多:回踩VWAP 64235｜空:破VWAP 64235
```

解读：
- **市场在等价格选方向** — 价格在VA内且贴VWAP，哪边先破哪边走
- **高周偏空**（空4h）— 限制做多
- **CVD已经确认卖压**（顺空确认）— 空的条件已有之一
- **等跌破VWAP** 触发完整做空条件

## 评分兜底

> 从脚本Python实现评分时，因子满分为趋势评分10分(A级要求≥8)、反转评分10分(C反级要求≥6)。
> 单因子权重固定：价格位置=2, EMA=2, DMI=2, CVD≈2, 量能=1。
> 关键区别：A空额外要求 cvdBearConfirm + acceptanceBearOk + priceBelowS——不仅是分数够。
