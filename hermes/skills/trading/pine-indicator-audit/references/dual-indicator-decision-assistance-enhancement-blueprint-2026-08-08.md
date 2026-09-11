# 双指标决策辅助增强蓝图（2026-08-08）

适用：TradingView Basic 下的 `SVP+ICT+VWAP+CVD` 主指标与 `Volume Aggregated Spot & Futures` 副指标。目标只优化指标本体对盘中决策的帮助，不涉及回测、复盘或盈利主张。

## 一、产品边界

- 主指标是唯一执行授权源：方向、等级、触发路径、Entry、Stop、Target、R:R、X硬阻断。
- 副指标只能确认、降级、否决：不得独立开单、不得给Entry/Stop/Target、不得把B/C升级为A。
- 推荐四态：`A可执行 / B-C人工候选 / WAIT / X`。
- 优先级固定：`X > WAIT > A执行 > B/C观察 > 无计划`。
- X或WAIT时，可执行Entry/Stop/Target必须原子清空；B/C价格进入独立Watch字段。

## 二、实施依赖顺序

1. 唯一 `FinalPlan`：方向、模型、胜出区域、Entry、Stop、Target、R:R、事件年龄原子绑定。
2. 修复X优先级；机器Side不能在X时继续输出多/空。
3. 拆分 `HardBlockCode / WaitCode / WarningCode`。
4. 所有价格按 `syminfo.mintick` 量化后重验多空几何和R:R。
5. Winning-zone合同：行动格写OB/FVG/iFVG时，价格必须来自同一胜出对象。
6. 触发状态机：事件柱、年龄、有效期、收线状态、下一缺口。
7. 行动格收敛后，再增加结构模块。

禁止先堆新概念再修执行合同。

## 三、主指标高价值增强排序

### 第一层：结构质量

1. OB结构源锚定：BOS位移起点选择最深/最极端反向K；FVG重叠可设必选或加权。
2. OB缓解语义：默认建议50% CE缓解，收盘完全穿透才失效；支持近端触碰/CE/影线穿透/收盘穿透/完全填补。
3. iFVG状态机：FVG收盘确认穿透后转极性，等待首次反向回测，复用原对象。
4. EQH/EQL流动性簇：已确认pivot、ATR+mintick容差、至少2触点、每侧仅保留2–3组；只进入“扫位→收回→MSS→回踩”路径。
5. Developing POC/VA迁移：区分价格离开价值与价值自身上移/下移/重叠/扩张。
6. 前日VP投影：前日POC/VAH/VAL，与nPOC去重，统一首次触碰/接受/收回/消费状态。
7. HVN/LVN：只保留每侧2–3个显著节点；HVN作接受/磁吸，LVN作低接受通道；进入Magnet而非新增方向评分。
8. 语义级关键位聚类：EQH/PDH/VAH/HVN/FVG等相近水平先聚类，只选一个winner，避免重复投票。

### 后置项

- BPR：二阶段以后。
- Adaptive Pivot：会改变全链结构语义，必须后置。
- 不新增Mitigation Block标签（与现有BOS后OB高度重复）。
- 不再新增0–100总分、第三套CVD、HH/HL/LH/LL满图标签。

## 四、副指标数据合同

必须保留5所成交量（Binance/Bybit/OKX/Coinbase/Bitget）和4所OI，不得为配额静默削源。

### P0增强

1. 逐venue freshness：同一请求tuple带回 `value + source time`；按各源cadence记录年龄、掉线、恢复。`not na`不等于新鲜，值不变也不等于失效。
2. 成交量逐源正规化：base量乘本所close；quote量直接使用；tick/n/a标单位未知，不进入USD总量。禁止先合并再乘主图close。
3. 数据存在与零成交分离；覆盖分母按现货/永续预期路由计算。
4. OI只用每所变化率、breadth、agreement、dispersion、dominance做决策；raw total仅兼容展示。
5. OI四象限统一：
   - 价涨+OI涨=扩仓上涨/新多；
   - 价跌+OI涨=扩仓下跌/新空；
   - 价涨+OI跌=减仓上涨/空回补；
   - 价跌+OI跌=减仓下跌/多平仓。
   空向OI确认不能写成“价跌+OI降”。
