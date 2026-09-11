# TradingView MCP 运行时 Quirks & Workaround

## 1. `chart_manage_indicator` 添加指标失败

**现象：** 在 cn.tradingview.com（中文版）上，`chart_manage_indicator(action='add', indicator='...')` 无论传什么名称都返回 `success: false`。

**已测试的名称：**
- `"Relative Strength Index"` — ❌
- `"RSI"` — ❌（短名不支持）
- `"相对强弱指数"` — ❌（中文名也不支持）

**原因推测：** 该 MCP tool 的 indicator 名称匹配机制在中文 TV 上不兼容（可能依赖英文 TV 的 exact name registry）。

**Workaround：**
- 别用 `chart_manage_indicator` 来加新指标
- 替代方案：
  1. **手动拉 OHLCV 数据 + Python 计算：** 用 `data_get_ohlcv(count=N)` 拿原始 K 线，在 Python 里算 RSI/MACD/Vol Ratio 等
  2. **用已有指标：** 用户图表上已挂的 Volume、CVD、SVP+ICT 等仍然可通过 `get_study_values` / `get_pine_tables` / `get_pine_lines` 读取
  3. **UI 交互路径：** 如需加新指标，用 `ui_click` / `ui_type_text` 模拟点击指标面板（如果必要）

## 2. `batch_run` 动作兼容性

**现象：** `batch_run(symbols=[...], action='get_ohlcv')` 对所有品种均返回 JS evaluation error。

```
symbols: ["BINANCE:BTCUSDT","BINANCE:ETHUSDT","BINANCE:SOLUSDT"]
action: get_ohlcv → ❌ 全部 failed
```

**可靠替代 — 逐个切换取数：**
```
chart_set_symbol("BINANCE:ETHUSDT")
→ wait / check chart_get_state
→ data_get_ohlcv(count=30)  # 或 summary=true
→ 在 Python 中统一计算指标
```

`batch_run(action='screenshot')` 等其他 action 可能正常工作，但 `get_ohlcv` 已知有问题。

## 3. 切换品种时周期重置

**现象：** 调 `chart_set_symbol` 后，`chart_get_state` 有时显示 `resolution: "1D"` 而不是当前的 15m 周期。

**触发条件：**
- `chart_set_symbol` 返回 `chart_ready: false`
- 之后 `chart_get_state` 显示品种已切但分辨率变成日线

**修复步骤：**
```
chart_set_symbol("BINANCE:SOLUSDT")
→ chart_get_state()  # 检查 resolution
→ if resolution != "15":
    chart_set_timeframe("15")
→ data_get_ohlcv(...)
```

**最佳实践：** 每次 `chart_set_symbol` 后，永远紧跟 `chart_get_state` + 必要时 `chart_set_timeframe`。

## 4. 可靠的多品种扫描工作流

以下模式经过验证稳定可用：

```
① chart_set_symbol("BTCUSDT")
② chart_get_state() → 检查 resolution
③ chart_set_timeframe("15")  # 如有需要
④ data_get_ohlcv(count=30)   # 获取完整 K 线
⑤ 重复①-④ 对每个品种
⑥ Python 计算 RSI/Vol Ratio/MACD 等
⑦ 输出对比结果
```

**对比 Vincent 帖子的功能映射：**

| Vincent 声称 | 实际实现 |
|---|---|
| "扫一遍所有合约" | 逐个切换 + OHLCV + Python 计算 |
| "RSI低于30，成交量放大200%" | 用 30 根 K 线计算 Wilder RSI(14) + 20 均量比 |
| "图表自动加载" | `chart_set_symbol` + `chart_set_timeframe` |
| "关键支撑位画好" | `draw_shape`（独立可用） |
| "Pine脚本回测跑完" | `pine_set_source` + `pine_compile` + Strategy Tester |
| "现场写一个指标" | `pine_set_source` → `pine_compile` → indicator loads |
| "40秒，脚本写好直接加载" | 实际 10-20 秒（取决于 Pine 编译） |
| "一分钟扫200多个标的" | 逐个切换约 2-3 秒/个，200 个约 8-10 分钟 |

> **注意：** 逐个切换的速率限制受 TV CDP 命令响应速度影响。如需真正批量扫描 200+ 合约，建议写 Pine Script 在 TV 内部完成扫描（使用 `request.security()` 多品种循环），一次性获取全量数据。
