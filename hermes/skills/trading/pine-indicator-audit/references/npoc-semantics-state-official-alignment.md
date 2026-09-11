# nPOC / Previous POC 语义、状态与官方口径审计

适用于 Pine 自定义 Session/Periodic Volume Profile 中的 Naked POC。

## 核心不变量

若周期结算与 nPOC 创建都读取同一次 `engine.lastPocPrice`，则**创建瞬间 nPOC 必须等于刚完成 Profile 的 POC**。观察到不等，优先排查：最新 POC 已被触及后回退到更早 active nPOC、比较了不同周期、或拿官方 VP 与自定义算法比较。

## 三个必须拆开的语义

- `prevCompletedPoc`：前一个已完成 Profile 的 POC，不管后来是否被触及。
- `latestActiveNpoc`：时间上最新、仍未触及的历史 POC。
- `nearestNpocAbove/Below`：相对当前价或最终 entry 最近的方向化 naked POC。

不得用一个“数组尾部首个 active”变量同时代表三者。支撑/阻力与 Magnet 应分别消费最近下方/上方 nPOC；轴标若只能显示一个，名称必须说明是“最新”还是“最近”。

## 触碰事件的状态机陷阱

危险顺序：

1. 扫描 active nPOC；若 `low <= price <= high`，先写 `active=false`；
2. 再从 active 集合选择当前 nPOC；
3. 用选中的 active nPOC 判断 `touchNow`。

此时真实被触及水平已从候选集合消失，`touchNow` 结构性不可达。正确做法是在 mutation 循环中直接输出瞬时事件：

- `npocTouchedNow`
- `npocTouchedPrice`
- `npocTouchedStartBar`
- 可选 `npocTouchedCount`

事件、提醒和 MCP 消费该快照；active 集合只表示触碰后的持久状态。

## 常见社区 Naked POC 生命周期

社区常见定义：POC 在源 session 结束后尚未被后续价格访问即为 naked；后续任意 bar 的高低区间跨过该价即 filled。源 Profile 自己的最后一根 K 不算回访；新周期第一根 K 可以立即填补。Clean/no-clutter 版本通常触碰后删除或隐藏；保留历史则应显式提供“截断并淡化”模式。

TradingView 官方 Periodic Volume Profile 的 `Extend POC Right` 也定义为延长到任意 bar 穿越该 POC 为止。

## 官方 PVP 对齐检查

### Lower timeframe 映射

TradingView Periodic VP 当前公开表：

- 1–4m → 1m
- 5–15m → 1m
- 16–30m → 5m
- 31–60m → 10m
- 61–120m → 15m
- 121–240m → 30m
- 241m 以上 → 60m

自定义映射若更粗，POC 不相等属于预期模型差异。

### 行宽必须是整数 tick

官方 Number of Rows 先计算 ticks per row，再向上/向下取整为整数 tick，选择实际总行数更接近请求值的一侧，必要时增加尾行覆盖全范围。仅做 `step=max(range/rows,mintick)` 会产生非 tick 对齐的桶中心和 POC，不能宣称官方一致。

### 成交量分配

“每根低周期 K 的成交量平均分给所有被高低区间穿过的桶”是常见简化，但边界碎片桶与完整覆盖桶同权。社区还存在按重叠高度比例、close-weighted triangular 等模型；TradingView 未公开全部行内分配细节。报告应称为模型差异，不把任一社区算法冒充官方唯一口径。

## 产品决策：保留、拆分或物理删除

语义研究不等于必须保留功能。若用户在小时及以上周期反复观察到历史未测试 POC 与其交易认知不一致，并明确要求删除，生产版采用：

- 保留当前发展中 POC；
- 保留 `pPOC`：紧邻前一个已完成 Profile 的 POC，无论是否回测；
- 物理删除 nPOC，而不是关闭显示开关。

“物理删除”必须全链清理：input/tooltip/style、UDT和数组、周期结算创建、touch/失效事件、支撑阻力、Magnet候选、关键位门控、候选触发路径、Data Window、提醒和价格轴。完成后对指标源码做大小写不敏感搜索，`npoc|nakedpoc` 必须为零；同时确认 `pPOC`仍有唯一线对象和唯一轴标。