6. 爆仓压力代理v2：必须有跨所OI一致下降+永续量尖峰+价格位移+CVD同向；OI上涨时只能叫扩仓，不叫爆仓。界面可保留直白“爆仓”，Data Window标 `LIQ_METHOD=PROXY`。
7. 唯一 `finalAggState` 贯穿面板、评分、提醒和MCP：`确认多/确认空/冲突/数据降级/中性/无效`。

### P1增强

- 五所量能宽度：各所相对自身基线，输出同步放量家数，避免单所主导伪共振。
- 副CVD改为跨所流向宽度：每所用自己的OHLC估算方向，只报告同向/分歧；主指标lower-TF CVD负责执行背景，二者不重复计票。
- LSR是账户数比，不是名义仓位；只作同向拥挤降级，不独立反手。
- 质量码只编码方法、venue数、单位可比性、freshness、anchor、confirmed/live；背离属于事件码，不应混进质量码。

## 五、主副单通道总线

Basic有一个indicator-on-indicator连接。推荐AggVol导出一个packed `valid/risk/confirm`数值，主指标用一个 `input.source()`消费，使主指标继续作为唯一最终裁决器。禁止形成循环依赖。

联合规则：

- 主X + 副任意 = X。
- 主WAIT + 副同向 = WAIT，并显示“订单流已就绪，继续等主触发”。
- 主A + 副同向且数据健康 = A确认。
- 主A + 副冲突/OI分歧/过期 = 降级WAIT或B。
- 主B/C + 副同向 = 仍为B/C，不升级A。
- 非加密 = 完全忽略AggVol。

## 六、行动格规范

主指标建议6行以内：

1. 结论：`↑A多 / ↓A空 / ○等待 / ×禁做`。
2. 位置：PD、VA、VWAP、dPOC迁移。
3. 路径：`扫位✓ → MSS○ → 回踩○（1/3）`，显示唯一下一缺口。
4. 执行：Entry/Stop/Target/R:R；仅A执行或明确B/C观察字段显示。
5. 时效/失效：事件年龄、剩余K数、结构失效。
6. 风险：只显示最高优先级blocker和副指标支持/冲突。

副指标只显示：支持/冲突/降权/中性/无效；成交宽度、OI四象限、CVD宽度、数据质量、拥挤/爆仓代理。界面可不写“估算”，但源码注释、tooltip和Method Code必须诚实披露。

## 七、Basic与2026能力边界

- Basic：2指标/图、5000历史K、20秒、0技术告警、100K intrabars、40 unique requests。
- `alert()`不能绕过0技术告警；Basic专版不应保留无用`alertcondition()`占plot。
- `request.footprint()`仅Premium/Ultimate且每脚本1个unique call；Basic生产版不加入。
- Footprint、官方CVD、普通VP的buy/sell分类均不得宣传为交易所逐笔aggressor tape；当前技术文档优先于营销博客。
- 2026 UDT排序与二分查找只在Profiler证明大型对象数组扫描是热点后使用；小数组不为“新功能”而改。

## 八、性能顺序

1. SVP增量桶缓存：新intrabar增量入桶，价格范围扩张才dirty rebuild。
2. 删除无消费者的HTF请求和会话CVD链。
3. 非加密动态请求门控。
4. 同context多字段tuple合并。
5. 表格仅last bar更新；对象优先`set*()`复用。
6. 新增多区前建立统一Zone Registry/对象池。
7. 最终以5m/15m/1h/4h Pine Profiler和Add-to-chart验证；云端编译不证明20秒性能通过。

## 九、权威参考

- TradingView Pine Release Notes: https://www.tradingview.com/pine-script-docs/release-notes/
- Limitations: https://www.tradingview.com/pine-script-docs/writing/limitations/
- Other timeframes/data: https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/
- Repainting: https://www.tradingview.com/pine-script-docs/concepts/repainting/
- Profiler: https://www.tradingview.com/pine-script-docs/writing/profiling-and-optimization/
- Volume Profile: https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/
- Official CVD: https://www.tradingview.com/support/solutions/43000725058-cumulative-volume-delta/
- Open Interest: https://www.tradingview.com/support/solutions/43000685269-open-interest/
- Bybit OI: https://bybit-exchange.github.io/docs/v5/market/open-interest

复用前重新访问官方URL；技术文档/API reference优先于博客和社区说明。