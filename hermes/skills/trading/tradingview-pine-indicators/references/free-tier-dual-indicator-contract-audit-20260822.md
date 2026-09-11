# 免费版双指标契约审计（2026-08-22）

适用：TradingView 免费账号下，SVP 主指标 + AggVol 副指标的增强与审计。目标是提高决策完整性和数据真实性；不加入回测/复盘、Footprint 或额外交易所。

## 免费版边界

- 保留既有 5 所成交量（BINANCE/BYBIT/OKX/COINBASE/BITGET）和 4 所 OI；先修契约，不静默削源。
- CVD 低周期请求的是当前图表 symbol，不等于五所聚合 CVD；UI、注释、Method Code 必须如实区分。
- 非加密品种（XAU/FX/股票/指数/期货等）不得进入加密跨所聚合请求路径；非加密只保留主指标/单图辅助语义。
- `None` 通道必须在调用交易所请求函数之前短路，不能构造 `EXCHANGE:BASE0`。

## P0 数据契约修复

1. 副指标 CVD 方法码动态化：`0=无效`、`1=当前K线方向估算`、`2=低周期CVD估算`。
2. 非 USD 汇率缺失不能 `nz(rate, 1.0)` 静默继续；应标记质量降级或禁止跨币种聚合。
3. 单所有效与跨所共识分离：`FeedValid` 可由 1 所正常数据成立，`ConsensusValid` 至少 2 所。
4. `freshness` 不要用单个 `barssince(...)->nz(...,999)` 同时表达有效、失效、从未失效；至少拆当前有效位和有效/失效年龄。
5. 主指标必须消费副指标的 valid/market/coverage/freshness/feed/contract 信息；不能只接 OI/State 数值。
6. 不要用 `source != close` 作为 input.source 接线哨兵；合法 OI 或状态值可能等于图表 close。用显式版本化质量包。
7. State 的 Neutral 与 Degraded 不得共用一个会被主指标一律扣分的编码；冲突、降级、中性分开。

## 推荐 Quality Pack

用一个稳定版本化数值包供主指标 `input.source()` 消费，避免增加大量独立总线。示例编码：

`230000 + marketBit*10000 + validBit*1000 + consensusBit*100 + validVenues*10 + validOI`

主指标先验证版本、加密市场位和 valid 位，再允许副指标状态参与评分。质量无效时：副指标可以显示诊断，但方向票、Flow Pack、Composite、提醒全部失效。

## 主指标执行合同

- 主指标是唯一执行授权源；副指标只能确认、降级、否决。
- 候选结构先收束成唯一 FinalPlan，再统一输出 Entry/Stop/Target/R:R、行动格、Data Window、MCP 和警报。
- X/WAIT 时 Entry/Stop/Target 必须为 `na`；B/C 价格进入独立人工候选字段；只有 A 且触发新鲜、收线确认、几何有效、R:R 合格才可执行。
- 多单必须 `Stop < Entry < Target`；空单必须 `Target < Entry < Stop`；按 `mintick` 量化后重新验证几何与 R:R。

## 真增强与伪增强

真增强：减少重绘/未来泄漏、修复数据单位和有效性、改善跨市场路由、让唯一计划包含确认/失效/目标/质量、降低真实计算/对象负荷。

伪增强：第三套 CVD、继续加交易所、更多总分、满屏 HH/HL/LH/LL、把 OHLC 估算称真实主动买卖、把永续-现货量差称真实爆仓、只加 input 开关但请求仍执行、只改颜色/文案。

## 验收

本地先做：文件完整性、UTF-8/CRLF、request/plot/object 统计、旧哨兵和伪请求扫描、质量包编码/解码一致性。最终仍需在 TradingView 云端编译并在 BTCUSDT 5m/15m/1h/4h 与 XAUUSD 对比验证；静态通过不得冒充云端编译通过。
