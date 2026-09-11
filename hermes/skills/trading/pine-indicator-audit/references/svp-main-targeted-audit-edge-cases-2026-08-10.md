# SVP 主指标定向深审边界案例（2026-08-10）

适用于大型 Pine v6 主指标的市场判定、锚定、事件告警、nPOC、行动格、MCP Data Window 与深色主题复核。

## 1. 市场身份必须拆成两个维度

不要让一个 `activeMarket` 同时决定“资产类别”和“交易时制/数据能力”。典型反例：`BINANCE:XAUUSDT.P` 是黄金资产，但也是 7×24 的 crypto/perpetual 数据源。

至少分别保存：

- `assetClassMetal / Forex / Stock / Index / ...`
- `tradingVenueCrypto / isPerp / hasMeaningfulVolume / tradesWeekend`

审计断言：

- `contains("GOLD")/contains("SILVER")` 不得覆盖已确认的 `syminfo.type == "stock"`（如 `NYSE:GOLD`）。
- 官方 `syminfo.type == "option"` 必须有明确分支；不能仅靠 ticker 中的 `CALL/PUT`。
- 若同时支持 `.P` 和 `PERP`，现货映射必须分别处理，且断言 `spotTicker != syminfo.tickerid`；否则基差会退化为永续对自身。

## 2. 锚定审计必须输出完整矩阵

逐格比较 `market × chart timeframe × SVP/S VWAP/CVD`，至少覆盖：

- `<1h`
- `1h–<4h`
- `4h–<1D`
- `1D+`

任何“有意分叉”都必须由代码旁合同说明；不能只说明 `1D+ SVP=12M`，却遗漏股票/金属/外汇/期权的其他分叉。

额外检查：当 `targetProfileTF == chart TF` 时，若完成逻辑要求 `endBar > startBar`，单 K Profile 会被丢弃。数值计算与零宽度绘图应分离。

## 3. CVD pivot 合同

两个 price pivot 只有在以下快照都兼容时才可比较：

- anchor 实例 ID 相同；
- 两个 pivot 当时的 CVD 方法相同或明确允许混用；
- 两个 pivot 当时的 sample/quality 均达标。

仅在当前 K 检查 `cvdQualityOk` 不足以认证历史 pivot。

## 4. nPOC 触碰冻结

- `approachSide` 必须在触碰前冻结，不能用触碰 K 自己的 `close` 生成；否则“收回确认”可能变成由结果反推方向的同 K 自证。
- tooltip 写“触碰后立即停止”时，默认模式不能仍是“收盘即扫”。
- `NPOC_LIMIT` 应按 active/unswept 对象治理；已扫/隐藏历史对象不能挤掉仍有效的 nPOC。

## 5. 告警事件化

禁止只对 `eventA or eventB or ...` 的聚合布尔做一次边沿检测。只要 A 持续为真，期间新发生的 B 会被吞掉。

优先方案：

1. 每种事件独立 `event and not event[1]`；
2. 或维护事件 bitmask/快照差集；
3. 同一 K 多事件拼成组合消息，而不是单条三元优先链丢弃其余事件。

## 6. 行动格一致性敌对场景

必须构造并核对：

- `readiness>=70` 但 geometry 无效；
- `readiness>=70` 但 R:R 不足；
- trigger 过期或未收线；
- 已显示“挂单”，路径仍写“等 MSS/等回踩”；
- B/C 人工候选 R:R=1.2/1.5/2.0；
- 无多空计划且附近只有 nPOC；
- OI 行开关关闭后是否真正移除整行。

`readiness` 必须被 geometry、R:R、trigger freshness、bar confirmation 和硬风险覆盖。`visiblePlan` 不得使低于最低 R:R 的 B/C 导出完整 Entry/Stop/Target 合同。

## 7. MCP Data Window 真值与单位

- 方法码必须描述实际采用路径：lower-TF 数组为空并回退 bar estimate 时，不得仍输出 lower-TF。
- 百分数转 bp：若变量已经乘过 `100` 成为百分数，转 bp 只再乘 `100`，不是 `10000`。
- Pack 必须使用固定宽度或独立字段；类似 `10000 + 300 + 600` 的相加无法无歧义还原三个风险参数。
- 输出字段总数、标题、单位、sentinel（不可用值与真实 0）必须逐项登记。

## 8. Plot 配额与死代码扫描

不要使用仅匹配行首的 `^\s*plot\(`：它会漏掉 `pEma = plot(...)`。应扫描任意代码位置的独立函数调用，并同时计入：

- `fill()`（series color 时占 plot count）
- `bgcolor()`
- `alertcondition()`
- series-color 产生的额外计数

死变量扫描除 primitive typed declarations 外，还要扫描 UDT `type` 字段：字段可能被初始化和反复写入，却从未通过 `.field` 读取。

## 9. 深色主题快速验收

以常见 TV 深色背景 `#131722` 做默认对比检查，并把透明背景先与图表背景合成后再计算文字对比度。特别检查：

- POC/DO/前日池等线色；
- 行动格默认主题是否与图表主题相反；
- 标签色在半透明行背景上的实际对比，而不是只比较未合成的十六进制颜色。
