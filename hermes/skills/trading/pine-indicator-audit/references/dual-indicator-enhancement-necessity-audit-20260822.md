# 双指标增强必要性审计方法（2026-08-22）

## 核心判定

审阅增强清单时，不能把每项都当作新增功能。先按源码证据分类：

- 已实现：源码已有完整逻辑，只需验证消费端一致性。
- 部分实现：已有变量/模块，但状态码、下游消费或边界不完整。
- 缺失：没有可复用实现，应评估后新增。
- 不值得：收益不足以抵消 Pine token、运行时、配额或认知复杂度。

每项必须说明：源码证据、用户收益、配额/性能成本、重绘或数据风险、P0/P1/P2 优先级。

## 双指标职责合同

主指标是唯一执行授权源：方向、等级、触发路径、Entry、Stop、Target、R:R、X硬阻断。副指标只能确认、降级、否决，不得独立发出买卖计划，也不得把 B/C 升级为 A。

最终优先级：`X > WAIT > A > B/C`。

- X、WAIT：Entry/Stop/Target 必须为空。
- B/C：价格只能进入独立人工候选字段。
- A：仅在收线确认、触发新鲜、价格几何有效、R:R 合格时可执行。

## 本次双指标审计结论

### P0 必须完善

1. **唯一 FinalPlan**：当前主指标已有 `finalEntryCandidate`、`finalStopCandidate`、`priceGeometryOk`、`executablePlan` 等，但必须验证行动格、Data Window、MCP pack、提醒和回放全部读取同一最终计划，不能继续存在旁路候选价格。
2. **X/WAIT/A/B/C 状态分层**：当前已有 `setupX`、`entryValidCode`、`signalStateCode`、`triggerFresh` 等，属于部分实现。应拆出稳定的 HardBlock/Wait/Warning 语义，避免“有方向”被误读成“可执行”。
3. **AggVol 数据语义**：五所成交量和四所 OI 是聚合数据，但副指标 CVD 是当前图表品种的低周期或 K 线估算，不能表述为五所聚合 CVD。
4. **CVD Method Code**：当前若固定输出 K 线方法码，会掩盖低周期路径。统一编码：0=无效，1=当前K线方向估算，2=低周期 CVD 估算。

### P1 值得新增或补齐

5. **双锚 CVD 状态**：保留加密 5m/15m 日锚用于执行，新增周锚作为结构背景；用“日/周同向或冲突”状态，不堆第三条独立信号。主副的期货、指数非加密锚定路由也必须统一。
6. **AggVol 同步放量宽度与逐源新鲜度**：显示 `4/5 同步放量`，并按交易所记录 freshness、掉线和恢复；覆盖率不能替代逐源新鲜度。
7. **OB/FVG/iFVG/扫线状态一致性**：主指标已有部分模块，不是从零新增。补齐影线触碰、CE缓解、收盘穿透、完全填补、iFVG反向回测、扫线事件年龄与失效状态，并让图形与交易逻辑共享状态机。

### P2 后置

8. **Zone Registry 与完整跨市场路由**：长期有价值，但先用轻量 `winnerZone` 统一胜出区域，暂不全量重构对象模型。期货夜盘/交易日、股票 RTH/盘前盘后、金属现货与期货数据语义应后置路由化。

## 外部资料核对后的稳定原则

TradingView 官方 CVD 说明：CVD 使用低周期成交量按价格运动分类并在锚定周期重置，是估算而非经审计的 Bid/Ask 主动成交量。因而日重置对加密日内执行是正常设计，不应简单替换为周重置；跨日背景应采用第二锚定状态。

社区常见 CVD 脚本使用 Session/Daily、Weekly、Multi-Day 或 Continuous 模式，并强调低周期分辨率与历史覆盖的权衡；结构确认的 pivot 背离比滚动极值更可读，但背离不能独立授权交易。

社区 OI 工具普遍使用价格上涨/下跌 × OI 上升/下降四象限，并把结果作为上下文。OI 上升并不能单独证明新增多仓或新增空仓，必须结合价格、CVD、量能和结构。

社区 Volume Profile 工具重点是 POC、VAH/VAL、HVN/LVN、前周期投影和 value migration。应把它们当作位置、接受/拒绝和磁吸背景，不要把每个结构重复加入总分。

多交易所量能聚合只有在单位可比、覆盖率、新鲜度和单所主导被显式显示时才有价值。当前图表 CVD 与跨所成交量必须在界面和 Data Window 分开命名。

## 不建议

暂不添加第三套 CVD、更多总分、未经验证的真实 Footprint/清算量声明、更多交易所覆盖或独立副指标买卖信号。每项都会增加配额、token、性能或认知负担，却不一定增加可执行信息。

## 实施顺序

1. FinalPlan 消费端统一与 X/WAIT 合同。
2. 副指标 CVD 方法码与数据语义修正。
3. 主副 CVD 锚定统一，加入日/周同向状态。
4. AggVol 逐源 freshness 与同步放量宽度。
5. OB/FVG/iFVG/扫线状态回归。
6. 轻量 winnerZone。
7. 期货、股票、金属专用时段/锚定路由。

## 参考来源

- TradingView CVD: https://www.tradingview.com/support/solutions/43000725058-cumulative-volume-delta/
- Pine limitations: https://www.tradingview.com/pine-script-docs/writing/limitations/
- Other timeframes/data: https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/
- OI Suite community example: https://www.tradingview.com/script/hCTvvx5o-Open-Interest-Suite-QuantAlgo/
- OI + Price Quadrants community example: https://www.tradingview.com/script/D5187oQf-Open-Interest-Price-Quadrants-GBB/
- Volume Profile XL community example: https://www.tradingview.com/script/OUL0w595-Volume-Profile-XL/
- Aggregated CVD community example: https://www.tradingview.com/script/GMQ0IESe-AGGREGATED-CVD-MULTI-EXCHANGE/
