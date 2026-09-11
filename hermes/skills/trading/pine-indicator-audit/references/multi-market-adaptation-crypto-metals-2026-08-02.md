# 多市场自适应 + calc_bars_count 截断（2026-08-02 实案）

适用：主指标 `SVP+ICT+VWAP+CVD`（加密/贵金属/外汇/股票共用的市场自适应引擎）。本文件记录两个真实教训与一套多市场模式。

## P0：`calc_bars_count` 硬编码会截断 SVP 分布图数据（实测引入又修复）

**陷阱**：给 `request.security_lower_tf` 加 `calc_bars_count=1000` 想省 intrabar 配额，却把完整分布图周期截断了。加密 5m/15m 图 D 分布图需要 **1440 根 1m intrabar**（288 根 5m × 5），`calc_bars_count=1000` 只给 1000 → **POC/VAH/VAL 缺 30% 数据算错**。4h 图 M 分布图需 1440 同样被截。

**根因**：`calc_bars_count` 的语义是「拉取 intrabar 总数上限」，必须 ≥ 一个完整分布图周期所需的 intrabar 数，否则 SVP 桶落在空数据上。免费档第一杠杆是「限制 lower-TF 拉取量」，但**不能硬编码，必须动态覆盖完整分布图跨度**。

**修法（动态计算）**：
```pine
int svpChartSec = timeframe.in_seconds(timeframe.period)
int svpCalcBars = math.max(1000,
    math.max(int(math.ceil(profSec / math.max(precSec, 1))),   // 完整分布图周期所需 intrabar
             int(math.ceil(svpChartSec / math.max(precSec, 1)))) // 单根图K内 intrabar
)
[tmpH, tmpL, tmpV] = request.security_lower_tf(syminfo.tickerid, finalPrecisionTF,
    [high, low, volume], ignore_invalid_symbol=true, calc_bars_count=svpCalcBars)
```
14 种市场×周期组合全部覆盖且仍远低于免费 100K 上限。

**验证命令**：对每种 (图周期, 分布图周期, 精度周期) 组合算 `profSec/precSec`，确认 `calc_bars_count >= 该值` 且 ≤ 100000。

**CVD 请求不同**：`array.sum` 只对当前图K内的 intrabar 求和，1000 足够，无需改。

## P1：注入变量 def-before-use 陷阱

在 620 行区域注入 calc 公式时用了 `tf_sec`，但它定义在 681 行 → `Undeclared identifier`。**注入任何变量引用前，必须确认该变量在上方已声明**（Pine 自上而下编译）。修法：公式内联 `timeframe.in_seconds(timeframe.period)`，不自作聪明复用一个后面才定义的名字。

## 多市场自适应模式（加密+贵金属重点，已验证落地）

### 贵金属 CVD 权重诚实化
现货贵金属（XAUUSD/OANDA）**无逐笔成交**，K线方向估算的 CVD 无意义。`effCvdWeight` 对 `metalSpot` 已归零（`0.0`），但行动格流向行仍输出「买盘/卖盘/背离」自相矛盾。修法：`cvdStateText` 最终输出点强制覆盖为 `"现货无逐笔"`。此时 `*Qualified` 全依赖 `effCvdWeight > 0` → 覆盖链不触发 → 诚实文本保持（闭环正确）。

### SMT 贵金属期货/现货分流
原代码 `f_is_xau_pair` 不认 `COMEX:GC1!`/`GC1!`，挂期货时 XAU/XAG 模式直接失效。修法：
```pine
f_is_xau_pair(string t) => str.contains(t,"XAUUSD") or str.contains(t,"XAU/USD") or str.contains(t,"GOLD") or str.contains(t,"COMEX:GC") or str.contains(t,"GC1!")
f_is_gc_futures(string t) => str.contains(t,"COMEX:GC") or str.contains(t,"GC1!")
// 期货 GC → COMEX:SI1!（同所同流动性池），现货 XAUUSD → OANDA:XAGUSD
smtTicker := f_is_xau_pair(stdTickerUpper) ? (f_is_gc_futures(syminfo.tickerid) ? "COMEX:SI1!" : "OANDA:XAGUSD") : stdTicker
```
**原则**：SMT 跨品种背离必须同流动性池对照；期货 vs 现货分开，否则背离误报。

### Funding 代理：现货-永续基差
**Pine 无读取资金费率（funding rate）的官方 API**（funding 只能走 Binance fapi/Coinglass 外部接口）。Pine 内可执行的等价方案 = **现货 vs 永续价差（basis）**：正基差=永续溢价=多头拥挤≈正 funding，社区公认代理。

```pine
string spotTicker = marketCrypto and isPerp ? str.replace(syminfo.tickerid, ".P", "") : ""
float perpSpotBasisPct = na
if SHOW_SPOT_PERP_BASIS and spotTicker != ""
    float spotRefClose = request.security(spotTicker, timeframe.period, close, ignore_invalid_symbol=true)
    if not na(spotRefClose) and spotRefClose > 0
        perpSpotBasisPct := (close - spotRefClose) / spotRefClose * 100
float basisEma = na(perpSpotBasisPct) ? na : ta.ema(perpSpotBasisPct, 20)
```

**市场隔离铁律**：`spotTicker` 只在 `marketCrypto and isPerp` 非空 → 贵金属/外汇/股票/加密现货一律空 → basis=na → 标签空串 → 行动格无基差，零副作用。加密现货无资金费率也应隐藏（isPerp=false → 正确）。

**行动格标签追加位置**：必须放到覆盖链**末尾**（`actionCvdText := actionCvdText + cvdRefTag` 之后），否则被 `cvdAbsorbBuyQualified` 等分支重建文本时丢弃。Data Window 导出 `perpSpotBasisPct*10000`（bp 单位）供 MCP 消费，不占绘图预算外的槽。

**注意**：验证「市场隔离」要用逻辑推演（spotTicker 空串→na→空标签），不要用字符串匹配（`'basisLabel' in file` 恒真，是误报）。

## 市场自适应引擎已具备（审计时确认存在，勿重复建议）
- 9 种市场预设 + 自动识别（`syminfo.type` + 前缀）
- 贵金属：XAU/XAG/GOLD/SILVER/GC1!/SI1! 识别、现货vs期货区分
- 加密：7x24 会话、CVD 权重 +0.5
- 参数自适应：ATR 止损倍数、ADX 阈值、KillZone 时间窗、分布图行数、桶宽 tick 倍数、ADR 周期全按市场调
- SMT 配对：BTC/ETH、BTC/DXY、XAU/XAG、XAU/DXY

## 免费档配额现状（2026-08-02 实测）
- 免费 Basic：0 技术告警 / 5000 历史K / 20s 计算 / 2 指标·图 / 100K intrabars / 40 request / 64 plot
- 主指标改后：44/64 plot、9/40 request、0 alertcondition
- 副指标改后：39~54/64 plot、展开 32/40 request、0 alertcondition
- Footprint 需 Premium+（排除，另做独立脚本）
