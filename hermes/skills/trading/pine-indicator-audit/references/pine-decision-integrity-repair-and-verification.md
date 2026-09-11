# Pine 决策完整性修复与验证协议

适用于大型 Pine v6 决策面板：Volume Profile、ICT 流动性、VWAP、CVD、Magnet、行动格和 Data Window 共同驱动交易计划时使用。

## 一、修复顺序

必须按依赖顺序处理，避免只修显示层：

1. **数值源**：POC/VAH/VAL、CVD、OI、HTF。
2. **事件状态机**：扫线、接受/拒绝、背离、吸收。
3. **候选计划**：方向、入场、失效、目标。
4. **方向几何**：多单 `stop < entry < target`；空单 `target < entry < stop`。
5. **R:R与执行闸门**。
6. **消费端统一**：行动格、提醒、Data Window、回放全部读同一最终计划。
7. **静态验证和TradingView云端编译**。

不能先改行动格文字，再让R:R和Data Window继续消费旧变量。

## 二、SVP计算与绘图解耦

危险模式是只有 `barstate.islast` 才调用同时负责计算和绘图的方法。修复时给引擎增加显式绘图开关：

```pine
method processAndRender(Engine this, int startBar, int endBar, bool active, bool renderObjects) =>
    // 数值总是计算
    ...
    bool shouldRender = renderObjects and (active or RENDER_COMPLETED_PROFILE)
```

调用规则：

- 已完成Profile：计算并按配置绘制；
- 当前Profile：每根K更新数值，仅最后一根绘制对象。

注意性能：修复后必须在主要使用周期实测执行时间。若每根K完整重分桶过慢，应进一步把数值引擎改为增量缓存，而不是退回“仅最后一根计算”的历史失真模式。

## 三、Value Area阈值

按当前 TradingView 官方口径审计：从 POC 比较上下候选桶；若加入候选桶会超过剩余目标量，则停止，不纳入该桶。禁止无条件累加到首次达到/超过目标的旧实现：

```pine
if current + candidate > threshold
    break
```

若产品明确采用“首次达到/超过”或其他平台口径，必须在源码和报告中标为自定义算法，不得称为 TradingView 官方一致。建议增加确定性回归样例：剩余目标70、当前已纳入40、候选桶31；官方口径应停止在40，旧算法会错误达到71。

## 四、统一扫线状态机

不要让图形层和交易层分别检测穿越。给流动性对象记录事件发生柱：

```pine
bool swept
int sweptBar
```

统一状态机确认扫线后设置：

```pine
lvl.swept := true
lvl.sweptBar := bar_index
```

交易事件只消费：

```pine
newlySwept = lvl.swept and lvl.sweptBar == bar_index
```

这样会自然继承“触碰即扫 / 收盘即扫 / 收回确认”，并阻止旧水平重复生成新扫事件。修改UDT字段后，必须检查**所有构造器参数数量**。

## 五、CVD质量门控

建议拆两层：

- `cvdDecisionUsableBase`：开关开启、样本质量合格、市场权重大于0；
- `cvdDecisionEnabled`：再叠加关键位/接受条件。

质量不足或该市场权重为0时，CVD必须退化为中性，而不是默认否决。执行链、B/C等级、直接挂单、冲突、提醒只能消费 Qualified 状态。原始CVD可留作显示，不得绕过门控。

## 六、唯一最终价格对象

先按优先级确定唯一候选：FVG CE、扫线价、VAH/VAL、吸收回踩价、普通计划价。再生成：

```pine
finalEntry
finalStop
finalTarget
priceGeometryOk
finalRR
finalExecutable
```

方向几何通过后才能计算有符号R:R：

```pine
longRisk   = entry - stop
longReward = target - entry
shortRisk  = stop - entry
shortReward= entry - target
```

止损ATR距离必须是 `abs(entry-stop)`。不可执行时，Data Window的Entry/Stop/Target应输出 `na`；行动格也不能显示另一套“看起来可下单”的价格。

## 七、主副指标有效性协议

加密聚合量/OI副指标需要一个全链有效标志，例如：

```pine
haldroUsable = isCrypto and (usingAggregatedFeed or fallbackToChartFeed)
```

它至少门控：

- 强/中共振；
- Confirm Score；
- 全部告警；
- OI/CVD/LSR导出；
- Flow Pack与Composite。

非加密时应保留明确Risk/Valid编码，但不能输出方向性确认。运行时 `if` 不减少request静态配额，不要把有效性门控误报成配额优化。

CVD质量码建议使用位图并写注释，例如：1=背离、4=非加密、8=估算口径。更改编码后必须同步下游解码器。

## 八、验证清单

### 静态扫描

- Pine版本；
- `request.*`静态展开；
- plot-count；
- 未定义变量；
- def-before-use；
- lookahead口径；
- UDT全部构造器参数数量。

### 针对性语义断言

- Value Area“首次达到/超过”回归；
- 多空价格几何正反样例；
- MCP Target读取最终可执行Target；
- 止损ATR按Entry计算；
- 旧扫线不能重复产生新事件；
- 非加密Confirm/Composite归零；
- 所有副指标告警含有效性门控；
- 删除重复CVD锚定输入。

### 完成声明边界

静态扫描通过不等于TradingView服务器编译通过。最终报告必须分开写：

1. 本地静态/语义回归结果；
2. TradingView云端编译错误列表；
3. 图表运行与Data Window验收。

如果自动化无法取得云端编译回执，应明确标注验证边界，但仍交付可复核源码、校验码和测试结果，禁止伪造“已编译通过”。
