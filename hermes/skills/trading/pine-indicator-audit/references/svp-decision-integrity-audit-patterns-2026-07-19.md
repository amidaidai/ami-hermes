# SVP 决策完整性审计模式（2026-07-19）

适用于大型 Pine v6 Volume Profile + ICT + CVD + Magnet + 行动格指标。以下问题能通过编译与常规配额扫描，却会改变交易裁决。

## 1. 当前 Profile 的历史/实时同构

危险模式：

```pine
if barstate.islast
    engine.processAndRender(startBar, bar_index, true)
float curPoc = engine.lastPocPrice
```

如果引擎每根历史K只存数据，却只在 `barstate.islast` 计算当前 POC/VAH/VAL，那么：

- 实时最后一根K会动态更新当前 Profile；
- 历史K仅看到上一已完成 Profile 或 `na`；
- 重载、回放、MCP历史读取与实时行动格不一致。

审计必须沿 `store* → process/calculate → lastPoc/lastVah/lastVal → setup/grade/MCP` 全链追踪。正确架构是把**数值计算**与**对象绘制**分离：数值每根K确定性更新；polyline/box/label 可仅在 `barstate.islast` 绘制。

## 2. Value Area 以 TradingView 当前官方“不得超过剩余目标量”口径为准

TradingView 当前官方 Volume Profile 文档明确：从 POC 开始，比较上下候选行；若加入较大候选行会超过剩余目标量，则停止，VA 完成。不要再沿用“必须纳入使累计量首次达到/超过阈值的整桶”这一旧假设。

审计危险模式：

```pine
while currentValueAreaVolume < threshold
    currentValueAreaVolume += candidateVol
    boundary += direction
```

若没有在加桶前检查 `current + candidate <= threshold`，实现会超过官方 VA 口径，使 VAH/VAL 变宽。此问题不改变 POC/nPOC 本身，但会污染接受/拒绝、位置和评分。若目标是其他平台或自定义“首次超过”算法，必须显式标为自定义口径，不能称为 TradingView 官方一致。

## 3. R:R 不能用绝对值掩盖方向错误

仅计算：

```pine
risk = math.abs(entry - stop)
reward = math.abs(target - entry)
```

不足以证明计划有效。执行前必须验证：

- 多单：`stop < entry < target`
- 空单：`target < entry < stop`

随后才计算有符号 R:R。止损 ATR 距离也必须按 `abs(entry-stop)`，不能按 `abs(close-stop)`。

## 4. 行动格、MCP、提醒必须共享唯一执行价格

常见错位：R:R/MCP 使用 `candidatePlanPrice`，行动格却按优先级显示 FVG CE、扫线价、VAH/VAL 或吸收价。这样屏幕上的进场价与旁边止损、目标、R:R不是同一计划。

审计时建立价格口径表：

| 消费端 | Entry | Stop | Target | R:R |
|---|---|---|---|---|
| 行动格 | | | | |
| MCP Data Window | | | | |
| alerts | | | | |
| replay/backtest | | | | |

四端应读取同一 `finalEntry/finalStop/finalTarget`。

## 5. 扫线必须只有一个状态机

若绘图线条使用 `SWEEP_MARK_MODE + barstate.isconfirmed + closeReclaim`，但决策事件另行用 `sameBarTouch or gapThrough`，会产生：

- 图上未标已扫，评分却已把它当扫线；
- “收回确认”被绕过；
- 当前K行动格闪变；
- 已扫水平再次穿越时重复生成新事件。

事件引擎应消费统一的 `newlySwept/reclaimed/accepted`，并检查 `not alreadySwept`。

## 6. CVD质量门控必须贯穿全部消费端

定义了 `cvdQualityOk` 与 Qualified 信号，不代表门控已经完成。必须继续检查：

- `cvdLongOk/cvdShortOk`
- 结构验证
- B/C等级
- 直接挂单
- 冲突/X降级
- alertcondition
- MCP编码

低样本、无有效成交量或远离关键位时，CVD应退化为中性，不能由 raw divergence/absorption 放行、阻断或触发“CVD配合”。

背离算法还要检查是否强制“价格pivot与CVD自身pivot同一根确认”。社区更常见且召回率更高的做法是以价格pivot为锚，比较该锚点的CVD值。

## 7. Magnet 的目标与提醒必须绑定同一分数

如果 `magnetScore`属于最近水平，而实际多/空目标使用最高分上方/下方水平，那么高分提醒不能读取 `magnetScore`。应生成原子绑定的：

```pine
magnetTargetName
magnetTargetPrice
magnetTargetScore
magnetTargetDist
magnetTargetHtf
```

目标方向还必须相对最终入场价有效，而不只是相对当前 `close` 位于上方/下方。

## 8. 跨资产适应检查

- 市场识别不要用任意子串（如 ticker 含 `GC` 即贵金属）；优先使用 `syminfo.type + syminfo.root + exchange` 精确白名单。
- “某市场CVD权重=0”若仍让 raw CVD进入结构/B级/挂单门控，语义仍不一致。
- `volume * price * barsPerDay` 只近似适合现货和部分线性合约；反向合约、张数计量期货必须分路由，无法确认单位时只提示不硬门控。

## 9. 配额结论写法

报告同时给原始调用数与 plot-count 构成，例如：

- request：顶层静态调用点/40；注明 input/三元/if 不减少静态配额；
- plot count：`plot + series-color附加 + fill(series color) + bgcolor + alertcondition`；
- 未取得 TradingView 服务器回执时，明确写“静态无P0”，不得把静态扫描冒充云端编译通过。

## 10. nPOC 必须拆开生命周期、事件与方向选择

`上一完成 POC` 与 `nPOC` 不是同一概念：前者无论是否回测都保留；后者只指 Profile 结束后尚未被后续价格访问的 POC。审计时必须沿 `边界结算 → 创建 → 当前K触碰 → active失效 → 清理 → 表格/轴标/磁吸/事件` 全链检查。

常见隐蔽错误：

- touch 循环先把对象设为 inactive，事件层随后只扫描 active 集合，导致“触nPOC”事件永远不可达；应在失效瞬间直接保存 `touchedNow/price/count`。
- 只取数组尾部第一个 active nPOC，会把“最新创建”误当成“离价格最近”；决策层应原子计算 `nearestAbove`、`nearestBelow`、`latestActive`，支撑/阻力和多空目标分别消费方向化结果。
- 轴标、行动格、磁吸和提醒各自重复扫描数组，会在后续修改选择规则时漂移；统一计算一次选择状态。
- 桶宽只限制 `>= mintick` 但不量化到整数 tick，会得到不可交易价格，并与 TradingView Periodic Volume Profile 口径偏离。
- 自动 lower-TF 映射、K线成交量在桶间的分配方法、POC同量 tie-break 都会造成与官方/社区 VP 的差异，不能把这些差异误报为 nPOC 生命周期错误。

验证至少覆盖：创建时 nPOC 与刚完成 POC 完全相等；新周期首K填补能产生一次事件；上下各有多个 active nPOC 时选择最近方向位；同价去重；重载/回放状态一致。

## 11. 死代码的决策含义

死变量不只影响token。若未确认 HTF request 仅供一个死文本变量使用，应连同整条请求链识别为可清理项；这既释放 request 配额，也防止未来误把未确认HTF值接入正式门控。