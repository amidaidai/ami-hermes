# SVP vNext 敌对式决策闭环审计签名（2026-07-19）

适用于大型 Pine v6 主指标已经通过普通静态扫描，但仍可能向行动格、MCP 或提醒导出错误执行计划的场景。

## 1. 最终风险态必须硬门控执行

危险模式：`setupX` / `noTrade` 只影响结论文字或 `entryValidCode`，却没有进入 `executablePlan`。

```pine
bool executablePlanBase = aOk or bcDirectOk
bool executablePlan = executablePlanBase and triggerFresh and barstate.isconfirmed
int entryValidCode = ... setupX ? -3 : executablePlan ? 2 : 1
```

这可同时产生“Entry Valid=-3”与非 `na` 的 Entry/Stop/Target。审计必须断言：

- `executablePlan` 含 `not setupX`（或统一 `not noTradeHardBlock`）；
- B/C/C-direct 原始路径也不能绕过硬风险态；
- Side/Grade/Entry Valid/Execution Pack/行动格结论不能互相冲突。

## 2. 多事件同K不能共用一个价格槽

危险模式：循环累积 `sweptHighNow/sweptLowNow`，却反复覆盖单一 `ictEventPrice`。外包K同时扫高、扫低时，多单可能读取扫高价，空单可能读取扫低价。

至少拆为：

- `sweptHighPrice/name/count`
- `sweptLowPrice/name/count`

最终多空 Entry、MSS、提醒分别消费方向化事件快照。

## 3. nPOC 必须完整继承扫线模式

若 `SWEEP_MARK_MODE` 有“触碰即扫 / 收盘即扫 / 收回确认”，nPOC 不得把后两者写成同一个条件。“收回确认”必须包含相对 nPOC 方向的 `closeReclaim`。同K触碰多个 nPOC 时，不能只保存最后一个价格；至少保存数量与方向化最近价格。

## 4. Qualified CVD 必须禁止 raw 绕过

定义 `cvd*Qualified` 后，继续逐项 grep：

- 结构验证；
- 结构冲突；
- B/C/C-direct；
- Trigger；
- Action/MCP/alerts。

正式决策端不得再读 raw divergence/absorption。尤其检查“市场 CVD 权重=0”时：Qualified 信号本身也必须退化为中性，不能因为评分权重为0却仍触发 C setup 或 Trigger。

## 5. 区域价格必须与质量对象原子绑定

危险模式：`score := max(score, zone.score)`，但 `entryCe := zone.ce` 每次循环都覆盖。这样显示的质量分与实际 Entry 来自不同 FVG/OB。

为每方向维护原子对象：`score/CE/top/bot/HTF/dist/id`，只在同一胜出分支中一起更新。MCP、行动格和 finalEntry 使用同一对象。

## 6. Magnet 应在 finalEntry 后按方向重选

只按当前 `close` 选 `above/below` 会把相对 close 合法、相对最终 Entry 无效的水平选为目标，然后让几何检查失败，即使还有更远的合法候选。

正确顺序：

1. 生成 finalEntry；
2. 以 finalEntry 为锚筛方向；
3. 在合法方向候选中评分；
4. 原子绑定 target name/price/score/dist/HTF；
5. 再计算 Stop/R:R。

若产品规定 nPOC 可参与 Magnet，必须确认 Magnet 候选循环显式扫描 active nPOC；“nPOC只参与支撑阻力”不等于已进入 Magnet。

## 7. Tick量化后必须验证全范围覆盖

`round(rawStep / mintick)` 可能把 step 向下取整，导致 `FINAL_ROWS * step < priceRange`，顶部价格被 clamp 到最后一桶，污染 POC/VA。量化后必须满足覆盖断言，通常使用 `ceil` 或官方 rows/ticks 选取逻辑，并验证最后一桶上沿覆盖 `maxProfilePrice`。

## 8. 唯一 Stop 源不仅约束“止损行”

即使 MCP Stop 与面板“止损”行都读 finalStop，“解除/失效”文本仍可能读旧的 close-anchored invalid price。审计价格口径表必须覆盖：

- 进场行；
- 止损行；
- 目标行；
- 解除/失效行；
- MCP；
- alerts；
- replay。

## 9. B/C提醒必须标清语义

A级执行提醒应消费最终 Entry Valid。B/C若只消费 `setupLongB/setupLongC`，只能命名为等待/候选提醒；任何下游可执行提醒都必须额外门控 trigger freshness、geometry、RR、hard risk 与 executablePlan。

## 10. 静态通过的声明边界

本地扫描无未定义变量、request/plot在限内，只能写“静态未发现P0”。TradingView编译探针没有服务器回执时，报告编译边界，不能把源码字符/token估算写成编译成功。