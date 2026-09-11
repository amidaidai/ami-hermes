# SVP v10.1 行动栏：B/C可挂单闸门 + 风险并入结论

## 背景
用户确认：B/C 状态也可以显示成可直接挂单，但必须“确定一点的才会”；其他 B/C 仍按等待确认处理。风险行可合并到结论，减少标准档占屏。

## 行动栏规则

### 风险合并
- 标准档：不再单独显示 `风险` 行；只把最高优先级风险摘要并入 `结论`。
- 完整档：保留独立 `风险` 行，供复盘看完整风险串。
- 推荐优先级：`R:R不足 > HTF逆 > CVD冲突 > ADR耗尽/空间少 > SMT逆 > 薄量 > OI异常`。
- 示例：
  - `结论：A多 回踩 ⚠HTF逆`
  - `结论：B空 可挂 ⚠ADR空间少`

### B/C 可挂单闸门
A 单仍要求 `R:R >= 2.0`，不足时硬挡。B/C 只有满足更严格确认才显示成可挂单；否则显示等待条件。

B 多/空可挂条件：
- HTF 顺向；
- CVD 顺向且无反向 CVD 背离/吸收/派发冲突；
- 无 SMT 逆向；
- 靠近 A 级关键位；
- 有 FVG/HTF FVG、扫线收回/拒绝、MSS、VA/VWAP 接受之一；
- 非 ADR 空间不足、非薄量；
- `R:R >= 1.5`。

C 多/空小仓条件：
- HTF 顺向；
- 靠近关键位；
- 扫线收回/拒绝或 VA 站回/跌回；
- CVD 吸收/派发或 CVD 背离确认；
- 无 SMT 逆向；
- 非 ADR 空间不足、非薄量；
- `R:R >= 1.5`。

### 面板文案
- 高确定 B：`B多 可挂` / `B空 可挂`，进场显示 `挂单 <price>`，止损/目标正常显示。
- 不确定 B：`B多 等确认` / `B空 等确认`，进场显示 `等回踩...确认` / `等反抽...确认`。
- 高确定 C：`C多 小仓` / `C空 小仓`。
- 不确定 C：`C多 等站回` / `C空 等跌回`。

## 实现锚点
- 在 replay/计划价区域加入 `bcLongDirectRaw`、`bcShortDirectRaw`、`cLongDirectRaw`、`cShortDirectRaw`、`bcDirectRaw`。
- 用 `candidatePlanPrice/candidateInvalidPrice` 计算 R:R；`bcDirectOk = bcDirectRaw and rrRatio >= 1.5`。
- `executablePlan = displayLongA or displayShortA or bcDirectOk`，非可执行 B/C 的 `replayPlanPrice/replayInvalidPrice` 保持 `na`。
- `panelConclusionVal = actionStateText + 风险摘要`，标准档风险不单独渲染；完整档保留。

## 验证
- grep 关键字段：`bcDirectOk`、`panelConclusionVal`、`if panelDetailFull and panelRiskText != ""`。
- 确认 plot/request.security 数量未增加。
- 检查 Pine 单行 ternary 未跨行、引号成对。
