# Pine v6 双指标官方约束增量审计（2026-07-21）

## 适用范围

审计主指标 `SVP+ICT+VWAP+CVD` 与副指标 `Volume Aggregated Spot & Futures` 时，用于校正 request、HTF 非重绘、告警与 plot 预算口径。官方页面无单独发布日期时，统一标“访问日期 2026-07-21”；release notes 使用其月份。

## 官方证据

1. **Plot 上限**：每脚本最多 64 plot counts；`alertcondition()`、`bgcolor()`、series-color `fill()` 计数；同一个 `plot()` 若 color 为 series 还会产生额外 count。
   - https://www.tradingview.com/pine-script-docs/writing/limitations/#plot-limits
2. **Request 上限**：40 个运行时 unique `request.*()`，Ultimate 64；相同函数与相同参数通常复用。Pine v6 默认 dynamic requests，允许 series context 与条件/循环内执行；实时只能访问历史执行阶段已请求过的上下文。
   - https://www.tradingview.com/pine-script-docs/writing/limitations/#number-of-calls
   - https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/#dynamic-requests
3. **HTF 非重绘**：确认 HTF 数据的标准模式是 expression 至少 `[1]` 偏移并使用 `lookahead_on`；两者必须同时存在。
   - https://www.tradingview.com/pine-script-docs/concepts/repainting/#repainting-requestsecurity-calls
4. **LTF 数据**：`security_lower_tf()` 比普通 security 更适合 intrabar，但仍可能因供应商修订或实时/历史数据源差异发生轻微重绘。Basic 至 Premium 为 100K intrabars，Expert 125K，Ultimate 200K；`calc_bars_count` 可约束范围。
   - https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/#lower-timeframe-data
   - https://www.tradingview.com/pine-script-docs/writing/limitations/#intrabars
5. **告警**：运行告警只在实时K工作；创建时服务器保存脚本、输入、品种、周期快照，源码或输入更新后必须删除并重建。`alert()` 支持动态 message 与 `alert.freq_once_per_bar_close`；`alertcondition()` 会占 plot count。
   - https://www.tradingview.com/pine-script-docs/concepts/alerts/
6. **Footprint**：2026-01 发布；仅 Premium/Ultimate；每脚本最多一个 unique call；可能返回 `na`。它按 intrabar 价格行为分类 buy/sell、delta、POC/VA 与行级 imbalance，不应宣传成交易所逐笔订单簿。
   - https://www.tradingview.com/pine-script-docs/release-notes/#january-2026
   - https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/#requestfootprint
7. **编译体量**：当前 IL 上限 100,000 tokens；字符数不能可靠换算；未影响输出的死代码会被编译器剔除。
   - https://www.tradingview.com/pine-script-docs/writing/limitations/#compiled-tokens

## 当前源码审计签名

### 主指标

- 40 个 plot 调用（含 4 个赋值形式）、16 个 `alertcondition()`、1 个 `bgcolor()`、2 个 series-color `fill()`，按当前结构约 **59/64**，余量约5。
- `f_htf_fvg()` 已使用 `[1]/[3]`，`f_htf_ob()` 使用已收 HTF 值；若外层仍为 `lookahead_off`，主要问题是额外延迟，不是未来泄漏。应改为 `lookahead_on` 以在新 HTF 开始时发布上一根确认结果。
- raw HTF trend request 若只生成未消费的 `htfArrow`，可物理删除，保留 confirmed pack。
- `security_lower_tf()` 的 SVP 与 CVD 请求应评估 `calc_bars_count`，但 MCP Entry/Stop/Target 和告警仍只能消费收盘确认结果。

### 副指标

- 39 个 plot + 9 个 alertcondition = 48 只是基础数；以下至少10个 plot 使用 series color：Volume、Delta Spot-Perp、Perp-Spot proxy、Delta、CVD、EX1-EX5。静态估计约 **58/64**，余量约6；最终以 TV 编译回执为准。
- 默认配置 unique datasets 约32/40，但“关闭功能不减少静态配额”不是 Pine v6 的通用真理。动态请求分支若未执行，可以减少实际运行时 unique contexts；仍须确保所有实时所需上下文已在历史阶段请求。
- 默认 USD/COIN 路径若仍无条件请求 `FX_CONV_RATE`，这是可释放的 request；只在 EUR/RUB 分支执行换汇请求。
- `ta.barssince(not na(value))` 只能检测缺口，无法识别上游持续重复旧值。freshness 应由每源 timestamp/更新时间年龄驱动。

## 审计与优化顺序

1. 先按 series 参数计算真实 plot counts，不把“调用数”当“plot count”。
2. 将持续状态告警改为进入事件（`state and not state[1]`）；保留少量需要独立选择的 `alertcondition()`，其余合并为动态 `alert()` 释放槽位。
3. 核对 HTF expression 是否已偏移；已偏移但 `lookahead_off` 时标“延迟”，不要误标“重绘”。
4. 按运行时 unique dataset 计算 Pine v6 request 预算，同时检查 dynamic request 的历史预取约束。
5. Footprint 优先独立做 Premium/Ultimate Pro 层，不直接把账户门槛和单调用限制塞入通用生产双指标。
6. 没有 TradingView 服务器编译回执时，只能写“静态估计/静态未发现超限”。
