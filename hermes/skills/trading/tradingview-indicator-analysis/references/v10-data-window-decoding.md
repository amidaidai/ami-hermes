# 指标svp_v10_优化版 Data Window 编码字段解码

来源：`D:/Hermes agent/svp_indicator.txt` 旧版 vs 用户实际文件 `指标svp_v10_优化版.txt` (2957行)
TV 上 indicator name = `SVP+ICT+VWAP+EMA+CVD`

## 编码字段公式（源码 2837-2871）

```
CVD Session          = round(cvdAsiaAcc/1e3)*1e6 + round(cvdLondonAcc/1e3)*1e3 + round(cvdNYAcc/1e3)
SMT Div              = smtBullDiv ? 2 : smtBearDiv ? -2 : 0
Magnet+ICT+Score     = magnetNearestPrice*1e6 + round(magnetNearestDist*1e3) + magnetScore/1e3 + ictCountEncoded/1e6
ICT Count            = ictSweptCount*100 + ictActiveCount
Magnet Score 0-100   = magnetScore (独立值)
Risk                 = RISK_PER_TRADE_PCT*10000 + DAILY_MAX_LOSS_PCT*100 + WEEKLY_MAX_LOSS_PCT
Eff Params           = effAtrStopMult*1000 + effVwapExtendedAtr*100 + effCvdWeight
Replay Side+Grade    = replaySideCode*10 + replayGradeCode
Scores               = locationScore*100 + confirmScore*10 + extensionRiskScore
```

## 解码示例

值 `58,288,003,168.1` (Magnet+ICT+Score 字段):
- magnetNearestPrice = 58,288 (取整数部分 /1e6)
- magnetNearestDist = 3.168 ATR (取 003168/1e3 = 3.168)
- magnetScore = 0 (小数部分 0.1 → 但分数需看独立 Magnet Score 字段)
- ICT Count = 106 (需看 ICT Count 独立字段)

## Scores 解码
- 130 = Loc1/Cfm3/Ext0 — 在VA内，确认分中，无延展
- 310 = Loc3/Cfm1/Ext0 — 靠近关键位，确认分低
- 330 = Loc3/Cfm3/Ext0 — 靠近关键位，确认分高
- 111 = Loc1/Cfm1/Ext1 — VA内，确认低，延展1

## 等级判定（源码 2404-2417）
- setupLongA = trendLong≥8 + 价在VWAP上 + CVD顺多 + 位移确认 + 非深溢价 + ...
- setupShortA = trendShort≥8 + 价在VWAP下 + CVD顺空 + 位移确认 + 非深折价 + ...
- setupShortB = trendShort≥6 + 关键位附近 + CVD顺空
- setupX = 过热延展 or 结构冲突 or 高周冲突

## 行动格（精简模式 源码2787-2800）
9行固定顺序: 结论 → 方向 → 进场 → 止损 → 目标 → 观察 → 核对 → 今日 → 磁吸上 → 磁吸下
- 方向 = actionBiasWord + mtfBiasText + dmiVerifyText
- 观察 = ↑/↓ + 最近磁吸位 + 距X.XATR + 守住→多/跌破接受→空 (或 扫拒→空/接受站上→多)
