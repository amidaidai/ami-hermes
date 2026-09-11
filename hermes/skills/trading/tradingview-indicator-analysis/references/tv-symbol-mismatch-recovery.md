# TradingView 品种错配恢复与更新验收

适用：标准更新或完整分析时，TV MCP 的 `chart_get_state`、quote 或行动格与目标品种不一致。

## 必做流程

1. 将错配视为数据完整性故障，不引用错品种的 quote、tables 或截图。
2. 调用 `tv_launch(kill_existing=true)`，再执行 `tv_health_check`，确认 CDP 已连接。
3. 调用 `chart_set_symbol` 设置目标品种；随后调用 `chart_set_timeframe` 设置目标周期。
4. 等待主指标重算约 15–30 秒；不要用切换瞬间的旧行动格。
5. 并行或依次验收：`chart_get_state` 的 symbol/resolution/studies、主指标行动格、副指标行动格、目标品种 quote。
6. 只有 symbol、resolution、指标列表均正确后，才读取关键位和截图；截图必须是新的 full 截图。
7. 若 TV quote 与 Binance 价格有小幅差异，核对品种、时间戳和波动维度；正常微差不否决，明显品种错配才阻断。

## 防并发污染

不要在切换品种/周期尚未验收时并发读取依赖当前图表的 quote、tables、lines、labels。可以并行拉 Binance 公开衍生品数据，但 TV 依赖项必须在状态确认后读取。