# SVP/ICT v2 深度静态审计：新增决策合同签名（2026-08-07）

适用于大型 Pine v6 的 SVP + ICT + CVD + FVG/OB + Magnet + 行动格主指标。本文补充普通编译/配额扫描抓不到、但会改变 Entry/Stop/Target/X 最终裁决的审计模式。

## 验收边界

审计结果必须分三层陈述：

1. 静态扫描：未定义变量、def-before-use、request/plot/object 预算；
2. TradingView `translate_light`：只有 `status=200, errors=[], warnings=[]` 才能写“服务器编译通过”；
3. Add-to-chart / Bar Replay / Profiler：未执行时必须明确“运行时性能与回放尚未验证”。

编译通过不等于决策合同一致。

## 1. 单图表 K Profile 的数值坍缩

危险组合：

```pine
if profileEndBar > profileStartBar
    // calculate POC/VA
```

若当前 Profile 第一根 K 调用时 `end == start`，即使 `security_lower_tf()` 已返回多根 intrabar，POC/VAH/VAL 仍不计算。若自动 Profile TF 与图表 TF 相同（典型：股票/贵金属日线自动 D），该 Profile 永远只有一根图表 K，SVP 与 nPOC 可持续为 `na`。

必查链：

- `processAndRender()` 的进入条件是 `>` 还是允许数值计算的 `>=`；
- 新周期结算是否同样跳过单 K Profile；
- 自动/手动 `targetProfileTF == timeframe.period` 时是否仍有数值；
- 数值计算与零宽度绘图必须分离：可以不画直方图，但不能不算 POC/VA。

## 2. B/C 人工候选不能绕过最低 R:R

危险模式：

```pine
bcDirectOk = bcRaw and rr >= 1.5
manualBcCandidate = bcRaw and geometryOk
visiblePlan = executablePlan or manualBcCandidate
```

这会在 `rr < 1.5` 时继续导出非 `na` 的 Entry/Stop/Target，同时 NoTrade 位又标记 R:R 不足。

强制断言：

- `manualBcCandidate` 也必须含产品约定的最低 R:R；
- `visiblePlan`、MCP 价格、行动格 B/C人工、replay 输出共享同一候选合同；
- 测试 `rr=1.2/1.5/2.0` 三个边界，核对 `visiblePlan/entryValid/noTrade/prices`。

## 3. X 必须优先于 Side，NoTrade 不能混装软警告

危险 Side 编码：

```pine
activeLong ? 1 : activeShort ? -1 : setupX ? 9 : 0
```

B/C 原始状态可能在 `setupX=true` 时仍为真，导致 Side=多/空、Grade=X、EntryValid=-3 并存。正确优先级应先输出 X，或把 Bias Side 与 Final Verdict 拆成两个有文档的字段。

`NoTradeReasonCode` 也不能把下列语义无区分地混在一个“禁做”字段：

- 硬风险：X、几何错误、最低 R:R 不足；
- 执行状态：未收线、触发过期；
- 软质量：CVD样本差、PD位置警告、SMT冲突但产品允许人工降级。

必须验证 `EntryValid=2/3` 时 NoTrade 是否仍可非零；若可以，字段应改名为 Risk/Quality Bits，或拆成 HardBlockCode + WarningCode。

## 4. nPOC approachSide 不能由触碰 K 自己的 close 反推

危险模式：创建时：

```pine
approachSide = close >= npoc ? 1 : -1
```

同一根新周期 K 随后触碰并检查：

```pine
closeReclaim = approachSide > 0 ? close > npoc : close < npoc
```

除恰好收在 nPOC，首 K 的 reclaim 几乎恒真，“收回确认”退化为“收盘即扫”。后续触碰时固定的旧 side 也可能与真实接近方向不符。

正确状态至少需要：

- 触碰前一根已确认 K 所在侧，或逐 K 更新“最近未触碰侧”；
- mutation 瞬间输出 `npocTouchedNow/Price/Count/Direction`；
- 触碰事件进入 Trigger/Action/MCP/alert，而不是只改线样式；
- 数量上限优先统计 active nPOC，已扫历史不能挤掉仍 active 的旧水平。

## 5. OB 质量对象必须携带执行价格

如果 B/C 路径允许 `bullObTradeOk/bearObTradeOk` 单独授权，但 `finalEntry` 只在 FVG CE、Sweep、VA、CVD、通用 support/resistance 中选择，则行动格会写“OB承接”，Entry 却来自 POC/VWAP 等无关价格。

每方向应原子保存：

