# 消费层图表证据读回：验证过的适配要点

适用于 TradingView MCP/CLI 把图表证据送入分析卡与 FinalVerdict 的场景。

## 同一现场采集顺序

1. 先读 `chart_get_state`，核对 symbol、resolution、studies；切图工具返回 `success` 不算验收。
2. 状态确认后，在同一现场读取 `values`、两张 action table、lines、boxes、labels、quote，并立即截图。
3. 每个读数都保留实际返回的 symbol、resolution 和 source-bar time；不要用请求参数给结果贴身份。
4. `study_count: 0` 先按争用/重算处理，重读并再次核对周期；不要直接解释成“指标没有输出”。

## CLI/MCP 形状差异

- MCP 的 Pine box 结果可能使用 `zones`，旧适配器可能使用 `boxes`；消费层应兼容两者，但不能凭价格区间猜测它是 FVG 还是 OB。
- quote 应保留一次响应里的 `last/open/high/low/close`，而不是只返回标量 last；这样价格栏可完整进入证据卡。
- 返回对象前先校验报价身份字段：请求 BTC 却出现 Gold/OANDA/commodity 时整份报价丢弃并恢复图表。
- 关键位列表要过滤非正价格；空标签线不能被渲染成有效关键位。

## 证据状态边界

- `verified` 表示身份、周期、研究、价格栏和可结构化的图表证据均通过校验；不等于当前一定存在每一种 ICT 子类型。
- 区域没有类型标签时记录为通用 `zones`，不能改写成 FVG/OB。
- 没有可读对象但只有截图或行动格时标记 `partial`/`visual_only`；FinalVerdict 最多 WAIT，不能升级 GO-A。
- identity mismatch 必须 NO-GO；不能复用上一次品种的指标表、报价或截图。

## 回归验收

至少验证：完整 quote 能渲染 O/H/L/C；`zones` 能保留；旧 `boxes` 仍兼容；0 价格被过滤；BTC 现场缓存的 symbol/timeframe/identity_valid/fresh 与截图一致；全量测试和指标契约审计均通过。
