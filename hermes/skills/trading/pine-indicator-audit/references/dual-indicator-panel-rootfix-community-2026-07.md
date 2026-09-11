# 双指标行动格根因修复与社区复核（2026-07）

> 历史记录（2026-07-01）：本文保留当时现场事实，不作为当前行动格合同。

> 历史记录（2026-07）：本文保留当时现场事实，不作为当前行动格合同。

适用于成熟的 `SVP+ICT+VWAP+CVD` 主指标与 `AggVol` 聚合量能/CVD/OI副指标迭代。

## 用户界面硬偏好

- 主指标行动格不出现“副驾/副驾驶/订单流核对”独立行。
- 副指标用户界面统一显示 `CVD`，不显示“估算/Estimated”；源码注释与方法码仍须诚实保留其低周期价格行为分类口径，不能宣称交易所真实逐笔 bid/ask。
- 主指标固定执行骨架：`结论 / 方向 / 进场 / 止损 / 目标 / 解除（仅有阻断时）/ 确认 / 磁吸↑ / 磁吸↓`。
- 磁吸上下各一行，必须显示目标名称、价格、分数和一位小数ATR距离。
- B/C人工候选保留Entry/Stop/Target；X仍硬阻断。

## “长期禁追”根因模式

错误模式：

```pine
bool xHotExtended = dmiHot and (vwapExtendedUp or vwapExtendedDn)
```

它把任一方向延展变成全局X，会误伤反向计划和无计划状态。正确做法是方向化：

```pine
bool xHotExtendedLong  = dmiHot and vwapExtendedUp and (setupLongA or setupLongB)
bool xHotExtendedShort = dmiHot and vwapExtendedDn and (setupShortA or setupShortB)
bool xHotExtended = xHotExtendedLong or xHotExtendedShort
```

结论行显示具体原因，如 `X · 过热远离`，不要只写泛化“禁追”。

## 磁吸消失根因模式

错误模式：无计划时仍使用 `finalEntryCandidate` 作为所有磁吸距离参考；其值为 `na`，导致距离和上下比较全部为 `na`。

正确分层：

```pine
float magnetAnchorPrice = finalEntryCandidate
float magnetReferencePrice = not na(finalEntryCandidate) ? finalEntryCandidate : close
```

- 候选池选取与行动格上下磁吸：使用 `magnetReferencePrice`，保证无计划时仍显示。
- 最终目标/R:R：仍使用 `magnetAnchorPrice`/最终Entry，避免改变执行几何。
- nPOC与普通流动性池使用同一参考价逻辑。

## 社区与官方复核后的P1顺序

1. 主指标CVD枢轴增加同Anchor ID门控，禁止跨D/W/M累计起点比较。
2. 已确认HTF FVG/OB采用历史偏移配合`lookahead_on`发布，避免额外延迟一整个HTF。
3. 告警从持续状态改为进入事件（`state and not state[1]`），信息类告警合并，释放plot count。
4. 副指标增加逐交易所冻结/更新时间检测；`not na`不等于数据新鲜。
5. 按TradingView官方series-color规则计算plot count；静态扫描的“最低值”不可当真实余量。
6. Sweep默认使用“收回确认”；外侧收盘分类为突破/消耗，不应增加已扫计数。

## Footprint边界

`request.footprint()`（Pine v6，2026-01）适合独立Premium/Ultimate脚本，不直接塞入当前双指标：

- 每脚本最多一个unique footprint请求；可能返回`na`。
- 无数据必须显式显示`NO DATA`，不能与现有CVD静默等价回退。
- 先作为POC/VA、imbalance、delta failure、absorption事件层，不直接改变A/B/C/X。
- Footprint依然按intrabar价格行为分类，不等同交易所逐笔DOM/tape。

## 验证契约

每轮相关修改必须执行：

1. 文本契约测试：禁止词、固定行动格行、方向性X、磁吸fallback、same-anchor。
2. 静态扫描：未定义变量、def-before-use、request展开、plot最低值。
3. TradingView服务器编译；拿不到回执时只能声明本地静态/语义通过。
4. Replay/Data Window golden snapshot：污染未来K线后，历史Grade、Entry/Stop/Target、风险码、CVD事件不得改变。
5. 同步上传源与桌面交付文件后做哈希/字节一致性校验。

## 禁止过度优化

- 不继续给主指标堆新面板、新技术指标或Footprint。
- 不用VP up/down颜色、CVD或OI单独授权下单。
- 不改已确认的pPOC删除、限时nPOC、B/C人工候选、X硬闸门。
- 社区建议只是输入；只有通过当前源码交叉检查与回测后才进入生产决策。