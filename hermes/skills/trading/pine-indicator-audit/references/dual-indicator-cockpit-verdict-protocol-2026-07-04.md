# 双指标驾驶舱裁决协议（2026-07-04）

适用场景：用户要求检查/优化 SVP v10 主指标 + HALDRO Volume Aggregated 副指标，并希望依赖二者进行加密短线入场开单。

## 核心结论

- SVP v10 是全市场主驾驶：结构、方向、关键位、入场、止损、目标、R:R、A/B/C/X。
- HALDRO 是加密专用副驾驶：聚合 OI、现货/合约量、CVD、覆盖率、Composite、Confirm Score。
- 不要把 HALDRO 强行适配黄金/外汇/股票/传统期货；非加密市场应隐藏或降权副指标，用对应市场数据替代。
- 能不能开单不由单个指标决定，而由“SVP 主结构 + HALDRO 订单流 + 外部验证 + GO/NO-GO 风控”共同裁决。

## 双指标裁决表必须前置

正式加密驾驶舱中，在“多周期定位”之前新增“双指标裁决表”，直接回答主副指标是否共振、能否入场。

建议表头：

| 裁决项 | SVP v10 主驾驶 | HALDRO 副驾驶 | 结论 |
|---|---|---|---|
| 方向 | A/B/C/X + 多/空/等待 | Composite +1/-1/0 | 共振/冲突/不足 |
| 位置 | VAL/POC/VAH/VWAP/EMA | 现货/合约主导 | 顺势/诱多/诱空 |
| 动能 | CVD/位移/DMI | CVD Quality/Volume Ratio | 强/弱/假突破 |
| 持仓 | 结构风险 | OI 增/减 | 增仓推进/减仓反弹 |
| 执行 | Entry/Stop/Target/R:R | Confirm Score/Coverage | A/B/C/X |

## 状态机

| 状态 | 条件 | 动作 |
|---|---|---|
| A可执行 | SVP A/B 同向 + HALDRO Composite 同向 + Confirm Score 高 + R:R≥1:2 + 数据新鲜 | 给入场、止损、目标、仓位 |
| B等确认 | SVP 偏向明确，但 HALDRO 不足或价格未确认 | 给触发条件，不现价追 |
| C轻仓试探 | SVP 低级别反转 + HALDRO 订单流强，但高周期未完全配合 | 只允许轻仓，必须二次确认 |
| X禁做观察 | SVP X / R:R不足 / 数据过期 / 主副强冲突 | 不给可执行入场，只给解除条件 |

## 主副冲突处理

| 情况 | 裁决 |
|---|---|
| SVP A多 + HALDRO 正向 + Binance 顺向 | A多可执行 |
| SVP A多 + HALDRO 负向/CVD卖压 | 降 B，等 CVD 修复 |
| SVP B多 + HALDRO 强确认 | B多，突破/回踩确认 |
| SVP C反多 + HALDRO 强买/OI降 | C轻仓反弹 |
| SVP A空 + HALDRO 负向 + Taker卖强 | A空可执行 |
| SVP A空 + HALDRO 正向 | 降 B 或 X，防假破 |
| SVP X + HALDRO 强 | 不做，只写解除条件 |
| 主副都弱 | X观察 |

## 必读字段

SVP MCP/Data Window 字段优先稳定读取：
- MCP Final State Code / Bias Code / NoTrade Reason Code
- MCP RR Ratio / Entry Valid / Entry Price / Stop Price / Target Price
- MCP Nearest Level / Distance To Level %

HALDRO 字段优先稳定读取：
- HALDRO Valid Code
- HALDRO Composite Code
- HALDRO Confirm Score
- HALDRO Coverage Grade
- HALDRO OI Direction
- HALDRO CVD Direction
- HALDRO Spot Perp Bias
- HALDRO Risk Code

## 审计检查

- 跑 `pine_static_scan.py`，确认 SVP/HALDRO request.security 与 plot 配额安全。
- SVP 若 R:R<1:2，行动格与 MCP Entry/Stop/Target 都必须同步禁用/置空，避免自动化误下单。
- HALDRO 非加密品种必须 Valid=0 或显示不适用，不能制造伪确认。
- auto_card/render/go_nogo 链路必须显式产生 `dual_indicator_verdict` 或同等结构，不能只把 HALDRO 放进“副指标”列。