若其他用户明确需要 nPOC，再采用三语义拆分：

- `prevCompletedPoc`：前一个已完成 Profile 的 POC，不管后来是否被触及；
- `latestActiveNpoc`：时间上最新、仍未触及的历史 POC；
- `nearestNpocAbove/Below`：相对当前价或最终 entry 最近的方向化 naked POC。

不得用一个“数组尾部首个 active”变量同时代表三者。

## 行动格触发导航

行动格不能只写“等触发”，但也不能把候选写成已经发生的事实。进场行采用五态：

- 未发生：`等触发（扫低收回→MSS↑）`
- 盘中未收：`等收线（扫低收回）`
- 已触发但其他闸门未齐：`等确认（扫低收回）`
- 已过期：`等新触发（MSS↑已过期）`
- 可执行：`挂单 价格（实际触发类型）`

候选路径按位置路由：流动性边界优先 Sweep→MSS；FVG/OB 内优先承接/承压→位移或MSS；VWAP/VA边界优先站回/跌回→MSS；CVD吸收/派发优先CVD→MSS。触发码、年龄、收线状态与进场文案必须来自同一个执行状态机。

**显示优先级陷阱：** 在触发尚未发生时，Entry/Stop/Target几何通常还不完整。如果 `panelEntryVal` 先判断 `not priceGeometryOk` 或 `rrHardBlock`，`等触发（路径）`分支会结构性不可见。正确顺序是：

1. `triggerCode == 0` → `等触发（expectedTriggerPath）`；
2. 触发存在但过期 → `等新触发（类型已过期）`；
3. 盘中未收 → `等收线（类型）`；
4. 此后才检查价格几何、R:R及其他硬闸门；
5. 合格后显示挂单价与实际触发类型。

无明确多空计划时也给稳定兜底：`等触发（等方向）`。回归测试应直接断言源码分支顺序为 `triggerCode == 0` 先于 `not priceGeometryOk`，不能只断言文案字符串存在。

## 其他状态与绘制检查

- 多个同价 active nPOC 是否按 tick 容差去重，或保存来源周期计数。
- inactive 对象是否占用容量，导致 distinct active 水平被过早淘汰。
- 创建线必须非零长度；维护 `x2` 与首次可见性一致。
- 轴标、表格、Magnet、提醒、MCP 不应各自重复扫描数组，应共享一次原子选择结果。
- 若触碰后把 line 整体设为 100% 透明，这是“只显示 naked”模式的合法行为，不应误报为绘制 bug；只有产品要求保留测试历史时才需改为截断/淡化。

## 最小验证矩阵

1. **创建一致性**：边界处断言 `newNpoc.price == prevCompletedPoc`。
2. **首 K 填补**：新周期第一根 K 穿越 POC；持久状态 inactive，瞬时 touch 事件必须恰好一次。
3. **最新回退**：填补最新 nPOC 后，显示回退到更早 active，证明它不是上一期 POC。
4. **方向候选**：上下各放一个 active nPOC，必须同时得到 nearest above/below。
5. **多水平同 K**：一根 K 穿越多个 nPOC，事件计数和价格集合不丢失。
6. **tick 对齐**：验证 `step/mintick` 与 `poc/mintick` 为整数或按定义的半行中心规则可解释。
7. **官方对照**：统一 period、rows、lower TF、volume source 后再比较；剩余差异标为未公开行内分配模型。
8. **重载/回放同构**：active 集合、触碰 bar、轴标和提醒在实时、重载、Bar Replay 中一致。

## 权威来源

- TradingView Volume Profile basic concepts: https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/
- TradingView Periodic Volume Profile: https://www.tradingview.com/support/solutions/43000703071-periodic-volume-profile/
- 社区 clean/no-clutter Naked POC 示例: https://www.tradingview.com/script/3r5whRmf-Naked-POC-nPOC-Clean-and-No-Clutter/
