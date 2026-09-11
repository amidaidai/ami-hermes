# 双指标 v2 源码审计新增签名（2026-08-08）

适用：大型 SVP/ICT 主指标 + 聚合成交量/OI/CVD 副指标已能编译，但仍需审计执行合同、数据质量和 Basic 配额。

## 1. X 与 MCP Side 的优先级必须一致

危险模式：

```pine
plot(activeLongPlan ? 1 : activeShortPlan ? -1 : setupX ? 9 : 0, "MCP Side Code", ...)
```

`setupX` 可与原始 A/B/C 布尔状态共存。若多空分支先于 X，面板显示禁做时 MCP 仍可能输出方向。

正确不变量：

- `setupX` 必须先判；
- X 时 Entry/Stop/Target 必须全为 `na`；
- Grade、Side、EntryValid、NoTrade、ExecutionPack 必须共同消费同一最终状态。

## 2. 人工候选与机器导出必须拆开

危险链：

```pine
manualBcCandidate = bcDirectRaw and priceGeometryOk and not setupX
visiblePlan = executablePlan or manualBcCandidate
replayEntry = visiblePlan ? finalEntry : na
```

若 `manualBcCandidate` 不含最低 R:R，低于 1.5R 的 B/C 候选仍会导出价格，同时 NoTrade 又写 R:R 不足，形成矛盾合同。

建议拆成：

- `displayCandidate`：允许行动格给用户看人工参考；
- `exportCandidate`：满足最低 R:R、几何、触发时效、收线和非 X 后才进入 MCP；
- EntryValid 明确区分显示候选、人工可评估、机器可执行。

敌对测试至少覆盖 R:R=1.2/1.5/2.0。

## 3. 单K Profile：数值计算与绘图宽度分离

若 `processAndRender()` 入口要求 `profileEndBar > profileStartBar`，则 Profile 周期等于图表周期时每期只有一根图表K，POC/VA/nPOC可能永久不生成。

修法：

- 数值计算允许 `endBar == startBar`，前提是已有图表K或 intrabar 数据；
- 直方图、线段宽度单独使用至少 1K 的视觉兜底；
- 测试手动 Profile TF = chart TF。

## 4. nPOC 首K触碰不能用同一根 close 自证

若新周期首K同时：

1. 用当前 `close` 建立 `approachSide`；
2. 再用同一根 `close` 判 `closeReclaim`；

则触碰方向与收回方向会形成自证。应保存创建前/首次接近时的方向快照，触碰事件只消费快照；Trigger、Action、MCP 使用同一事件 ID 与年龄。

## 5. OB 触发必须原子绑定 Entry 几何

若 OB 可以授权 B/C 或成为 Trigger Code，胜出 OB 必须携带：

`id / side / top / bottom / entry / score / HTF / bornBar`

不能出现面板写“OB承接”，最终 Entry 却来自无关 FVG、VA边、VWAP或通用候选。触发原因、价格源、止损和导出必须同源。

## 6. 最终价格统一量化

SVP 桶宽对齐 mintick 不代表 FVG CE、ATR Stop、磁吸 Target 已对齐。标准顺序：

1. 生成候选 Entry/Stop/Target；
2. 按方向与 mintick 量化；
3. 重验 `stop < entry < target` 或镜像空单；
4. 重算 R:R；
5. 再统一写行动格、提醒、回放和 MCP。

## 7. Freshness 不能用 `barssince(not na(value))`

持续前向填充的序列会让该值长期为 0，这只证明“当前非空”，不证明数据刚更新。

最低可接受实现：

- 每 venue 记录值变化或源时间变化；
- 输出 cadence、最后变化年龄、coverage、dropout；
- 无服务器 timestamp 时明确叫“更新年龄代理”，不得写成真实延迟。

## 8. OI 空向共振必须与四象限一致

统一语义：

- 价涨 + OI涨 = 新多扩仓；
- 价跌 + OI涨 = 新空扩仓；
- 价涨 + OI跌 = 空回补；
- 价跌 + OI跌 = 多平仓/去杠杆。

因此趋势确认票对多空都应优先消费 `oiUp && consensusOk`。危险模式是正式 Confirm Score 对空使用 OI涨，而“共振 x/4”却写 `dirDn && oiDn`，导致新空不给票、多平仓反而给票。所有面板、评分、Composite 和告警必须复用同一 OI 语义函数。

## 9. 非适用市场要短路请求，不只隐藏显示

`isCrypto` 若只保护 table/plot，成交量聚合、OI、LSR、基差仍会在 XAU/外汇图表历史阶段预取并消耗动态上下文。应在请求函数入口按市场门控；同时保留 5 所成交量和 4 所 OI，不用删源换配额。

## 10. 验证闭环

1. 跑静态扫描：request 展开、plot、对象、def-before-use、未定义变量；
2. 用 `scripts/tv_pine_check_files.mjs` 对本地文件调用 TradingView `translate_light`；
3. 只有 `status=200, errors=[], warnings=[]` 才写“服务器编译通过”；
4. 运行时 unique request、plot 实际计数、Basic 20秒性能仍需 Add-to-chart + Profiler 验证；
5. 服务器编译通过不等于上述决策合同正确。