```text
obId / top / bot / entryPrice(or CE/edge) / score / htf / dist / breaker
```

并确认触发、Entry、MCP、行动格消费同一个胜出 OB。另查 `bornBar`：若它保存原始 OB K，不能用 `bar_index > bornBar` 作为“排除检测当根 K 立即缓解”的条件，应另存 detectedBar/createdBar。

## 6. CVD pivot 必须同 anchor、同质量合同

累计 CVD 在 D/W/M 重置时，前后两个 pivot 值不可直接比较。审计不能只看“以价格 pivot 为锚”，还要检查：

- 两个 pivot 是否携带相同 `anchorId`；
- 当前与上一 pivot 当时的 `cvdQualityOk/sampleCount/method` 是否都合格；
- `calc_bars_count` 之外的历史 bar-fallback 是否可能被当前好质量重新升格；
- 不同 anchor 时应拒绝背离，或改用独立连续 CVD。

只用当前 K 的 `cvdQualityOk` 门控整个历史背离是不充分的。

## 7. 最终价格统一 mintick 量化

“stepSize 是整数 tick”不代表 POC 可成交：桶中心 `(index+0.5)*step` 在奇数 tick 行宽时仍可能落到半 tick。FVG CE、VWAP、ATR Stop 同样可能是任意小数。

最终导出前必须统一量化并重验几何：

1. 生成 raw Entry/Stop/Target；
2. 按方向和产品规则量化到 mintick；
3. 重新验证多单 `stop < entry < target`、空单镜像；
4. 重新计算 R:R；
5. 行动格、MCP、alerts、replay 全部使用量化后的唯一价格。

`format.mintick` 只修字符串显示，不修 Data Window 数值。

## 8. readiness/置信度不得和硬阻断矛盾

计数式 readiness 若只看 Sweep/MSS/FVG/OB/CVD/HTF，而不消费 `geometry/RR/freshness/confirmed`，会出现“X R:R不足”同时“就绪85%”。关闭可选模块时还应动态调整分母，不能关闭 FVG/OB/CVD 后永久扣分，却关闭 HTF 时白送一分。

必查：

- `setupX`、几何错误、最低 R:R、触发过期、未收线是否覆盖 readiness；
- `置信XX%` 是否只是启发式分数，避免宣传为统计概率；
- Entry 已显示“挂单”时，不应无条件再拼“等MSS/等回踩”等未来路径；
- 表格高亮索引必须对准真正的“结论”行，而不是插入新首行后仍写死 `row==0`。

## 9. “显示/风控”输入必须核对真实消费链

两类常见假功能：

- 基差：输入写“显示”，却只计算死 `basisLabel` 或只导 MCP；同时 `isPerp` 识别 `PERP` 与 `.P`，spot 映射却只删除 `.P`，`...PERP` 可能请求自身得到假中性；
- 风控：单笔风险/日亏停止/周亏降频只打包 Data Window，没有仓位、PnL、X闸门消费者。

报告必须明确“Pine 内执行”还是“仅供外部消费者”。整数 RiskPack 还要测试小数步长碰撞，例如 `int()` 是否让 6.0 与 6.5 编码相同。

## 10. Basic 性能：数值同构不等于可以 O(N²) 重算

当前 Profile 为保证历史/实时同构而每根 K 重扫全部已存 intrabars，是正确性优先的架构，但在 Basic 20 秒限制下可能形成二次复杂度。静态审计需同时报告：

- Profile 内累计外层迭代估算；
- 每根 intrabar 跨桶的双循环上界；
- 关闭 CVD/SVP 精度开关时 request 与重计算是否真正短路；
- 没跑 Profiler/Add-to-chart 时只能写“性能风险”，不能断言超时或通过。

## 最小敌对场景矩阵

1. Profile 第一根 K，且该 K 有多根 intrabar；
2. `targetProfileTF == chart TF`；
3. B/C、geometry=true、RR=1.2；
4. `setupX=true` 且原始 B 多条件仍为真；
5. 新周期首 K 穿越 nPOC 并收在另一侧；
6. 一根 K 同时触碰多个 nPOC；
7. 仅 OB 条件授权，附近 POC/VWAP 不在 OB 内；
8. 两个 CVD price pivots 跨 D/W/M reset；
9. 奇数 ticksPerRow 的 POC 作为 Entry；
10. RR不足但共振因子达到 readiness 高档；
11. CVD质量差但硬门槛关闭，检查 EntryValid 与 NoTrade 是否冲突；
12. `...PERP` 与 `.P` 两种永续代码的 spot mapping。
