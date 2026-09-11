# TV MCP 数据保真陷阱（2026-08-28 实测）

## 1. study_values 大数值被缩写 → 精确价别读它
`data_get_study_values` 返回的 S VWAP/EMA/关键位会被 TV 缩写成
`4.6K`、`1.1M`、`171.02K` 之类，**拿不到精确点位**。
- 精确价必须读 `data_get_pine_lines`（去重价位数组 / verbose 拿 raw）+
  `data_get_pine_labels`（text+price）。
- 例：15m 时 VWAP 显示 `4.6K`，实际靠 lines/labels 解析出 `4643.21 / 4564.27 / 4618.15`。

## 2. 跨周期 close 冲突 → 用 quote_get 仲裁真现价
同一根 bar 时间戳，15m 最末 close 和 5m 最末 close 可能差 30+ 点
（示例：15m close=4616.96 vs 5m close=4587.22，同一时间戳）。
- 不猜，直接 `quote_get(symbol=...)` 拿 `last` 作权威真现价。
- OANDA:XAUUSD 面板返回 `type=commodity` 可确认是黄金而非 crypto。

## 3. ClosedResourceError 恢复
首次调用若报 `ClosedResourceError`，走 `tv_launch(kill_existing=true, port=9222)`
重启 TV 带 CDP，等 5-8s 待图表加载，再 `tv_health_check` 确认
`cdp_connected:true + api_available:true`。不要在一个坏连接上反复重试同一条失败路径。

## 4. 品种静默漂移
同一次分析里，`tv_health_check` 读到 XAUUSD、`chart_get_state` 却读到 BTCUSDT
（多标签/切品种后指标引擎未跟随）。**每次读主数据前先 `chart_get_state` 校验 symbol，
发现漂移立即重拉，绝不用错品种数据糊弄。**

## 5. 1h 等周期 SVP 渲染不全
1h 偶发只返回 Volume+副指标(Valid=0)，或 SVP 数值与 4h/15m 明显不符（锚错位/残留）。
- 重读一次；仍不整则标「无SVP独立数据·继承相邻周期」，**不硬用异常数值**。

## 6. deferred MCP 调用方式
本会话 TV 的 set_symbol/set_timeframe/quote 等需用 `tool_call` 包装，不能直接当原生函数。
`chart_set_symbol` 直接调用报 does not exist → 用 `tool_call(name=..., arguments={...})`。
