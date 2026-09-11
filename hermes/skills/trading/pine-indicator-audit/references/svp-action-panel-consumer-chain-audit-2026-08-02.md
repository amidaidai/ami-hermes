# SVP 行动格消费链 + 时间锚审计（2026-08-02）

免费档优化版主指标（3018 行）全量审计发现的 P0 与 P1。

## P0: 行动格 CVD 行静默消失（computed-but-unused 显示端）

**症状**：`actionCvdText`（日买盘/卖盘/顶背离/底背离/吸收/派发/基差标签）被赋值 9 处，但表格行消费 **0 处**。行动格实际 9 行：结论/方向/进场/止损/目标/解除/确认/磁吸↑/磁吸↓——**没有 CVD 行**。

**后果**：
- 主指标唯一的订单流状态行（含 `基差+ 0.12% 拥挤` funding 代理标签）全白算了
- `basisLabel`（现货-永续基差）只被 `actionCvdText` 消费 → 基差功能实际没显示
- 按双指标铁律主指标是唯一裁决，但裁决面板看不到 CVD

**根因**：显示变量被计算但没接回 `f_pnl_row()`/`table.cell()`。编译通过不代表消费存在——这是"computed-but-unused"的显示端变体，比死代码更隐蔽（计算链看着完整，只是消费端没接线）。

**修法**：行动格加回一行 `f_pnl_row("CVD", actionCvdText, ...)`（插在"确认"行后），零新增计算，纯恢复消费。

**审计方法（关键）**：
```bash
grep -n "f_pnl_row(" 主指标.txt   # 列全表格行
# 对每个 computed 显示变量确认至少被一个 table 行消费：
# actionCvdText / panelDirVal / panelConclusionVal / panelEntryVal / panelStopVal / panelTgtVal / panelUnlockText
```
死代码扫描要区分两种：① 真正零引用死变量（可删）；② 被计算但不被表格消费的显示变量（需接回表格，不是删）。

## P1: 时间锚不一致（3 处）

**P1-A 日/周池时区错位**：`newDayPool = ta.change(time("D"))`（L1261）用**交易所时区**日界，而 `f_day_name_from_time` 用 `DISP_TZ`（默认北京）命名星期。Binance 加密日界 = UTC 00:00 = **北京 08:00** → 池在北京 08:00 才切换，而非北京 0 点。若用户按北京自然日理解"前日高/低"，每天前 8 小时看到的是"昨天 08:00 才开始"的池。

**P1-B 高周期锚不一致**：1h 图 SVP 锚=W、4h+ 锚=M（`autoProfileByMarket`），但池永远按 D 滚 → 两个"日"不是同一个日。

**P2-C 边界K星期错标**：`f_day_name_from_time` 用 DISP_TZ 命名交易所日界开始的时刻，边界K（UTC 23:00 = 北京 07:00）星期可能错一天。

**修法（社区验证模式，svp-anchored-trading-day-boundaries）**：池锚定跟随 SVP 锚周期——
```pine
bool newDayPool  = targetProfileTF == "D" ? isNewPeriod : ta.change(time("D")) != 0
bool newWeekPool = targetProfileTF == "W" ? isNewPeriod : ...
```
或加 `POOL_ANCHOR_TZ` 输入用 `time("D","0000-0000",tz)` 切池。优先前者（零新增 input、零配额，让池的日与 SVP 分布图的日彻底同源）。

## 死代码（23 主 + 7 副，全部零消费，可安全删）

主指标：`tfRole` `cvdReliable` `htfTfLabel` `killZoneLabel` `cvdSessionSummary` `sessionOverlapText` `npocTouchedPrice` `sweptHighAccepted` `sweptLowAccepted` `lastEventName` `eventAge` `longPlanText` `shortPlanText` `invalidSpecificText` `candidateInvalidPrice` `magnetNearestDist` `magnetAboveDist` `magnetBelowDist` `htfArrow` `execTfText` `structTfText` `bgTfText` `cvdDirectionHint`

副指标：`TTtype` `TTvol` `TTlen` `TTEX` `checkerror` `oiExpansionA` `flowTagA`

注：`execTfText/structTfText/bgTfText` 写死 "5m/15m" 却没接表格——设计成联动显示但没落地，删或接上都行。

## 本次静态扫描基线（2026-08-02 免费档优化版）

主指标：3018 行、request 9/40、plot 41、fill 2、bgcolor 1、alertcondition 0、未定义变量 none、def-before-use none、重绘信号 6（全部非重绘正确写法）。最低 plot-count 44/64。

副指标：599 行、request 展开 32/40、plot 39、alertcondition 0、未定义变量 none、重绘 1（正确）。最低 39/64。

## 模块保留裁决（2026-08-02）

保留：SVP 引擎 / POC-VAH-VAL-nPOC / 日周池（修锚）/ ICT 三通道+KillZone / 扫线状态机 / FVG+HTF / OB-Breaker+HTF / S-VWAP+周月VWAP / EMA 云 / CVD 计算链（修消费）/ 基差 / SMT / ADR / DMI / A-B-C-X / MCP DW / alert() / 副指标 OI-LSR-CVD-爆仓。
建议默认关：LV（快进快出噪声大）。
不建议加：Mitigation/Rejection/IFVG/IDM/NWOG（swing 向，免费档 2 指标+20s 限制下决策增益低）。
可选补：行动格 CVD 行（P0 修复）+ Volume Imbalance 轻量状态。
